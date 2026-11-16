"""Settings, read from environment variables (see .env.example)."""
import hashlib
import os


def _int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    return int(v) if v else default


class Settings:
    app_name = os.getenv("APP_NAME", "Hudd").strip() or "Hudd"

    # LiveKit server (the media server). The browser reaches it through Caddy at /rtc on the same origin.
    livekit_url = os.getenv("LIVEKIT_URL", "ws://127.0.0.1:7880")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
    livekit_public_url = os.getenv("LIVEKIT_PUBLIC_URL", "")   # empty = same origin as the page

    # Used to sign host keys and password checks. Falls back to a value derived from the LiveKit secret.
    secret_key = os.getenv("SECRET_KEY", "").strip() or hashlib.sha256(("hudd:" + livekit_api_secret).encode()).hexdigest()

    domain = os.getenv("DOMAIN", "").strip()
    public_host = os.getenv("PUBLIC_HOST", "").strip()
    https_port = _int("HTTPS_PORT", 8443)

    # Optional: only people who know this passcode can start meetings (anyone can still join with a link).
    create_passcode = os.getenv("CREATE_PASSCODE", "").strip()

    # How long LiveKit keeps a meeting that nobody has joined yet, and after the last person leaves (seconds).
    room_empty_timeout = _int("ROOM_EMPTY_TIMEOUT", 1800)
    room_departure_timeout = _int("ROOM_DEPARTURE_TIMEOUT", 120)

    # Abuse limits per client IP (0 = off). Kept in memory.
    rooms_per_hour_per_ip = _int("ROOMS_PER_HOUR_PER_IP", 20)
    open_rooms_per_ip = _int("OPEN_ROOMS_PER_IP", 10)

    # Proxies in front of Caddy whose X-Forwarded-For can be trusted (comma separated IPs or CIDRs).
    trusted_proxies = [x.strip() for x in os.getenv("TRUSTED_PROXIES", "").replace(" ", ",").split(",")
                       if x.strip() and x.strip() != "private_ranges"]

    # Link to the source code shown in the page footer (empty = hide).
    source_url = os.getenv("SOURCE_URL", "https://github.com/AldrichWorld/hudd").strip()


settings = Settings()
