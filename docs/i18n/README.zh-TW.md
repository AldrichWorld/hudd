[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · **繁體中文**

# Hudd

**在瀏覽器裡直接使用的免費視訊會議。** 免安裝、免註冊、不限時長，也沒有資料庫。
一條指令就能部署你自己的會議系統。

> **只想開個會？** [hudd.live](https://hudd.live) 是基於 Hudd 的線上服務：不用部署，打開就能用，另有 AI 會議記錄、虛擬背景、螢幕特效等功能。

## 功能

- 電腦和手機上的主流瀏覽器都能開影音會議
- 螢幕分享，針對文字清晰度做了最佳化
- 會議內聊天，支援 @ 提及
- 格狀和講者版面，可釘選、可全螢幕
- 會議密碼
- 主持人控制：全部靜音、將某人靜音、請某人開麥克風、為所有人結束會議
- 13 種介面語言: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- 可以安裝成電腦和手機上的應用程式（PWA）
- 不儲存任何資料：沒有資料庫、沒有帳號，聊天訊息從不儲存

## 快速開始

需要安裝 [Docker](https://docs.docker.com/get-docker/)（含 Docker Compose）。

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

腳本只問一個問題：你的網域名稱。

- **在有網域的伺服器上：** 先把網域的 DNS A 記錄指向伺服器，開放 TCP 80、443、7881 和 UDP 7882，然後在提示時輸入網域。Hudd 會自動申請免費的 HTTPS 憑證，網址是 `https://你的網域`。
- **在自己的電腦或區域網路裡：** 直接按 Enter。本機開啟 `http://localhost:8080`，區域網路裡的其他裝置開啟 `https://<這台電腦的 IP>:8443`（自簽憑證）。

其他指令：`./deploy.sh status`、`./deploy.sh logs`、`./deploy.sh restart`（修改 `.env` 後）、`./deploy.sh update`、`./deploy.sh down`。

### 不用 Docker

也可以從原始碼建置和執行 Hudd：取得程式碼、建置前端、準備 Python 環境，再用 systemd 執行 LiveKit 和網頁服務，前面放 Caddy 或 Nginx。詳細步驟見[從原始碼安裝](../../docs/install-from-source.zh-CN.md)（簡體中文）。想先在自己的電腦上試試：

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

然後開啟 `http://localhost:8000`（需要 Node.js、Python 3.11 以上和 [livekit-server](https://docs.livekit.io/home/self-hosting/local/)）。

## 設定

所有設定都在 `.env` 裡（第一次執行時由 `.env.example` 產生）。最常修改的幾項：

| 設定項 | 作用 |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | 公開模式，自動 HTTPS。`DOMAIN` 留空即本機／區域網路模式 |
| `CREATE_PASSCODE` | 只有知道這個通行碼的人才能發起會議；用連結加入會議永遠不需要 |
| `REVERSE_PROXY=host` | 伺服器上已有 Nginx 或 Caddy 佔用 80/443 連接埠（見下文） |
| `PUBLIC_HOST` | 本機用於傳輸影音的 IP 位址，自動偵測 |
| `ROOM_EMPTY_TIMEOUT` | 新會議等待第一個人進入的時長（秒，預設 1800） |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | 每個訪客 IP 的防濫用限制（0 = 不限制） |
| `APP_NAME`, `SOURCE_URL` | 頁面上顯示的名稱，以及頁尾的原始碼連結 |

修改 `.env` 後執行 `./deploy.sh restart`。

### 放在你自己的網頁伺服器後面

如果伺服器上的 Nginx 或 Caddy 已經佔用了 80 和 443 連接埠，在 `.env` 裡設定 `REVERSE_PROXY=host`。Hudd 就只監聽 `127.0.0.1:18080`，由你的網頁伺服器把網域轉送過來（需要支援 WebSocket）：

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

用 Caddy 只要一行：`你的網域 { reverse_proxy 127.0.0.1:18080 }`。影音仍然需要開放 TCP 7881 和 UDP 7882。

## 運作方式

`docker-compose.yml` 啟動三個容器：

- **LiveKit** （媒體伺服器）：傳輸音訊、視訊和螢幕分享。
- **web** （Python、FastAPI）：網頁，以及建立、加入會議的小型 API。
- **Caddy** HTTPS，並讓網頁和 LiveKit 共用一個網址。

沒有資料庫。會議存在的時間就是它在 LiveKit 裡的房間存在的時間；房間資訊裡保存主題、主持人名字和密碼的帶金鑰雜湊。主持人權限來自簽章的金鑰，所以重新啟動網頁服務不會影響進行中的會議。聊天訊息在與會者之間直接傳送，從不儲存。

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## 開發與測試

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## 翻譯

所有介面文字都在 [`web/static/js/i18n.js`](../../web/static/js/i18n.js) 裡，每種語言一段。修正翻譯或新增語言，修改這個檔案並提交 Pull Request 即可；`tests/test_i18n.py` 會檢查每種語言的鍵和預留位置是否一致。

## 授權

[MIT](../../LICENSE)。第三方元件及其授權見 [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt)。

Hudd 是 [hudd.live](https://hudd.live) 的開源核心。歡迎提交 Issue 和 Pull Request。
