"""Home page, phones and PWA:
1 the home page in all 13 languages: text filled in, right-to-left for Arabic and Persian, nothing missing
2 desktop shows all 8 features without scrolling; phones and tablets have no sideways scroll
3 join box: a bad ID shows a notice; an invite link with ?pwd= opens the meeting and fills in the password
4 the meeting page on a phone: all control buttons on screen
5 PWA: manifest, service worker, install button
6 footer links to the source code"""
import asyncio
import json
import os
import httpx
from playwright.async_api import async_playwright

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
SHOTS = os.getenv("SHOTS_DIR")
LANGS = ["en", "es", "fr", "pt", "de", "ru", "uk", "ar", "fa", "ja", "ko", "zh-CN", "zh-TW"]
ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]


async def main():
    async with async_playwright() as pw, httpx.AsyncClient() as http:
        b = await pw.chromium.launch(args=ARGS)
        errors = []

        # 1
        p = await (await b.new_context(viewport={"width": 1280, "height": 800})).new_page()
        p.on("pageerror", lambda e: errors.append(str(e)))
        for lang in LANGS:
            await p.goto(f"{BASE}/?lang={lang}")
            r = await p.evaluate("""() => ({ lang: document.documentElement.lang, dir: document.dir,
                empty: [...document.querySelectorAll('[data-i18n],[data-i18n-html]')].filter(e => !e.textContent.trim() && !e.closest('.hidden')).map(e => e.dataset.i18n || e.dataset.i18nHtml),
                ph: document.getElementById('jCode').placeholder, h1: document.querySelector('h1').textContent })""")
            assert r["lang"] == lang and r["dir"] == ("rtl" if lang in ("ar", "fa") else "ltr") and not r["empty"] and r["ph"] and r["h1"], (lang, r)
            if lang != "en":
                assert r["h1"] != "Connect with people anywhere in the world.All you need is a browser.", lang
            if SHOTS and lang in ("en", "ar", "zh-CN"): await p.screenshot(path=f"{SHOTS}/home_{lang}.png")
        await p.goto(f"{BASE}/"); assert await p.evaluate("document.documentElement.lang") == "zh-TW"   # last choice is remembered
        await p.goto(f"{BASE}/?lang=en")
        print("1 home page filled in all 13 languages (Arabic and Persian right to left); the choice is remembered")

        # 2
        for w, h in ((1280, 800), (1440, 900), (1366, 650)):
            await p.set_viewport_size({"width": w, "height": h}); await p.goto(f"{BASE}/")
            bottom = await p.evaluate("Math.max(...[...document.querySelectorAll('#feats .feat')].map(e => e.getBoundingClientRect().bottom))")
            assert await p.locator("#feats .feat").count() == 8 and bottom <= h, (w, h, bottom)
        for w, h in ((390, 844), (820, 1180), (360, 740)):
            c = await b.new_context(viewport={"width": w, "height": h}, is_mobile=w < 500, has_touch=True)
            q = await c.new_page(); await q.goto(f"{BASE}/?lang=en")
            assert await q.evaluate("document.documentElement.scrollWidth") <= w and await q.is_visible("#newBtn") and await q.is_visible("#jCode"), w
            if SHOTS and w == 390: await q.screenshot(path=f"{SHOTS}/home_phone.png", full_page=True)
            await c.close()
        print("2 desktop shows all 8 features without scrolling; no sideways scroll on phones and tablets")

        # 3
        d = (await http.post(f"{BASE}/api/rooms", json={"nickname": "Host", "room_pass": "k9"})).json()
        code, key = d["room"]["code"], d["owner_key"]
        await p.set_viewport_size({"width": 1280, "height": 800}); await p.goto(f"{BASE}/")
        await p.fill("#jCode", "12345"); await p.click("#joinBtn")
        assert "9 digits" in await p.inner_text("#jErr")
        await p.fill("#jCode", f"{BASE}/r/{code}?pwd=k9"); await p.click("#joinBtn"); await p.wait_for_url(f"**/r/{code}")
        await p.wait_for_selector("#prejoin:not(.hidden)")
        assert await p.input_value("#pjPass") == "k9" and "pwd=" not in p.url
        await p.goto(f"{BASE}/r/{code}?pwd=k9"); await p.wait_for_selector("#prejoin:not(.hidden)")
        assert await p.input_value("#pjPass") == "k9" and "pwd=" not in p.url   # the password leaves the address bar
        print("3 bad ID notice; invite link with ?pwd= opens the meeting with the password filled in (and removed from the address bar)")

        # 4
        c = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, permissions=["camera", "microphone"])
        q = await c.new_page(); q.on("pageerror", lambda e: errors.append(str(e)))
        await q.goto(f"{BASE}/r/{code}?pwd=k9&lang=en"); await q.wait_for_selector("#prejoin:not(.hidden)")
        await q.fill("#pjNick", "Phone"); await q.click("#pjBtn"); await q.wait_for_selector("#meeting:not(.hidden)")
        boxes = await q.evaluate("[...document.querySelectorAll('.m-ctrl .cbtn')].filter(b => b.offsetParent).map(b => { const r = b.getBoundingClientRect(); return [b.id, r.left, r.right, r.bottom]; })")
        assert all(l >= 0 and r <= 390 and bt <= 844 for _, l, r, bt in boxes) and "cLeave" in [x[0] for x in boxes], boxes
        assert await q.evaluate("document.documentElement.scrollWidth") <= 390
        await q.click("#cPanel"); await q.wait_for_selector("#chatInput", state="visible")
        if SHOTS: await q.screenshot(path=f"{SHOTS}/meeting_phone.png")
        await c.close()
        await http.post(f"{BASE}/api/rooms/{code}/end", json={"owner_key": key})
        print("4 meeting page on a phone: every control button is on screen; the panel opens with chat")

        # 5
        m = (await http.get(f"{BASE}/manifest.webmanifest")).json()
        assert m["name"] == "Hudd" and m["display"] == "standalone" and len(m["icons"]) == 3
        for ic in m["icons"]:
            assert (await http.get(BASE + ic["src"])).status_code == 200
        sw = await http.get(f"{BASE}/sw.js"); assert sw.status_code == 200 and "javascript" in sw.headers["content-type"]
        await p.goto(f"{BASE}/"); await p.wait_for_function("navigator.serviceWorker.getRegistration().then(r => !!r)", timeout=10000)
        print("5 PWA: manifest with icons, service worker registered")

        # 6
        assert await p.get_attribute("#srcLink", "href") == "https://github.com/AldrichWorld/hudd"
        assert (await http.get(f"{BASE}/static/THIRD-PARTY-NOTICES.txt")).status_code == 200
        print("6 footer links to the source code and the third-party notices")
        assert not errors, errors
        await b.close()
    print("HOME OK")

asyncio.run(main())
