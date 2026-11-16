**English** · [简体中文](install-from-source.zh-CN.md)

# Install Hudd from source (without Docker)

This guide runs Hudd directly on a Linux server, with systemd keeping it running. If you have Docker, `./deploy.sh` in the [README](../README.md) is simpler.

Hudd has two programs of its own to run, plus a web server in front:

| Program | Listens on | Purpose |
|---|---|---|
| LiveKit server | `127.0.0.1:7880`, TCP `7881`, UDP `7882` | Carries audio, video and screen sharing |
| Hudd web service (Python) | `127.0.0.1:8000` | Pages and the small meeting API |
| Caddy or Nginx | `80`, `443` | HTTPS; forwards `/rtc` and `/twirp` to LiveKit and everything else to Hudd |

## 1. Requirements

- A Linux server (Debian or Ubuntu commands are shown) with a public IP and a domain name whose DNS A record points to it
- Python 3.11 or newer, Node.js 18 or newer (only needed to build), git, curl
- Firewall open for TCP 80, 443, 7881 and UDP 7882. Keep 7880 and 8000 closed to the outside.

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv nodejs npm
```

## 2. Get the source

```bash
sudo git clone https://github.com/AldrichWorld/hudd.git /opt/hudd
sudo useradd --system --home-dir /opt/hudd --shell /usr/sbin/nologin hudd
sudo chown -R hudd:hudd /opt/hudd
cd /opt/hudd
```

The services run as the user `hudd`, and the code lives in `/opt/hudd`. If you choose another folder, change the paths in the two files under `config/systemd/` too.

## 3. Build

```bash
# Front-end: copies the LiveKit browser SDK into web/static/vendor (the pages load nothing from CDNs)
sudo -H -u hudd sh -c 'cd web/vendor-src && npm ci --no-audit --no-fund && sh build.sh ../static/vendor'

# Back-end: a Python virtual environment with the web service's dependencies
sudo -H -u hudd python3 -m venv .venv
sudo -H -u hudd .venv/bin/pip install -r web/requirements.txt
```

## 4. Configure

```bash
sudo -H -u hudd ./deploy.sh config
```

It asks for your domain and an optional passcode for starting meetings, then writes:

- `.env`: your settings, plus generated keys (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `SECRET_KEY`). Keep this file private.
- `config/livekit.yaml`: the LiveKit configuration made from `.env`.

Check that `PUBLIC_HOST` in `.env` is the server's public IP. After changing `.env`, run `./deploy.sh config` again.

## 5. Install LiveKit

```bash
curl -sSL https://get.livekit.io | bash     # installs /usr/local/bin/livekit-server
```

See LiveKit's [self-hosting docs](https://docs.livekit.io/home/self-hosting/) for other ways to install it.

## 6. Run both services with systemd

```bash
sudo cp config/systemd/hudd-livekit.service config/systemd/hudd-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hudd-livekit hudd-web
systemctl status hudd-livekit hudd-web --no-pager
curl -s http://127.0.0.1:8000/healthz      # {"ok":true}
```

## 7. HTTPS and the domain

**Caddy** (gets and renews the certificate by itself). Install it from [caddyserver.com/docs/install](https://caddyserver.com/docs/install), then:

```bash
sudo cp config/Caddyfile.native /etc/caddy/Caddyfile
sudo sed -i 's/meet.example.com/YOUR-DOMAIN/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

**Or Nginx** with Certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp config/nginx-hudd.conf /etc/nginx/sites-available/hudd
sudo sed -i 's/meet.example.com/YOUR-DOMAIN/' /etc/nginx/sites-available/hudd
sudo ln -s /etc/nginx/sites-available/hudd /etc/nginx/sites-enabled/hudd
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d YOUR-DOMAIN
```

Open `https://YOUR-DOMAIN` and start a meeting.

## Update

```bash
cd /opt/hudd
sudo -H -u hudd git pull --ff-only
sudo -H -u hudd sh -c 'cd web/vendor-src && npm ci --no-audit --no-fund && sh build.sh ../static/vendor'
sudo -H -u hudd .venv/bin/pip install -r web/requirements.txt
sudo systemctl restart hudd-web
```

Restarting `hudd-web` does not interrupt meetings in progress. Restart `hudd-livekit` only when needed, because that ends the meetings that are running.

## Try it on your own computer

For a quick look without a domain, run LiveKit in development mode and start the web service against it:

```bash
livekit-server --dev --bind 127.0.0.1      # in one terminal
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000      # in another
```

Then open `http://localhost:8000`. Development mode uses fixed test keys, so use it only on your own computer.

## When something does not work

- `journalctl -u hudd-web -u hudd-livekit -f` shows both services' logs.
- People can join but see no video: TCP 7881 or UDP 7882 is blocked, or `PUBLIC_HOST` in `.env` is not the public IP (run `./deploy.sh config` and restart `hudd-livekit` after fixing it).
- The page loads but meetings cannot start: the web service cannot reach LiveKit at `127.0.0.1:7880`, or the keys in `.env` and `config/livekit.yaml` differ (`./deploy.sh config` writes both from `.env`).
