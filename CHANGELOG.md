# Changelog

## 1.0.0 (2026-11-17)

First public release.

- Video and audio meetings in the browser, on computers and phones
- Screen sharing, tuned for sharp text (1 s receive buffer)
- Chat with @mentions; grid and speaker layouts, pin and full screen
- Meeting passwords; host controls: mute everyone, mute one person, ask to unmute, end for everyone
- 13 interface languages, including right-to-left Arabic and Persian
- Installable as an app (PWA)
- No database and no accounts: meeting state lives in memory and in LiveKit room metadata, and survives a restart of the web service
- One-command deployment with Docker (`./deploy.sh up`: local, own domain, or behind an existing proxy), or from source with systemd, Caddy or Nginx
