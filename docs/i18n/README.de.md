[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · **Deutsch** · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**Kostenlose Videomeetings, die im Browser laufen.** Keine Installation, keine Konten, kein Zeitlimit und keine Datenbank.
Mit einem Befehl auf deinem eigenen Server.

## Funktionen

- Audio- und Videomeetings in jedem aktuellen Browser, auf Computern und Smartphones
- Bildschirmfreigabe, abgestimmt auf gut lesbaren Text
- Chat im Meeting, mit @Erwähnungen
- Kachel- und Sprecheransicht, Anheften und Vollbild
- Meeting-Passwörter
- Gastgeber-Funktionen: alle stummschalten, eine Person stummschalten, jemanden bitten, das Mikrofon einzuschalten, das Meeting für alle beenden
- 13 Oberflächensprachen: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- Als App installierbar (PWA) auf Computern und Smartphones
- Nichts wird gespeichert: keine Datenbank, keine Konten, Chatnachrichten werden nie gesichert

## Schnellstart

Du brauchst [Docker](https://docs.docker.com/get-docker/) mit Docker Compose.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

Das Skript stellt nur eine Frage: deinen Domainnamen.

- **Auf einem Server mit Domain:** Richte den DNS-A-Eintrag der Domain auf den Server, öffne TCP 80, 443, 7881 und UDP 7882 und gib die Domain ein, wenn danach gefragt wird. Hudd holt sich ein kostenloses HTTPS-Zertifikat und läuft unter `https://deine-domain`.
- **Auf deinem eigenen Computer oder im lokalen Netzwerk:** Drücke einfach Enter. Hudd läuft unter `http://localhost:8080`, andere Geräte im Netzwerk nutzen `https://<IP dieses Computers>:8443` (selbstsigniertes Zertifikat).

Weitere Befehle: `./deploy.sh status`, `./deploy.sh logs`, `./deploy.sh restart` (nach Änderungen an `.env`), `./deploy.sh update`, `./deploy.sh down`.

### Ohne Docker

Du kannst Hudd auch aus dem Quellcode bauen und betreiben: Code holen, Frontend bauen, Python-Umgebung einrichten und LiveKit sowie den Webdienst mit systemd hinter Caddy oder Nginx laufen lassen. Die Schritt-für-Schritt-Anleitung (auf Englisch) steht unter [Installation aus dem Quellcode](../../docs/install-from-source.md). Zum Ausprobieren auf dem eigenen Rechner:

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

Dann `http://localhost:8000` öffnen (benötigt Node.js, Python 3.11+ und [livekit-server](https://docs.livekit.io/home/self-hosting/local/)).

## Einstellungen

Alle Einstellungen stehen in `.env` (beim ersten Start aus `.env.example` erzeugt). Die am häufigsten geänderten:

| Einstellung | Wirkung |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | Öffentlicher Modus mit automatischem HTTPS. `DOMAIN` leer lassen für den lokalen Modus |
| `CREATE_PASSCODE` | Nur wer diesen Code kennt, kann Meetings starten. Für die Teilnahme per Link wird er nie gebraucht |
| `REVERSE_PROXY=host` | Dein eigenes Nginx oder Caddy nutzt bereits die Ports 80/443 (siehe unten) |
| `PUBLIC_HOST` | Die IP-Adresse dieses Rechners für Audio und Video. Wird automatisch erkannt |
| `ROOM_EMPTY_TIMEOUT` | Wie lange ein neues Meeting auf die erste Person wartet (Sekunden, Standard 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | Missbrauchsgrenzen pro Besucher-IP (0 = keine Grenze) |
| `APP_NAME`, `SOURCE_URL` | Der Name auf den Seiten und der Link zum Quellcode in der Fußzeile |

Nach Änderungen an `.env` `./deploy.sh restart` ausführen.

### Hinter deinem eigenen Webserver

Wenn Nginx oder Caddy auf dem Server die Ports 80 und 443 schon belegt, setze `REVERSE_PROXY=host` in `.env`. Hudd lauscht dann nur auf `127.0.0.1:18080`, und dein Webserver leitet die Domain dorthin weiter, inklusive WebSockets:

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

Mit Caddy ist es eine Zeile: `deine-domain { reverse_proxy 127.0.0.1:18080 }`. Für Audio und Video müssen TCP 7881 und UDP 7882 weiterhin offen sein.

## So funktioniert es

`docker-compose.yml` startet drei Container:

- **LiveKit** (Medienserver): überträgt Audio, Video und Bildschirmfreigabe.
- **web** (Python, FastAPI): die Seiten und eine kleine API zum Anlegen von und Teilnehmen an Meetings.
- **Caddy** HTTPS und eine gemeinsame Adresse für die Seiten und LiveKit.

Es gibt keine Datenbank. Ein Meeting existiert genau so lange wie sein LiveKit-Raum; die Metadaten des Raums enthalten das Thema, den Namen des Gastgebers und einen schlüsselbasierten Hash des Passworts. Die Rechte des Gastgebers stammen aus einem signierten Schlüssel, daher unterbricht ein Neustart des Webdienstes nichts. Chatnachrichten gehen direkt zwischen den Teilnehmenden und werden nie gespeichert.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## Entwicklung und Tests

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## Übersetzungen

Alle Texte der Oberfläche stehen in [`web/static/js/i18n.js`](../../web/static/js/i18n.js), ein Block pro Sprache. Um eine Übersetzung zu verbessern oder eine Sprache hinzuzufügen, bearbeite diese Datei und öffne einen Pull Request; `tests/test_i18n.py` prüft, dass alle Sprachen dieselben Schlüssel und Platzhalter haben.

## Lizenz

[MIT](../../LICENSE). Komponenten von Drittanbietern und ihre Lizenzen stehen in [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt).

Hudd ist der Open-Source-Kern von [hudd.live](https://hudd.live).
