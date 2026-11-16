[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **简体中文** · [繁體中文](README.zh-TW.md)

# Hudd

**在浏览器里直接使用的免费视频会议。** 免安装、免注册、不限时长，也没有数据库。
一条命令就能部署你自己的会议系统。

## 功能

- 电脑和手机上的主流浏览器都能开音视频会议
- 屏幕共享，针对文字清晰度做了优化
- 会议内聊天，支持 @ 提及
- 宫格和演讲者布局，可置顶、可全屏
- 会议密码
- 主持人控制：全部静音、静音某人、请某人开麦、为所有人结束会议
- 13 种界面语言: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- 可以安装成电脑和手机上的应用（PWA）
- 不保存任何数据：没有数据库、没有账号，聊天消息从不保存

## 快速开始

需要安装 [Docker](https://docs.docker.com/get-docker/)（含 Docker Compose）。

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

脚本只问一个问题：你的域名。

- **在有域名的服务器上：** 先把域名的 DNS A 记录指向服务器，放行 TCP 80、443、7881 和 UDP 7882，然后在提示时输入域名。Hudd 会自动申请免费的 HTTPS 证书，访问地址是 `https://你的域名`。
- **在自己的电脑或局域网里：** 直接按回车。本机访问 `http://localhost:8080`，局域网里的其他设备访问 `https://<这台电脑的 IP>:8443`（自签证书）。

其他命令：`./deploy.sh status`、`./deploy.sh logs`、`./deploy.sh restart`（修改 `.env` 后）、`./deploy.sh update`、`./deploy.sh down`。

### 不用 Docker

也可以从源代码构建和运行 Hudd：拉取代码、构建前端、准备 Python 环境，再用 systemd 运行 LiveKit 和 Web 服务，前面放 Caddy 或 Nginx。详细步骤见[从源代码安装](../../docs/install-from-source.zh-CN.md)。想先在自己的电脑上试试：

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

然后打开 `http://localhost:8000`（需要 Node.js、Python 3.11 及以上和 [livekit-server](https://docs.livekit.io/home/self-hosting/local/)）。

## 配置

所有配置都在 `.env` 里（第一次运行时由 `.env.example` 生成）。最常改的几项：

| 配置项 | 作用 |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | 公网模式，自动 HTTPS。`DOMAIN` 留空即本机/局域网模式 |
| `CREATE_PASSCODE` | 只有知道这个口令的人才能发起会议；用链接加入会议永远不需要 |
| `REVERSE_PROXY=host` | 服务器上已有 Nginx 或 Caddy 占用 80/443 端口（见下文） |
| `PUBLIC_HOST` | 本机用于传输音视频的 IP 地址，自动探测 |
| `ROOM_EMPTY_TIMEOUT` | 新会议等待第一个人进入的时长（秒，默认 1800） |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | 每个访问者 IP 的防滥用限制（0 = 不限制） |
| `APP_NAME`, `SOURCE_URL` | 页面上显示的名称，以及页脚的源代码链接 |

修改 `.env` 后运行 `./deploy.sh restart`。

### 放在你自己的 Web 服务器后面

如果服务器上的 Nginx 或 Caddy 已经占用了 80 和 443 端口，在 `.env` 里设置 `REVERSE_PROXY=host`。Hudd 就只监听 `127.0.0.1:18080`，由你的 Web 服务器把域名转发过来（需要支持 WebSocket）：

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

用 Caddy 只要一行：`你的域名 { reverse_proxy 127.0.0.1:18080 }`。音视频仍然需要放行 TCP 7881 和 UDP 7882。

## 工作原理

`docker-compose.yml` 启动三个容器：

- **LiveKit** （媒体服务器）：传输音频、视频和屏幕共享。
- **web** （Python、FastAPI）：网页，以及创建、加入会议的小型接口。
- **Caddy** HTTPS，并让网页和 LiveKit 共用一个地址。

没有数据库。会议存在的时间就是它在 LiveKit 里的房间存在的时间；房间信息里保存主题、主持人名字和密码的带密钥哈希。主持人权限来自签名的密钥，所以重启 Web 服务不会影响正在进行的会议。聊天消息在参会者之间直接传送，从不保存。

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## 开发与测试

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## 翻译

所有界面文字都在 [`web/static/js/i18n.js`](../../web/static/js/i18n.js) 里，每种语言一段。修正翻译或增加语言，改这个文件并提交 Pull Request 即可；`tests/test_i18n.py` 会检查每种语言的键和占位符是否一致。

## 许可证

[MIT](../../LICENSE)。第三方组件及其许可证见 [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt)。

Hudd 是 [hudd.live](https://hudd.live) 的开源核心。
