[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · **Português** · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**Videochamadas gratuitas que rodam no navegador.** Nada para instalar, sem contas, sem limite de tempo e sem banco de dados.
Rode a sua com um único comando.

> **Só quer fazer uma reunião?** O [hudd.live](https://hudd.live) é o serviço hospedado construído sobre o Hudd: nada para configurar, com extras como notas de reunião com IA, fundos virtuais e efeitos na tela.

## Recursos

- Reuniões de áudio e vídeo em qualquer navegador moderno, em computadores e celulares
- Compartilhamento de tela ajustado para texto nítido
- Chat na reunião, com @menções
- Layouts de grade e de orador, fixar e tela cheia
- Senhas de reunião
- Controles do anfitrião: silenciar todos, silenciar uma pessoa, pedir para alguém ativar o microfone, encerrar a reunião para todos
- 13 idiomas de interface: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- Instalável como aplicativo (PWA) em computadores e celulares
- Nada é armazenado: sem banco de dados, sem contas, e as mensagens do chat nunca são salvas

## Início rápido

Você precisa do [Docker](https://docs.docker.com/get-docker/) com Docker Compose.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

O script faz uma única pergunta: o seu domínio.

- **Em um servidor com domínio:** aponte o registro DNS A do domínio para o servidor, libere TCP 80, 443, 7881 e UDP 7882 e digite o domínio quando for perguntado. O Hudd obtém um certificado HTTPS gratuito e roda em `https://seu-dominio`.
- **No seu computador ou na rede local:** apenas pressione Enter. O Hudd roda em `http://localhost:8080`, e outros aparelhos da rede podem usar `https://<IP deste computador>:8443` (certificado autoassinado).

Outros comandos: `./deploy.sh status`, `./deploy.sh logs`, `./deploy.sh restart` (depois de editar o `.env`), `./deploy.sh update`, `./deploy.sh down`.

### Sem Docker

Você também pode compilar e rodar o Hudd a partir do código-fonte: baixar o código, compilar o front-end, criar um ambiente Python e rodar o LiveKit e o serviço web com systemd atrás do Caddy ou do Nginx. O guia passo a passo (em inglês) está em [Instalar a partir do código-fonte](../../docs/install-from-source.md). Para testar antes no seu computador:

```bash
git clone https://github.com/AldrichWorld/hudd.git && cd hudd
(cd web/vendor-src && npm ci && sh build.sh ../static/vendor)
python3 -m venv .venv && .venv/bin/pip install -r web/requirements.txt
livekit-server --dev --bind 127.0.0.1 &
cd web && LIVEKIT_PUBLIC_URL=ws://localhost:7880 ../.venv/bin/uvicorn app.main:app --port 8000
```

Depois abra `http://localhost:8000` (requer Node.js, Python 3.11+ e [livekit-server](https://docs.livekit.io/home/self-hosting/local/)).

## Configurações

Todas as configurações ficam no `.env` (criado na primeira execução a partir do `.env.example`). As que você mais deve mudar:

| Configuração | O que faz |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | Modo público com HTTPS automático. Deixe `DOMAIN` vazio para o modo local |
| `CREATE_PASSCODE` | Só quem conhece este código pode iniciar reuniões. Entrar por link nunca precisa dele |
| `REVERSE_PROXY=host` | Seu Nginx ou Caddy já usa as portas 80/443 (veja abaixo) |
| `PUBLIC_HOST` | O IP desta máquina para o tráfego de áudio e vídeo. Detectado automaticamente |
| `ROOM_EMPTY_TIMEOUT` | Quanto tempo uma reunião nova espera pela primeira pessoa (segundos, padrão 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | Limites contra abuso por IP de visitante (0 = sem limite) |
| `APP_NAME`, `SOURCE_URL` | O nome exibido nas páginas e o link para o código-fonte no rodapé |

Execute `./deploy.sh restart` depois de alterar o `.env`.

### Atrás do seu próprio servidor web

Se o Nginx ou o Caddy da máquina já usa as portas 80 e 443, defina `REVERSE_PROXY=host` no `.env`. O Hudd passa a escutar só em `127.0.0.1:18080`, e o seu servidor web encaminha o domínio para ele, incluindo WebSockets:

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

Com o Caddy é uma linha: `seu-dominio { reverse_proxy 127.0.0.1:18080 }`. Áudio e vídeo continuam precisando de TCP 7881 e UDP 7882 liberados.

## Como funciona

O `docker-compose.yml` inicia três contêineres:

- **LiveKit** (servidor de mídia): transporta áudio, vídeo e compartilhamento de tela.
- **web** (Python, FastAPI): as páginas e uma pequena API para criar e entrar em reuniões.
- **Caddy** HTTPS e um único endereço para as páginas e o LiveKit.

Não há banco de dados. Uma reunião existe exatamente enquanto a sala do LiveKit existir; os metadados da sala guardam o tópico, o nome do anfitrião e um hash com chave da senha. As permissões do anfitrião vêm de uma chave assinada, então reiniciar o serviço web não interrompe nada. As mensagens do chat vão direto entre os participantes e nunca são armazenadas.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## Desenvolvimento e testes

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## Traduções

Todo o texto da interface está em [`web/static/js/i18n.js`](../../web/static/js/i18n.js), um bloco por idioma. Para corrigir uma tradução ou adicionar um idioma, edite esse arquivo e abra um pull request; o `tests/test_i18n.py` confere se todos os idiomas têm as mesmas chaves e marcadores.

## Licença

[MIT](../../LICENSE). Componentes de terceiros e suas licenças estão em [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt).

O Hudd é o núcleo de código aberto do [hudd.live](https://hudd.live). Issues e pull requests são bem-vindos.
