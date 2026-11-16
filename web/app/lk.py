"""Thin wrapper around the LiveKit server API: rooms, access tokens, muting."""
import json
import logging
from datetime import timedelta

from livekit import api

from .config import settings

log = logging.getLogger("hudd.livekit")

# Participants may only publish camera, microphone and screen share.
SOURCES = ["camera", "microphone", "screen_share", "screen_share_audio"]


def _http_url() -> str:
    return settings.livekit_url.replace("ws://", "http://").replace("wss://", "https://")


def client() -> api.LiveKitAPI:
    return api.LiveKitAPI(_http_url(), settings.livekit_api_key, settings.livekit_api_secret)


def make_token(room: str, identity: str, name: str, role: str) -> str:
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_metadata(json.dumps({"role": role}))
        .with_ttl(timedelta(hours=12))
        .with_grants(api.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True,
                                     can_publish_data=True, can_publish_sources=SOURCES))
        .to_jwt()
    )


async def create_room(code: str, metadata: dict) -> None:
    async with client() as lk:
        await lk.room.create_room(api.CreateRoomRequest(
            name=code, empty_timeout=settings.room_empty_timeout, departure_timeout=settings.room_departure_timeout,
            metadata=json.dumps(metadata, ensure_ascii=False)))


async def list_rooms(names: list[str] | None = None) -> dict[str, dict]:
    """Rooms that exist on the LiveKit server right now: name -> {metadata, participants}."""
    async with client() as lk:
        res = await lk.room.list_rooms(api.ListRoomsRequest(names=names or []))
    out = {}
    for r in res.rooms:
        try:
            meta = json.loads(r.metadata or "{}")
        except ValueError:
            meta = {}
        out[r.name] = {"metadata": meta, "participants": r.num_participants}
    return out


async def delete_room(code: str) -> None:
    try:
        async with client() as lk:
            await lk.room.delete_room(api.DeleteRoomRequest(room=code))
    except Exception as e:  # already gone
        log.info("delete_room(%s): %s", code, e)


def _role(p) -> str:
    try:
        return str(json.loads(p.metadata or "{}").get("role") or "")
    except ValueError:
        return ""


async def set_mics(code: str, identity: str | None, mute: bool) -> list[str]:
    """Host microphone control. identity=None means everyone except hosts.
    Mute: turns the microphone off on the server right away and tells the person.
    Unmute: browsers do not allow turning on someone else's microphone, so we only send a request
    that the person confirms. Returns the identities affected."""
    hit: list[str] = []
    async with client() as lk:
        res = await lk.room.list_participants(api.ListParticipantsRequest(room=code))
        for p in res.participants:
            if identity is None and _role(p) == "owner":
                continue
            if identity is not None and p.identity != identity:
                continue
            mics = [t for t in p.tracks if t.source == api.TrackSource.MICROPHONE]
            if mute:
                live = [t for t in mics if not t.muted]
                for t in live:
                    await lk.room.mute_published_track(api.MuteRoomTrackRequest(room=code, identity=p.identity, track_sid=t.sid, muted=True))
                if live:
                    hit.append(p.identity)
            elif not mics or all(t.muted for t in mics):
                hit.append(p.identity)
        if hit:
            await lk.room.send_data(api.SendDataRequest(
                room=code, data=json.dumps({"action": "muted" if mute else "unmute"}).encode(),
                kind=api.DataPacket.Kind.RELIABLE, topic="hudd.ctl", destination_identities=hit))
    return hit
