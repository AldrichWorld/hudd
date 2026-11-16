[English](install-from-source.md) · **简体中文**

# 从源代码安装 Hudd（不用 Docker）

本指南把 Hudd 直接装在 Linux 服务器上，由 systemd 负责保持运行。如果服务器上有 Docker，用 [README](i18n/README.zh-CN.md) 里的 `./deploy.sh` 更简单。

Hudd 本身要运行两个程序，前面再加一个 Web 服务器：

| 程序 | 监听 | 作用 |
|---|---|---|
| LiveKit 服务器 | `127.0.0.1:7880`、TCP `7881`、UDP `7882` | 传输音频、视频和屏幕共享 |
| Hudd Web 服务（Python） | `127.0.0.1:8000` | 网页和创建、加入会议的小型接口 |
| Caddy 或 Nginx | `80`、`443` | HTTPS；把 `/rtc`、`/twirp` 转发给 LiveKit，其余转发给 Hudd |

## 1. 准备

- 一台 Linux 服务器（下面用的是 Debian / Ubuntu 的命令），有公网 IP，域名的 DNS A 记录已指向它
- Python 3.11 及以上、Node.js 18 及以上（只在构建时需要）、git、curl
- 防火墙放行 TCP 80、443、7881 和 UDP 7882；7880 和 8000 不要对外开放

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv nodejs npm
```

## 2. 拉取源代码

```bash
sudo git clone https://github.com/AldrichWorld/hudd.git /opt/hudd
sudo useradd --system --home-dir /opt/hudd --shell /usr/sbin/nologin hudd
sudo chown -R hudd:hudd /opt/hudd
cd /opt/hudd
```

服务以 `hudd` 用户运行，代码放在 `/opt/hudd`。如果换了目录，`config/systemd/` 下两个文件里的路径也要一起改。

## 3. 构建

```bash
# 前端：把 LiveKit 浏览器 SDK 复制到 web/static/vendor（网页不从任何 CDN 加载）
sudo -H -u hudd sh -c 'cd web/vendor-src && npm ci --no-audit --no-fund && sh build.sh ../static/vendor'

# 后端：建一个 Python 虚拟环境，装好 Web 服务的依赖
sudo -H -u hudd python3 -m venv .venv
sudo -H -u hudd .venv/bin/pip install -r web/requirements.txt
```

## 4. 配置

```bash
sudo -H -u hudd ./deploy.sh config
```

它会问你的域名，以及（可选的）发起会议口令，然后生成：

- `.env`：你的配置，以及自动生成的密钥（`LIVEKIT_API_KEY`、`LIVEKIT_API_SECRET`、`SECRET_KEY`）。这个文件不要外泄。
- `config/livekit.yaml`：根据 `.env` 生成的 LiveKit 配置。

确认 `.env` 里的 `PUBLIC_HOST` 是服务器的公网 IP。以后修改 `.env`，再运行一次 `./deploy.sh config`。

## 5. 安装 LiveKit

```bash
curl -sSL https://get.livekit.io | bash     # 安装到 /usr/local/bin/livekit-server
```

其他安装方式见 LiveKit 的[自托管文档](https://docs.livekit.io/home/self-hosting/)。

## 6. 用 systemd 运行两个服务

```bash
sudo cp config/systemd/hudd-livekit.service config/systemd/hudd-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hudd-livekit hudd-web
systemctl status hudd-livekit hudd-web --no-pager
curl -s http://127.0.0.1:8000/healthz      # {"ok":true}
```

## 7. HTTPS 和域名

**Caddy**（自动申请和续期证书）。按 [caddyserver.com/docs/install](https://caddyserver.com/docs/install) 安装后：

```bash
sudo cp config/Caddyfile.native /etc/caddy/Caddyfile
sudo sed -i 's/meet.example.com/你的域名/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

**或者 Nginx** 加 Certbot：

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp config/nginx-hudd.conf /etc/nginx/sites-available/hudd
sudo sed -i 's/meet.example.com/你的域名/' /etc/nginx/sites-available/hudd
sudo ln -s /etc/nginx/sites-available/hudd /etc/nginx/sites-enabled/hudd
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d 你的域名
```

打开 `https://你的域名`，发起一场会议试试。

## 更新

```bash
cd /opt/hudd
sudo -H -u hudd git pull --ff-only
sudo -H -u hudd sh -c 'cd web/vendor-src && npm ci --no-audit --no-fund && sh build.sh ../static/vendor'
sudo -H -u hudd .venv/bin/pip install -r web/requirements.txt
sudo systemctl restart hudd-web
```

重启 `hudd-web` 不会打断正在进行的会议。`hudd-livekit` 只在必要时重启，因为它会结束所有正在进行的会议。

## 在自己的电脑上试用

没有域名也想先看看效果，可以用开发模式运行 LiveKit，再启动 Web 服务：

```bash
livekit-server --dev --bind 127.0.0.1      # 在一个终端里
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000      # 在另一个终端里
```

然后打开 `http://localhost:8000`。开发模式使用固定的测试密钥，只适合在自己的电脑上用。

## 遇到问题

- `journalctl -u hudd-web -u hudd-livekit -f` 可以同时查看两个服务的日志。
- 能进会议但看不到画面：TCP 7881 或 UDP 7882 没放行，或者 `.env` 里的 `PUBLIC_HOST` 不是公网 IP（改好后运行 `./deploy.sh config` 并重启 `hudd-livekit`）。
- 页面能打开但发起不了会议：Web 服务连不上 `127.0.0.1:7880` 的 LiveKit，或者 `.env` 和 `config/livekit.yaml` 里的密钥不一致（`./deploy.sh config` 会根据 `.env` 同时生成两者）。
