[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · **Українська** · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**Безкоштовні відеозустрічі просто в браузері.** Нічого не треба встановлювати, без акаунтів, без обмеження часу й без бази даних.
Розгорніть власну копію однією командою.

## Можливості

- Аудіо- та відеозустрічі в будь-якому сучасному браузері на комп’ютерах і телефонах
- Демонстрація екрана, налаштована на чіткий текст
- Чат під час зустрічі з @згадками
- Режими сітки та доповідача, закріплення й повноекранний режим
- Паролі для зустрічей
- Керування для організатора: вимкнути мікрофони всім, вимкнути мікрофон одному учаснику, попросити ввімкнути мікрофон, завершити зустріч для всіх
- 13 мов інтерфейсу: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- Встановлюється як застосунок (PWA) на комп’ютери й телефони
- Нічого не зберігається: ні бази даних, ні акаунтів; повідомлення чату не зберігаються

## Швидкий старт

Потрібен [Docker](https://docs.docker.com/get-docker/) із Docker Compose.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

Скрипт ставить лише одне запитання: ваше доменне ім’я.

- **На сервері з доменом:** спрямуйте DNS-запис A домену на сервер, відкрийте TCP 80, 443, 7881 і UDP 7882 та введіть домен, коли скрипт запитає. Hudd отримає безкоштовний HTTPS-сертифікат і працюватиме за адресою `https://ваш-домен`.
- **На власному комп’ютері або в локальній мережі:** просто натисніть Enter. Hudd буде доступний за адресою `http://localhost:8080`, а інші пристрої в мережі зможуть відкрити `https://<IP цього комп’ютера>:8443` (самопідписаний сертифікат).

Інші команди: `./deploy.sh status`, `./deploy.sh logs`, `./deploy.sh restart` (після зміни `.env`), `./deploy.sh update`, `./deploy.sh down`.

### Без Docker

Hudd можна зібрати й запустити з вихідного коду: отримати код, зібрати фронтенд, створити середовище Python і запустити LiveKit та вебсервіс через systemd за Caddy або Nginx. Покрокова інструкція (англійською) — у [Встановлення з вихідного коду](../../docs/install-from-source.md). Щоб спершу спробувати на своєму комп’ютері:

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

Потім відкрийте `http://localhost:8000` (потрібні Node.js, Python 3.11+ і [livekit-server](https://docs.livekit.io/home/self-hosting/local/)).

## Налаштування

Усі налаштування зберігаються в `.env` (створюється під час першого запуску з `.env.example`). Найчастіше змінюють:

| Параметр | Призначення |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | Публічний режим з автоматичним HTTPS. Залиште `DOMAIN` порожнім для локального режиму |
| `CREATE_PASSCODE` | Починати зустрічі можуть лише ті, хто знає цей код. Для входу за посиланням він не потрібен |
| `REVERSE_PROXY=host` | Ваш Nginx або Caddy вже займає порти 80/443 (див. нижче) |
| `PUBLIC_HOST` | IP-адреса цієї машини для передавання звуку й відео. Визначається автоматично |
| `ROOM_EMPTY_TIMEOUT` | Скільки нова зустріч чекає на першого учасника (секунди, типово 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | Обмеження проти зловживань на один IP відвідувача (0 = без обмежень) |
| `APP_NAME`, `SOURCE_URL` | Назва на сторінках і посилання на вихідний код у нижньому колонтитулі |

Після зміни `.env` виконайте `./deploy.sh restart`.

### За вашим власним вебсервером

Якщо Nginx або Caddy на сервері вже займає порти 80 і 443, вкажіть `REVERSE_PROXY=host` у `.env`. Тоді Hudd слухає лише `127.0.0.1:18080`, а ваш вебсервер перенаправляє на нього домен, разом із WebSocket:

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

У Caddy це один рядок: `ваш-домен { reverse_proxy 127.0.0.1:18080 }`. Для звуку й відео, як і раніше, потрібні відкриті TCP 7881 і UDP 7882.

## Як це влаштовано

`docker-compose.yml` запускає три контейнери:

- **LiveKit** (медіасервер): передає звук, відео й демонстрацію екрана.
- **web** (Python, FastAPI): сторінки й невеликий API для створення зустрічей і входу в них.
- **Caddy** HTTPS і єдина адреса для сторінок і LiveKit.

Бази даних немає. Зустріч існує рівно стільки, скільки існує її кімната в LiveKit; у метаданих кімнати зберігаються тема, ім’я організатора й хеш пароля з ключем. Права організатора ґрунтуються на підписаному ключі, тож перезапуск вебсервісу нічого не перериває. Повідомлення чату йдуть напряму між учасниками й ніколи не зберігаються.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## Розробка й тести

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## Переклади

Усі тексти інтерфейсу містяться в [`web/static/js/i18n.js`](../../web/static/js/i18n.js), по блоку на мову. Щоб виправити переклад або додати мову, відредагуйте цей файл і відкрийте pull request; `tests/test_i18n.py` перевіряє, що в усіх мовах однакові ключі й підстановки.

## Ліцензія

[MIT](../../LICENSE). Сторонні компоненти та їхні ліцензії наведено в [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt).

Hudd — відкрите ядро [hudd.live](https://hudd.live).
