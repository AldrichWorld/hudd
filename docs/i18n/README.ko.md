[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · **한국어** · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**브라우저에서 바로 쓰는 무료 화상 회의.** 설치도, 계정도, 시간 제한도, 데이터베이스도 없습니다.
명령어 하나로 내 서버에 설치하세요.

## 기능

- 컴퓨터와 휴대폰의 최신 브라우저에서 음성·화상 회의
- 글자가 선명하도록 조정한 화면 공유
- 회의 중 채팅(@멘션 지원)
- 갤러리 보기와 발표자 보기, 고정과 전체 화면
- 회의 비밀번호
- 호스트 기능: 모두 음소거, 한 사람 음소거, 음소거 해제 요청, 모두에게 회의 종료
- 13개 인터페이스 언어: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- 컴퓨터와 휴대폰에 앱으로 설치 가능(PWA)
- 아무것도 저장하지 않음: 데이터베이스와 계정이 없고, 채팅도 저장되지 않음

## 빠른 시작

[Docker](https://docs.docker.com/get-docker/)(Docker Compose 포함)가 필요합니다.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

스크립트는 도메인 이름 하나만 묻습니다.

- **도메인이 있는 서버:** 도메인의 DNS A 레코드를 서버로 지정하고 TCP 80, 443, 7881과 UDP 7882를 연 다음, 물어보면 도메인을 입력하세요. 무료 HTTPS 인증서가 자동으로 발급되고 `https://내-도메인`에서 실행됩니다.
- **내 컴퓨터나 로컬 네트워크:** Enter만 누르세요. 이 컴퓨터에서는 `http://localhost:8080`, 같은 네트워크의 다른 기기에서는 `https://<이 컴퓨터의 IP>:8443`(자체 서명 인증서)으로 접속합니다.

기타 명령: `./deploy.sh status`, `./deploy.sh logs`, `./deploy.sh restart`(`.env` 수정 후), `./deploy.sh update`, `./deploy.sh down`.

### Docker 없이

소스 코드에서 빌드해 실행할 수도 있습니다. 코드를 받고, 프런트엔드를 빌드하고, Python 환경을 만든 다음, LiveKit과 웹 서비스를 systemd로 Caddy나 Nginx 뒤에서 실행합니다. 단계별 안내(영어)는 [소스에서 설치](../../docs/install-from-source.md)에 있습니다. 먼저 내 컴퓨터에서 써 보려면:

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

그런 다음 `http://localhost:8000`을 여세요(Node.js, Python 3.11 이상, [livekit-server](https://docs.livekit.io/home/self-hosting/local/) 필요).

## 설정

모든 설정은 `.env`에 있습니다(처음 실행할 때 `.env.example`에서 생성). 자주 바꾸는 항목:

| 설정 | 역할 |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | 자동 HTTPS가 적용되는 공개 모드. `DOMAIN`을 비우면 로컬 모드 |
| `CREATE_PASSCODE` | 이 암호를 아는 사람만 회의를 시작할 수 있습니다. 링크로 참여할 때는 필요 없습니다 |
| `REVERSE_PROXY=host` | 서버의 Nginx나 Caddy가 이미 80/443 포트를 쓰는 경우(아래 참고) |
| `PUBLIC_HOST` | 음성·영상 전송에 쓰는 이 컴퓨터의 IP 주소. 자동 감지 |
| `ROOM_EMPTY_TIMEOUT` | 새 회의가 첫 참가자를 기다리는 시간(초, 기본값 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | 방문자 IP별 남용 방지 한도(0 = 제한 없음) |
| `APP_NAME`, `SOURCE_URL` | 페이지에 표시되는 이름과 바닥글의 소스 코드 링크 |

`.env`를 바꾼 뒤에는 `./deploy.sh restart`를 실행하세요.

### 기존 웹 서버 뒤에서 실행하기

서버의 Nginx나 Caddy가 이미 80과 443 포트를 쓰고 있다면 `.env`에 `REVERSE_PROXY=host`를 설정하세요. Hudd는 `127.0.0.1:18080`에서만 대기하고, 웹 서버가 도메인을 여기로 전달합니다(WebSocket 포함):

```nginx
location / {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
}
```

Caddy라면 한 줄입니다: `내-도메인 { reverse_proxy 127.0.0.1:18080 }`. 음성·영상을 위해 TCP 7881과 UDP 7882는 계속 열어 두어야 합니다.

## 동작 방식

`docker-compose.yml`이 컨테이너 세 개를 시작합니다:

- **LiveKit** (미디어 서버): 음성, 영상, 화면 공유를 전달합니다.
- **web** (Python, FastAPI): 페이지와 회의를 만들고 참여하는 작은 API.
- **Caddy** HTTPS, 그리고 페이지와 LiveKit을 위한 하나의 주소.

데이터베이스는 없습니다. 회의는 LiveKit 방이 존재하는 동안만 존재하며, 방 정보에 회의 제목, 호스트 이름, 비밀번호의 키 기반 해시를 담습니다. 호스트 권한은 서명된 키에서 나오므로 웹 서비스를 다시 시작해도 진행 중인 회의는 끊기지 않습니다. 채팅 메시지는 참가자 사이에서 직접 오가며 저장되지 않습니다.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## 개발과 테스트

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## 번역

인터페이스 문구는 모두 [`web/static/js/i18n.js`](../../web/static/js/i18n.js)에 언어별로 모여 있습니다. 번역을 고치거나 언어를 추가하려면 이 파일을 수정해 풀 리퀘스트를 보내 주세요. `tests/test_i18n.py`가 모든 언어의 키와 자리 표시자가 같은지 확인합니다.

## 라이선스

[MIT](../../LICENSE). 서드파티 구성 요소와 라이선스는 [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt)에 있습니다.

Hudd는 [hudd.live](https://hudd.live)의 오픈 소스 핵심입니다.
