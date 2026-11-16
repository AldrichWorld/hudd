"""Meeting state without a database.

The LiveKit server is the source of truth: a meeting exists exactly as long as its LiveKit room exists.
The room's metadata carries everything needed to rebuild the meeting after this service restarts:
    {"title": ..., "owner": <host name>, "pw": <keyed hash of the meeting password, or "">}
This process only keeps a small in-memory cache on top of that:
    - the plain meeting password, so the host can share it (lost on restart; the host's browser keeps a copy)
    - who created the meeting (client IP) and when, for the abuse limits
Host rights come from a host key that is an HMAC of the meeting ID, so they survive restarts too.
"""
import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field

from . import lk
from .config import settings

log = logging.getLogger("hudd.rooms")


@dataclass
class Room:
    code: str
    title: str
    owner: str
    pw: str = ""                 # keyed hash of the password ("" = no password)
    password: str | None = None  # plain password, only while this process remembers it
    ip: str | None = None        # creator's IP (for the abuse limits)
    created: float = field(default_factory=time.time)


_cache: dict[str, Room] = {}
_created_by_ip: dict[str, list[float]] = {}


def _mac(*parts: str) -> str:
    return hmac.new(settings.secret_key.encode(), ":".join(parts).encode(), hashlib.sha256).hexdigest()


def owner_key(code: str) -> str:
    return _mac("owner", code)[:32]


def is_owner(code: str, key: str | None) -> bool:
    return bool(key) and hmac.compare_digest(key, owner_key(code))


def pw_hash(code: str, password: str) -> str:
    return _mac("pw", code, password)[:32] if password else ""


def pw_ok(room: Room, given: str | None) -> bool:
    return not room.pw or hmac.compare_digest(pw_hash(room.code, (given or "").strip()), room.pw)


def _from_live(code: str, info: dict) -> Room:
    meta = info.get("metadata") or {}
    old = _cache.get(code)
    room = Room(code=code, title=str(meta.get("title") or ""), owner=str(meta.get("owner") or ""), pw=str(meta.get("pw") or ""))
    if old:
        room.password, room.ip, room.created = old.password, old.ip, old.created
    _cache[code] = room
    return room


async def get(code: str) -> Room | None:
    """The meeting if it is still open on the LiveKit server, otherwise None."""
    live = await lk.list_rooms([code])
    if code not in live:
        _cache.pop(code, None)
        return None
    return _from_live(code, live[code])


def _new_code() -> str:
    return str(secrets.randbelow(900_000_000) + 100_000_000)   # 9 digits, never starts with 0


def check_limits(ip: str) -> tuple[str, int] | None:
    """Returns (message key, limit) when this IP may not start another meeting now."""
    now = time.time()
    recent = [t for t in _created_by_ip.get(ip, []) if now - t < 3600]
    _created_by_ip[ip] = recent
    if settings.open_rooms_per_ip > 0 and sum(1 for r in _cache.values() if r.ip == ip) >= settings.open_rooms_per_ip:
        return "open_limit", settings.open_rooms_per_ip
    if settings.rooms_per_hour_per_ip > 0 and len(recent) >= settings.rooms_per_hour_per_ip:
        return "rate_limit", settings.rooms_per_hour_per_ip
    return None


async def create(title: str, owner: str, password: str, ip: str) -> Room:
    for _ in range(20):
        code = _new_code()
        if code in _cache or await lk.list_rooms([code]):
            continue
        room = Room(code=code, title=title, owner=owner, pw=pw_hash(code, password), password=password or None, ip=ip)
        await lk.create_room(code, {"title": title, "owner": owner, "pw": room.pw})
        _cache[code] = room
        _created_by_ip.setdefault(ip, []).append(time.time())
        return room
    raise RuntimeError("could not allocate a meeting ID")


async def end(code: str) -> None:
    await lk.delete_room(code)
    _cache.pop(code, None)


async def sweep_forever(interval: float = 60) -> None:
    """Forget meetings that LiveKit has closed, and old rate-limit entries, so memory stays small."""
    while True:
        await asyncio.sleep(interval)
        try:
            live = await lk.list_rooms()
            for code in [c for c in _cache if c not in live]:
                _cache.pop(code, None)
            now = time.time()
            for ip in [ip for ip, ts in _created_by_ip.items() if not ts or now - ts[-1] > 3600]:
                _created_by_ip.pop(ip, None)
        except Exception as e:
            log.warning("sweep failed: %s", e)
