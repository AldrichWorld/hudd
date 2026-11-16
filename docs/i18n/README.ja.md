[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · **日本語** · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**ブラウザで動く無料のビデオ会議。** インストール不要、アカウント不要、時間制限なし、データベースもありません。
コマンド 1 つで自分のサーバーに導入できます。

## 機能

- パソコンとスマホの主要ブラウザで音声・ビデオ会議
- 文字が読みやすいように調整した画面共有
- 会議中のチャット（@メンション対応）
- ギャラリー表示とスピーカー表示、ピン留め、全画面
- 会議パスワード
- ホストの操作：全員をミュート、個別にミュート、ミュート解除の依頼、全員の会議を終了
- 13 のインターフェース言語: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- パソコンやスマホにアプリとしてインストール可能（PWA）
- 何も保存しません：データベースもアカウントもなく、チャットも保存されません

## クイックスタート

[Docker](https://docs.docker.com/get-docker/)（Docker Compose を含む）が必要です。

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

スクリプトが尋ねるのはドメイン名だけです。

- **ドメインのあるサーバーの場合：** ドメインの DNS A レコードをサーバーに向け、TCP 80・443・7881 と UDP 7882 を開放してから、聞かれたらドメインを入力します。無料の HTTPS 証明書が自動で取得され、`https://あなたのドメイン` で使えます。
- **自分のパソコンやローカルネットワークの場合：** Enter を押すだけです。このパソコンからは `http://localhost:8080`、同じネットワークの他の端末からは `https://<このパソコンの IP>:8443`（自己署名証明書）で開けます。

その他のコマンド：`./deploy.sh status`、`./deploy.sh logs`、`./deploy.sh restart`（`.env` を変更した後）、`./deploy.sh update`、`./deploy.sh down`。

## 設定

設定はすべて `.env` にあります（初回実行時に `.env.example` から作成）。よく変更するもの：

| 設定 | 内容 |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | 自動 HTTPS の公開モード。`DOMAIN` を空にするとローカルモード |
| `CREATE_PASSCODE` | このパスコードを知っている人だけが会議を開始できます。リンクからの参加には不要です |
| `REVERSE_PROXY=host` | サーバー上の Nginx や Caddy がすでに 80/443 を使っている場合（下記参照） |
| `PUBLIC_HOST` | 音声・映像の通信に使うこのマシンの IP アドレス。自動検出 |
| `ROOM_EMPTY_TIMEOUT` | 新しい会議が最初の参加者を待つ時間（秒、既定値 1800） |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | 訪問者 IP ごとの乱用防止の上限（0 = 制限なし） |
| `APP_NAME`, `SOURCE_URL` | ページに表示する名前と、フッターのソースコードへのリンク |

`.env` を変更したら `./deploy.sh restart` を実行してください。

### 既存の Web サーバーの後ろで動かす

サーバー上の Nginx や Caddy がすでにポート 80 と 443 を使っている場合は、`.env` で `REVERSE_PROXY=host` を設定します。Hudd は `127.0.0.1:18080` だけで待ち受けるので、Web サーバーからドメインを転送してください（WebSocket を含む）：

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

Caddy なら 1 行です：`あなたのドメイン { reverse_proxy 127.0.0.1:18080 }`。映像と音声には引き続き TCP 7881 と UDP 7882 の開放が必要です。

## しくみ

`docker-compose.yml` が 3 つのコンテナを起動します：

- **LiveKit** （メディアサーバー）：音声・映像・画面共有を運びます。
- **web** （Python、FastAPI）：ページと、会議を作成・参加するための小さな API。
- **Caddy** HTTPS と、ページと LiveKit で共通の 1 つのアドレス。

データベースはありません。会議は LiveKit のルームが存在する間だけ存在し、ルームの情報に会議名・ホスト名・パスワードの鍵付きハッシュを保存します。ホストの権限は署名付きの鍵によるもので、Web サービスを再起動しても進行中の会議は中断されません。チャットは参加者間で直接やり取りされ、保存されることはありません。

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## 開発とテスト

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## 翻訳

インターフェースの文言はすべて [`web/static/js/i18n.js`](../../web/static/js/i18n.js) に言語ごとにまとまっています。翻訳の修正や言語の追加は、このファイルを編集してプルリクエストを送ってください。`tests/test_i18n.py` がすべての言語でキーとプレースホルダーが揃っているかを確認します。

## ライセンス

[MIT](../../LICENSE)。サードパーティのコンポーネントとそのライセンスは [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt) にあります。

Hudd は [hudd.live](https://hudd.live) のオープンソースのコアです。
