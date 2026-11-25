#!/usr/bin/env bash
# Local end-to-end tests: a real LiveKit server + the Hudd web service, driven by HTTP calls and a headless browser.
# Needs: livekit-server on PATH; Python with web/requirements.txt, httpx and playwright (python -m playwright install chromium).
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd); LOG=$(mktemp -d)
export LIVEKIT_URL=ws://127.0.0.1:7880 LIVEKIT_API_KEY=testkey LIVEKIT_API_SECRET=testsecret_testsecret_testsecret_1234
export LIVEKIT_PUBLIC_URL=ws://127.0.0.1:7880 SECRET_KEY=test-secret NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
export ROOMS_PER_HOUR_PER_IP=0 OPEN_ROOMS_PER_IP=0
[ -f "$ROOT/web/static/vendor/livekit-client.umd.js" ] || sh "$ROOT/web/vendor-src/build.sh" "$ROOT/web/static/vendor"
PIDS=()
cleanup() { kill "${PIDS[@]}" 2>/dev/null || true; echo "logs: $LOG"; }
trap cleanup EXIT
livekit-server --config livekit-test.yaml >"$LOG/livekit.log" 2>&1 & PIDS+=($!)
web() {   # web <port> [ENV=VALUE ...]: another instance of the web service
  local port=$1; shift
  (cd "$ROOT/web" && exec env "$@" uvicorn app.main:app --port "$port" >"$LOG/web-$port.log" 2>&1) & PIDS+=($!)
}
web 8000
web 8001                                                   # same secret: stands in for "the service restarted"
web 8002 CREATE_PASSCODE=letmein ROOMS_PER_HOUR_PER_IP=3   # passcode and rate limit
web 8003 SECRET_KEY=other-secret                           # a different secret: host keys must not work there
for p in 8000 8001 8002 8003; do for i in $(seq 30); do curl -sf "http://127.0.0.1:$p/healthz" >/dev/null && break; sleep 0.5; done; done
python test_api.py
python test_i18n.py
if python -c "import playwright" 2>/dev/null; then
  python test_meeting.py
  python test_home.py
  python test_annotate.py
fi
echo "ALL TESTS PASSED"
