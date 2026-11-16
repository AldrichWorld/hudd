#!/usr/bin/env bash
# ============================================================
# Hudd one-command deployment
#   ./deploy.sh            first deployment, or rebuild and start (default: up)
#   ./deploy.sh status     show the services
#   ./deploy.sh logs [svc] follow the logs (svc: web | livekit | caddy)
#   ./deploy.sh restart    restart everything (after editing .env)
#   ./deploy.sh down       stop and remove the containers
#   ./deploy.sh update     git pull, then deploy again
#   ./deploy.sh config     only create .env and config/livekit.yaml (for running without Docker,
#                          see docs/install-from-source.md)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

C_G='\033[32m'; C_Y='\033[33m'; C_R='\033[31m'; C_B='\033[1m'; C_0='\033[0m'
info() { echo -e "${C_G}▶${C_0} $*"; }
warn() { echo -e "${C_Y}⚠${C_0} $*"; }
die()  { echo -e "${C_R}✖ $*${C_0}" >&2; exit 1; }

# .env is read and written line by line (never sourced, so special characters in values are safe)
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true; }
env_set() {
  local key=$1 val=$2 tmp
  tmp=$(mktemp)
  awk -v k="$key" -v v="$val" 'BEGIN{done=0} $0 ~ "^"k"=" {print k"="v; done=1; next} {print} END{if(!done) print k"="v}' .env >"$tmp"
  cat "$tmp" >.env && rm -f "$tmp"
}
rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1" || true; }

lan_ip() {
  local ip=""
  if [[ "$(uname)" == "Darwin" ]]; then
    for i in en0 en1 en2; do ip=$(ipconfig getifaddr "$i" 2>/dev/null || true); [[ -n "$ip" ]] && break; done
  else
    ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)
    [[ -z "$ip" ]] && ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  echo "${ip:-127.0.0.1}"
}

public_ip() {
  local ip=""
  for u in https://api.ipify.org https://ifconfig.me https://ipv4.icanhazip.com; do
    ip=$(curl -fs4 --max-time 5 "$u" 2>/dev/null | tr -d '[:space:]') && [[ "$ip" =~ ^[0-9.]+$ ]] && break
    ip=""
  done
  echo "$ip"
}

compose() { docker compose "$@"; }

preflight() {
  command -v docker >/dev/null || die "Docker is not installed. Install Docker Desktop (Mac/Windows) or Docker Engine (Linux) first."
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (the 'docker compose' command)."
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker first."
}

prepare_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    info "Created .env from .env.example"
    if [[ -t 0 ]]; then   # first run in a terminal: ask the two questions that matter
      echo
      echo -e "${C_B}Where will Hudd run?${C_0}"
      echo "  - On a server with a domain name: type the domain (its DNS A record must point to this server)"
      echo "  - On this computer or your local network: just press Enter"
      read -r -p "Domain name: " d
      d=$(echo "$d" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]' | sed -E 's#^https?://##; s#/.*$##')
      if [[ -n "$d" ]]; then
        env_set DOMAIN "$d"
        if [[ -z "${NATIVE:-}" ]]; then
          read -r -p "Email for HTTPS certificate notices (Let's Encrypt): " em
          env_set ACME_EMAIL "$(echo "$em" | tr -d '[:space:]')"
        fi
        read -r -p "Passcode to start meetings (Enter = anyone can start meetings): " pc
        env_set CREATE_PASSCODE "$pc"
      fi
      echo
    fi
  fi

  local domain; domain=$(env_get DOMAIN)
  if [[ -n "$domain" ]]; then
    # ---------- public mode (server + domain) ----------
    if [[ "$(env_get REVERSE_PROXY)" == "host" ]]; then
      # Your own Nginx/Caddy already uses 80/443: listen on 127.0.0.1 only and let it forward to us
      env_set CADDYFILE Caddyfile.proxy
      env_set HTTP_BIND 127.0.0.1; env_set HTTPS_BIND 127.0.0.1
      case "$(env_get HTTP_PORT)" in ""|80|8080) env_set HTTP_PORT 18080 ;; esac
      case "$(env_get HTTPS_PORT)" in ""|443|8443) env_set HTTPS_PORT 18443 ;; esac
    else
      env_set CADDYFILE Caddyfile.domain
      # (Without Docker your own Caddy or Nginx handles certificates, so the email is not needed here)
      [[ -n "${NATIVE:-}" || "$(env_get ACME_EMAIL)" == *@*.* ]] || die "With DOMAIN set, ACME_EMAIL must be an email address (for Let's Encrypt). Edit .env and run ./deploy.sh again."
      env_set HTTP_BIND 0.0.0.0; env_set HTTPS_BIND 0.0.0.0
      case "$(env_get HTTP_PORT)" in ""|8080|18080) env_set HTTP_PORT 80 ;; esac
      case "$(env_get HTTPS_PORT)" in ""|8443|18443) env_set HTTPS_PORT 443 ;; esac
    fi
    if [[ -z "$(env_get PUBLIC_HOST)" ]]; then
      local pip; pip=$(public_ip)
      if [[ -n "$pip" ]]; then env_set PUBLIC_HOST "$pip"; info "Public IP: $pip"
      else warn "Could not detect this server's public IP. Set PUBLIC_HOST in .env to it, or video will not connect."; fi
    fi
    local resolved; resolved=$(getent ahostsv4 "$domain" 2>/dev/null | awk 'NR==1{print $1}' || true)
    if [[ -z "$resolved" ]]; then
      warn "$domain does not resolve yet. Add a DNS A record pointing to this server, or the certificate cannot be issued."
    elif [[ -n "$(env_get PUBLIC_HOST)" && "$resolved" != "$(env_get PUBLIC_HOST)" ]]; then
      warn "$domain points to $resolved, but this server's public IP is $(env_get PUBLIC_HOST). If you use a CDN or proxy, turn it off for this name (media needs a direct connection)."
    fi
    [[ -z "$(env_get CREATE_PASSCODE)" ]] && info "Anyone who opens your site can start meetings. To restrict that, set CREATE_PASSCODE in .env."
  else
    # ---------- local / LAN mode ----------
    env_set CADDYFILE Caddyfile
    env_set HTTP_BIND 0.0.0.0; env_set HTTPS_BIND 0.0.0.0
  fi
  [[ -z "$(env_get LIVEKIT_API_KEY)" ]] && env_set LIVEKIT_API_KEY "API$(rand 12)"
  [[ -z "$(env_get LIVEKIT_API_SECRET)" ]] && env_set LIVEKIT_API_SECRET "$(rand 40)"
  [[ -z "$(env_get SECRET_KEY)" ]] && env_set SECRET_KEY "$(rand 48)"
  if [[ -z "$(env_get PUBLIC_HOST)" ]]; then
    env_set PUBLIC_HOST "$(lan_ip)"
    info "This machine's IP: $(env_get PUBLIC_HOST) (change PUBLIC_HOST in .env if it is wrong)"
  fi
  return 0
}

render_livekit_config() {
  local tpl=config/livekit.yaml.tpl out=config/livekit.yaml content
  content=$(cat "$tpl")
  for k in PUBLIC_HOST LIVEKIT_API_KEY LIVEKIT_API_SECRET LIVEKIT_TCP_PORT LIVEKIT_UDP_PORT ROOM_EMPTY_TIMEOUT ROOM_DEPARTURE_TIMEOUT; do
    local v; v=$(env_get "$k")
    case $k in
      LIVEKIT_TCP_PORT) v=${v:-7881};; LIVEKIT_UDP_PORT) v=${v:-7882};;
      ROOM_EMPTY_TIMEOUT) v=${v:-1800};; ROOM_DEPARTURE_TIMEOUT) v=${v:-120};;
    esac
    content=${content//\$\{$k\}/$v}
  done
  printf '%s\n' "$content" >"$out"
}

wait_healthy() {
  info "Waiting for the services…"
  for _ in $(seq 1 60); do
    if compose exec -T web python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')" >/dev/null 2>&1; then
      local domain; domain=$(env_get DOMAIN)
      if [[ -n "$domain" && "$(env_get REVERSE_PROXY)" != "host" ]]; then
        info "Checking https://$domain (the first certificate can take about 30 seconds)…"
        local up=
        for _ in $(seq 1 30); do
          curl -fs --max-time 5 "https://$domain/healthz" >/dev/null 2>&1 && { up=1; break; }
          sleep 3
        done
        [[ -n "$up" ]] || warn "https://$domain is not reachable yet. Check the DNS record and that ports 80/443 are open; ./deploy.sh logs caddy shows the certificate log."
      fi
      return 0
    fi
    sleep 2
  done
  warn "The services did not become ready within 120 seconds. Run ./deploy.sh logs to see why."
  return 1
}

summary() {
  local host http https
  host=$(env_get PUBLIC_HOST); http=$(env_get HTTP_PORT); https=$(env_get HTTPS_PORT)
  echo
  echo -e "${C_B}Hudd $(cat VERSION 2>/dev/null) is running${C_0}"
  if [[ -n "$(env_get DOMAIN)" && "$(env_get REVERSE_PROXY)" == "host" ]]; then
    echo -e "  Address      : ${C_G}https://$(env_get DOMAIN)/${C_0}  (through your own web server)"
    echo -e "  Internal port: 127.0.0.1:${http} (this machine only)"
    echo -e "  Caddy on the host needs:   ${C_Y}$(env_get DOMAIN) { reverse_proxy 127.0.0.1:${http} }${C_0}"
    echo -e "  Nginx: proxy_pass http://127.0.0.1:${http}; with WebSocket upgrade headers (see the README)"
    echo -e "  Open ports   : TCP $(env_get LIVEKIT_TCP_PORT), UDP $(env_get LIVEKIT_UDP_PORT)"
  elif [[ -n "$(env_get DOMAIN)" ]]; then
    echo -e "  Address      : ${C_G}https://$(env_get DOMAIN)/${C_0}"
    echo -e "  Open ports   : TCP 80, 443, $(env_get LIVEKIT_TCP_PORT), UDP $(env_get LIVEKIT_UDP_PORT)"
  else
    echo -e "  This computer: ${C_G}http://localhost:${http:-8080}${C_0}"
    echo -e "  Your network : ${C_G}https://${host}:${https:-8443}${C_0}  (self-signed certificate: choose \"continue\" the first time)"
    echo -e "  Open ports   : TCP ${http:-8080}, ${https:-8443}, $(env_get LIVEKIT_TCP_PORT), UDP $(env_get LIVEKIT_UDP_PORT)"
  fi
  echo -e "  Logs         : ./deploy.sh logs"
  echo
}

cmd=${1:-up}
case "$cmd" in
  up)
    preflight; prepare_env; render_livekit_config
    info "Building and starting the containers…"
    compose up -d --build --remove-orphans
    wait_healthy && summary
    ;;
  restart)
    preflight; prepare_env; render_livekit_config
    compose up -d --force-recreate --remove-orphans
    wait_healthy && summary
    ;;
  config)   # without Docker: settings and LiveKit config only
    NATIVE=1 prepare_env; render_livekit_config
    info "Wrote .env and config/livekit.yaml. Next steps: docs/install-from-source.md"
    ;;
  down) compose down ;;
  status) compose ps ;;
  logs) shift; compose logs -f --tail=200 "$@" ;;
  update)
    git pull --ff-only
    exec "$0" up
    ;;
  *) die "Unknown command: $cmd (use: up | status | logs | restart | down | update | config)" ;;
esac
