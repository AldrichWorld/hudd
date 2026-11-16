"""Meeting flow in two real browsers (host A, guest B):
1 the host starts a meeting from the home page (topic + password) and lands in it
2 the guest needs the password; then both see each other, the member list shows the host
3 chat between them, with an @mention notification
4 host mutes everyone; asks the guest to unmute, the guest confirms
5 screen sharing: the guest sees the shared screen (speaker view), with the ~1 s receive buffer
6 layout menu (grid / speaker), invite text contains link and password
7 language switch inside the meeting (Arabic, right to left)
8 the host ends the meeting: everyone sees the end screen and the link no longer works"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
        "--auto-select-desktop-capture-source=Entire screen", "--enable-usermedia-screen-capturing"]
PCS = "window.__pcs=[];const _PC=RTCPeerConnection;window.RTCPeerConnection=function(...a){const p=new _PC(...a);__pcs.push(p);return p};RTCPeerConnection.prototype=_PC.prototype;"
TILES = "() => [...document.querySelectorAll('.tile')].map(t => ({ n: t.querySelector('.n').textContent, w: t.querySelector('video').videoWidth, screen: t.classList.contains('screen') }))"


async def until(page, js, timeout=15000):
    await page.wait_for_function(js, timeout=timeout)


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=ARGS)
        errors = []
        async def ctx():
            c = await b.new_context(permissions=["camera", "microphone", "clipboard-read", "clipboard-write"], viewport={"width": 1280, "height": 800})
            await c.add_init_script(PCS + "try{localStorage.setItem('hudd.devicePrefs',JSON.stringify({mic:true,cam:true}))}catch(e){}")
            p = await c.new_page(); p.on("pageerror", lambda e: errors.append(str(e)))
            return p
        a, g = await ctx(), await ctx()

        # 1
        await a.goto(BASE + "/")
        await a.click("#newBtn"); await a.fill("#cNick", "Ana")
        await a.click("#cMore summary"); await a.fill("#cTitle", "Weekly sync"); await a.fill("#cRoomPass", "pw1")
        await a.click("#createBtn"); await a.wait_for_url("**/r/*")
        code = a.url.rsplit("/", 1)[1]
        await a.wait_for_selector("#prejoin:not(.hidden)")
        assert await a.is_hidden("#pjPassWrap") and "Ana" in await a.inner_text("#pjWho")   # host: no password box, joins as herself
        await a.click("#pjBtn"); await a.wait_for_selector("#meeting:not(.hidden)")
        assert await a.inner_text("#mTitle") == "Weekly sync" and "pw1" in await a.inner_text("#mCode"), await a.inner_text("#mCode")
        print("1 host starts a meeting from the home page and is in it:", code)

        # 2
        await g.goto(f"{BASE}/r/{code}")
        await g.wait_for_selector("#prejoin:not(.hidden)"); assert await g.is_visible("#pjPassWrap")
        await g.fill("#pjNick", "Bo"); await g.fill("#pjPass", "wrong"); await g.click("#pjBtn")
        await until(g, "document.getElementById('pjErr').textContent.length > 0")
        await g.fill("#pjPass", "pw1"); await g.click("#pjBtn"); await g.wait_for_selector("#meeting:not(.hidden)")
        await until(g, "[...document.querySelectorAll('.tile video')].filter(v => v.videoWidth > 0).length >= 2")
        await until(a, "[...document.querySelectorAll('.tile video')].filter(v => v.videoWidth > 0).length >= 2")
        assert "Members (2)" in await a.inner_text("#memHead") and "Host" in await g.inner_text("#memberList")
        assert await a.is_visible("#memTools") and await g.is_hidden("#memTools")   # mute tools are for the host only
        print("2 guest needs the password; both see each other; member list shows the host")

        # 3
        await g.fill("#chatInput", "@Ana hello there"); await g.press("#chatInput", "Escape"); await g.click("#chatSend")
        await until(a, "[...document.querySelectorAll('.chat-msg.to-me')].some(m => m.textContent.includes('hello there'))")
        await a.fill("#chatInput", "hi Bo, see https://example.com"); await a.press("#chatInput", "Enter")
        await until(g, "[...document.querySelectorAll('.chat-msg a[href=\"https://example.com\"]')].length === 1")
        print("3 chat both ways, @mention highlighted for the person mentioned, links clickable")

        # 4
        await until(g, "document.getElementById('cMic').classList.contains('off') === false")
        await a.click("#muteAll")
        await until(g, "document.getElementById('cMic').classList.contains('off')")
        await until(a, "document.querySelector('.mic-btn[data-on=\"0\"]') !== null")
        await a.click(".mic-btn[data-on='0']")
        await g.wait_for_selector("#askUnmute:not(.hidden)"); await g.click("#auYes")
        await until(g, "!document.getElementById('cMic').classList.contains('off')")
        print("4 host mutes everyone; asks the guest to unmute and the guest confirms")

        # 5
        await a.click("#cScreen")
        await until(g, "[...document.querySelectorAll('.tile.screen video')].some(v => v.videoWidth > 0)")
        assert await g.is_visible("#speakerView")   # auto layout switches to the speaker view
        bufs = await g.evaluate("__pcs.flatMap(pc => pc.getReceivers()).filter(r => r.track && r.track.kind === 'video').map(r => r.jitterBufferTarget ?? null)")
        assert 1000 in bufs, bufs
        await a.click("#cScreen"); await until(g, "!document.querySelector('.tile.screen')")
        print("5 screen sharing reaches the guest in the speaker view, with a 1 s receive buffer")

        # 6
        await g.click("#mLayout"); await g.check("input[name=lay][value=speaker]")
        await until(g, "!document.getElementById('speakerView').classList.contains('hidden')")
        await g.check("input[name=lay][value=grid]"); await until(g, "!document.getElementById('grid').classList.contains('hidden')")
        await g.click("#mTitle")
        await a.click("#mInvite")
        text = await a.evaluate("navigator.clipboard.readText()")
        assert f"/r/{code}?pwd=pw1" in text and "Weekly sync" in text and "pw1" in text, text
        print("6 layout menu switches grid / speaker; the invite has the link and the password")

        # 7
        await g.select_option("#meeting select.lang-sel", "ar")
        assert await g.evaluate("document.dir") == "rtl" and await g.inner_text("#cLeave") != "Leave"
        await g.select_option("#meeting select.lang-sel", "en")
        print("7 language switch in the meeting (Arabic, right to left)")

        # 8
        await a.click("#cLeave"); await a.click("#lmEnd")
        await a.wait_for_selector("#ended:not(.hidden)"); await g.wait_for_selector("#ended:not(.hidden)", timeout=15000)
        assert "ended" in (await g.inner_text("#edTitle")).lower(), await g.inner_text("#edTitle")
        await g.goto(f"{BASE}/r/{code}"); await g.wait_for_selector("#ended:not(.hidden)")
        assert "ended" in (await g.inner_text("#edTitle")).lower()
        print("8 host ends the meeting: everyone sees the end screen; the link no longer works")
        assert not errors, errors
        await b.close()
    print("MEETING OK")

asyncio.run(main())
