# Contributing to Hudd

Thanks for helping! Hudd is small on purpose: a browser meeting app with no accounts and no database. Changes that keep it simple and easy to self-host are the easiest to accept.

## Ways to help

- **Report a bug**: open an issue with the steps, your browser and device, and what you expected to happen.
- **Fix or add a translation**: all interface text is in [`web/static/js/i18n.js`](web/static/js/i18n.js), one block per language, and the server messages are in [`web/app/i18n.py`](web/app/i18n.py). `tests/test_i18n.py` checks that every language has the same keys and placeholders.
- **Improve the docs**: the README is in 13 languages under [`docs/i18n/`](docs/i18n/); install guides are in [`docs/`](docs/).
- **Code**: look for issues labelled [`good first issue`](https://github.com/AldrichWorld/hudd/labels/good%20first%20issue). For a bigger change, open an issue first so we can agree on the approach.

## Development

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

The tests start a real LiveKit server and the web service, then drive two browsers through a whole meeting. Please make sure they pass before opening a pull request, and add a check when you add a feature.

## Pull requests

- Keep each pull request to one change, and describe what it does and how you tested it.
- Match the existing style: plain JavaScript (no framework), FastAPI on the server, no new runtime dependencies without discussion.
- Any user-visible text goes into `i18n.js` for **all 13 languages**. If you can't translate, copy the English text and say so in the pull request; someone will translate it.
- By contributing you agree that your work is released under the [MIT license](LICENSE).
