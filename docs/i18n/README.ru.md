[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · **Русский** · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**Бесплатные видеовстречи прямо в браузере.** Ничего не нужно устанавливать, без аккаунтов, без ограничения по времени и без базы данных.
Разверните свою копию одной командой.

> **Нужно просто провести встречу?** [hudd.live](https://hudd.live) — облачный сервис на основе Hudd: ничего не нужно настраивать, а ещё есть ИИ-заметки о встрече, виртуальные фоны и эффекты на экране.

## Возможности

- Аудио- и видеовстречи в любом современном браузере на компьютерах и телефонах
- Демонстрация экрана, настроенная на чёткий текст
- Чат во время встречи с @упоминаниями
- Режимы сетки и докладчика, закрепление и полноэкранный режим
- Пароли для встреч
- Управление для организатора: выключить микрофоны всем, выключить микрофон одному участнику, попросить включить микрофон, завершить встречу для всех
- 13 языков интерфейса: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- Устанавливается как приложение (PWA) на компьютеры и телефоны
- Ничего не хранится: ни базы данных, ни аккаунтов; сообщения чата не сохраняются

## Быстрый старт

Нужен [Docker](https://docs.docker.com/get-docker/) с Docker Compose.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

Скрипт задаёт только один вопрос: ваше доменное имя.

- **На сервере с доменом:** направьте DNS-запись A домена на сервер, откройте TCP 80, 443, 7881 и UDP 7882 и введите домен, когда скрипт спросит. Hudd получит бесплатный HTTPS-сертификат и будет работать по адресу `https://ваш-домен`.
- **На своём компьютере или в локальной сети:** просто нажмите Enter. Hudd будет доступен по адресу `http://localhost:8080`, а другие устройства в сети смогут открыть `https://<IP этого компьютера>:8443` (самоподписанный сертификат).

Другие команды: `./deploy.sh status`, `./deploy.sh logs`, `./deploy.sh restart` (после изменения `.env`), `./deploy.sh update`, `./deploy.sh down`.

### Без Docker

Hudd можно собрать и запустить из исходного кода: получить код, собрать фронтенд, создать окружение Python и запустить LiveKit и веб-сервис через systemd за Caddy или Nginx. Пошаговая инструкция (на английском) — в [Установка из исходного кода](../../docs/install-from-source.md). Чтобы сначала попробовать на своём компьютере:

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

Затем откройте `http://localhost:8000` (нужны Node.js, Python 3.11+ и [livekit-server](https://docs.livekit.io/home/self-hosting/local/)).

## Настройки

Все настройки хранятся в `.env` (создаётся при первом запуске из `.env.example`). Чаще всего меняют:

| Параметр | Назначение |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | Публичный режим с автоматическим HTTPS. Оставьте `DOMAIN` пустым для локального режима |
| `CREATE_PASSCODE` | Начинать встречи могут только те, кто знает этот код. Для входа по ссылке он не нужен |
| `REVERSE_PROXY=host` | Ваш Nginx или Caddy уже занимает порты 80/443 (см. ниже) |
| `PUBLIC_HOST` | IP-адрес этой машины для передачи звука и видео. Определяется автоматически |
| `ROOM_EMPTY_TIMEOUT` | Сколько новая встреча ждёт первого участника (секунды, по умолчанию 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | Ограничения против злоупотреблений на один IP посетителя (0 = без ограничений) |
| `APP_NAME`, `SOURCE_URL` | Название на страницах и ссылка на исходный код в подвале |

После изменения `.env` выполните `./deploy.sh restart`.

### За вашим собственным веб-сервером

Если Nginx или Caddy на сервере уже занимает порты 80 и 443, укажите `REVERSE_PROXY=host` в `.env`. Тогда Hudd слушает только `127.0.0.1:18080`, а ваш веб-сервер перенаправляет на него домен, включая WebSocket:

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

В Caddy это одна строка: `ваш-домен { reverse_proxy 127.0.0.1:18080 }`. Для звука и видео по-прежнему нужны открытые TCP 7881 и UDP 7882.

## Как это устроено

`docker-compose.yml` запускает три контейнера:

- **LiveKit** (медиасервер): передаёт звук, видео и демонстрацию экрана.
- **web** (Python, FastAPI): страницы и небольшой API для создания встреч и входа в них.
- **Caddy** HTTPS и единый адрес для страниц и LiveKit.

Базы данных нет. Встреча существует ровно столько, сколько существует её комната в LiveKit; в метаданных комнаты хранятся тема, имя организатора и хеш пароля с ключом. Права организатора основаны на подписанном ключе, поэтому перезапуск веб-сервиса ничего не прерывает. Сообщения чата идут напрямую между участниками и никогда не сохраняются.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## Разработка и тесты

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## Переводы

Все тексты интерфейса находятся в [`web/static/js/i18n.js`](../../web/static/js/i18n.js), по блоку на язык. Чтобы исправить перевод или добавить язык, отредактируйте этот файл и откройте pull request; `tests/test_i18n.py` проверяет, что во всех языках одинаковые ключи и подстановки.

## Лицензия

[MIT](../../LICENSE). Сторонние компоненты и их лицензии перечислены в [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt).

Hudd — открытое ядро [hudd.live](https://hudd.live). Будем рады issues и pull request’ам.
