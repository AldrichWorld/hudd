"""Hudd web service: serves the pages and a small JSON API; all media goes through LiveKit."""
import asyncio
import hashlib
import hmac
import html as htmllib
import ipaddress
import json
import logging
import re
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import i18n, lk, rooms
from .config import settings
from .i18n import tr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hudd")

STATIC = Path(__file__).resolve().parent.parent / "static"
app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.add_middleware(i18n.LangMiddleware)

CODE_RE = re.compile(r"^\d{9}$")


def _build_id() -> str:
    """Changes whenever a page, script or stylesheet changes, so browsers never use stale files."""
    h = hashlib.sha256()
    for f in sorted(STATIC.rglob("*")):
        if f.is_file() and f.suffix in (".html", ".js", ".css"):
            h.update(f.read_bytes())
    return h.hexdigest()[:10]


BUILD_ID = _build_id()
_ASSET_RE = re.compile(r'((?:src|href)="/static/[^"?]+\.(?:js|css))"')


def _page(name: str) -> HTMLResponse:
    page = (STATIC / name).read_text(encoding="utf-8")
    page = _ASSET_RE.sub(lambda m: f'{m.group(1)}?v={BUILD_ID}"', page)
    page = page.replace("{{APP_NAME}}", htmllib.escape(settings.app_name))
    boot = {"name": settings.app_name, "build": BUILD_ID, "source": settings.source_url}
    page = page.replace("<head>", f"<head>\n<script>window.APP={json.dumps(boot)};</script>", 1)
    return HTMLResponse(page, headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def _cache_headers(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static/"):
        # Files linked with ?v=<build> can be cached for a long time; others are revalidated (ETag → 304).
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable" if "v=" in request.url.query else "no-cache"
    return resp


# ---------------- client IP (for the abuse limits) ----------------
_PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "fd00::/8", "::1/128")]


def _trusted(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    if any(a in n for n in _PRIVATE if n.version == a.version):
        return True
    for t in settings.trusted_proxies:
        try:
            if a in ipaddress.ip_network(t, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request) -> str:
    """The left-most X-Forwarded-For entry can be forged, so walk from the right and skip trusted proxies."""
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if request.client:
        hops.append(request.client.host)
    for h in reversed(hops):
        if not _trusted(h):
            return h
    return hops[0] if hops else "?"


# ---------------- request bodies ----------------
class Person(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)

    def nick(self) -> str:
        n = self.nickname.strip()
        if not n:
            raise HTTPException(400, tr("nick_required"))
        return n


class CreateReq(Person):
    title: str | None = Field(default=None, max_length=64)
    passcode: str | None = Field(default=None, max_length=128)
    room_pass: str | None = Field(default=None, max_length=32)


class JoinReq(Person):
    owner_key: str | None = None
    room_pass: str | None = Field(default=None, max_length=64)


class OwnerReq(BaseModel):
    owner_key: str | None = None


class MuteReq(OwnerReq):
    identity: str | None = Field(default=None, max_length=128)   # empty = everyone except hosts
    mute: bool = True


# ---------------- helpers ----------------
def _code(code: str) -> str:
    c = code.replace(" ", "")
    if not CODE_RE.match(c):
        raise HTTPException(404, tr("room_gone"))
    return c


async def _room_or_404(code: str) -> rooms.Room:
    try:
        room = await rooms.get(_code(code))
    except HTTPException:
        raise
    except Exception as e:
        log.error("livekit unavailable: %s", e)
        raise HTTPException(502, tr("livekit_down"))
    if not room:
        raise HTTPException(404, tr("room_gone"))
    return room


def _public(room: rooms.Room, owner: bool) -> dict:
    data = {"code": room.code, "title": room.title, "owner_nickname": room.owner, "status": "open", "has_password": bool(room.pw)}
    if owner:   # only the host gets the password back (to share it in the invite)
        data["password"] = room.password
    return data


def _join(room: rooms.Room, nick: str, role: str) -> dict:
    identity = "u_" + hashlib.sha256(f"{room.code}{nick}{time.time_ns()}".encode()).hexdigest()[:10]
    return {"room": _public(room, role == "owner"), "identity": identity, "role": role,
            "token": lk.make_token(room.code, identity, nick, role), "livekit_url": settings.livekit_public_url}


# Wrong meeting passwords: at most 10 tries per IP and meeting within 10 minutes.
_PASS_FAILS: dict[tuple[str, str], list[float]] = {}
PASS_MAX_FAILS, PASS_WINDOW = 10, 600


def _check_pass(room: rooms.Room, given: str | None, request: Request) -> None:
    if not room.pw:
        return
    key, now = (room.code, client_ip(request)), time.time()
    fails = [t for t in _PASS_FAILS.get(key, []) if now - t < PASS_WINDOW]
    if len(fails) >= PASS_MAX_FAILS:
        _PASS_FAILS[key] = fails
        raise HTTPException(429, tr("room_pass_locked"))
    if rooms.pw_ok(room, given):
        _PASS_FAILS.pop(key, None)
        return
    if not (given or "").strip():
        raise HTTPException(403, tr("room_pass_required"))
    fails.append(now)
    _PASS_FAILS[key] = fails
    if len(_PASS_FAILS) > 5000:   # keep memory bounded
        for k in [k for k, v in _PASS_FAILS.items() if not v or now - v[-1] > PASS_WINDOW]:
            _PASS_FAILS.pop(k, None)
    raise HTTPException(403, tr("room_pass_wrong"))


# ---------------- pages ----------------
@app.get("/", include_in_schema=False)
async def index():
    return _page("index.html")


@app.get("/r/{code}", include_in_schema=False)
async def room_page(code: str):
    return _page("room.html")


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"ok": True}


# ---------------- PWA: installable on computers and phones ----------------
@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    icon = lambda f: f"/static/brand/app/{f}?v={BUILD_ID}"
    data = {
        "id": "/", "name": settings.app_name, "short_name": settings.app_name, "description": "Video meetings in your browser",
        "start_url": "/?source=pwa", "scope": "/", "display": "standalone", "background_color": "#061a13", "theme_color": "#061a13",
        "icons": [
            {"src": icon("icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon("icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icon("icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return Response(json.dumps(data), media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


# The service worker only makes the app installable and shows a notice when offline. It caches nothing.
_SW = """const OFFLINE = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__NAME__</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#061a13;color:#e8f5ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;text-align:center}
b{display:block;font-size:22px;margin-bottom:8px;color:#3ee59a}button{margin-top:18px;padding:10px 22px;border:0;border-radius:10px;background:#3ee59a;color:#04301e;font-size:15px;font-weight:600}</style></head>
<body><div><b>__NAME__</b>No internet connection<br><button onclick="location.reload()">↻</button></div></body></html>`;
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(() => new Response(OFFLINE, { headers: { 'Content-Type': 'text/html; charset=utf-8' } })));
});
"""


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return Response(_SW.replace("__NAME__", htmllib.escape(settings.app_name)), media_type="text/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


# ---------------- API ----------------
@app.get("/api/config")
async def get_config():
    if settings.domain:
        share_base = f"https://{settings.domain}"
    elif settings.public_host:
        share_base = f"https://{settings.public_host}:{settings.https_port}"
    else:
        share_base = ""
    return {"share_base": share_base, "require_passcode": bool(settings.create_passcode)}


@app.post("/api/rooms")
async def create_room(req: CreateReq, request: Request):
    if settings.create_passcode and not hmac.compare_digest((req.passcode or "").strip(), settings.create_passcode):
        raise HTTPException(403, tr("bad_passcode"))
    nick = req.nick()
    ip = client_ip(request)
    hit = rooms.check_limits(ip)
    if hit:
        log.warning("limit %s hit by %s", hit[0], ip)
        raise HTTPException(429, tr(hit[0], n=hit[1]))
    title = (req.title or "").strip() or tr("default_title", nick=nick)
    try:
        room = await rooms.create(title, nick, (req.room_pass or "").strip(), ip)
    except Exception as e:
        log.error("create room failed: %s", e)
        raise HTTPException(502, tr("livekit_down"))
    log.info("meeting %s created", room.code)
    return {**_join(room, nick, "owner"), "owner_key": rooms.owner_key(room.code)}


@app.get("/api/rooms/{code}")
async def get_room(code: str, x_owner_key: str | None = Header(default=None)):
    room = await _room_or_404(code)
    return _public(room, rooms.is_owner(room.code, x_owner_key))


@app.post("/api/rooms/{code}/join")
async def join_room(code: str, req: JoinReq, request: Request):
    room = await _room_or_404(code)
    nick = req.nick()
    owner = rooms.is_owner(room.code, req.owner_key)
    if not owner:
        _check_pass(room, req.room_pass, request)
    return _join(room, nick, "owner" if owner else "member")


@app.post("/api/rooms/{code}/mute")
async def mute(code: str, req: MuteReq):
    """Host: mute everyone / ask everyone to unmute / mute one person / ask one person to unmute."""
    room = await _room_or_404(code)
    if not rooms.is_owner(room.code, req.owner_key):
        raise HTTPException(403, tr("owner_only"))
    try:
        hit = await lk.set_mics(room.code, req.identity or None, req.mute)
    except Exception as e:
        log.error("mute failed for %s: %s", room.code, e)
        raise HTTPException(502, tr("livekit_down"))
    return {"count": len(hit), "identities": hit}


@app.post("/api/rooms/{code}/end")
async def end_meeting(code: str, req: OwnerReq):
    c = _code(code)
    if not rooms.is_owner(c, req.owner_key):
        raise HTTPException(403, tr("owner_only"))
    await rooms.end(c)
    log.info("meeting %s ended by host", c)
    return {"status": "ended"}


_bg: set[asyncio.Task] = set()


@app.on_event("startup")
async def _start() -> None:
    t = asyncio.create_task(rooms.sweep_forever())
    _bg.add(t)
    t.add_done_callback(_bg.discard)
