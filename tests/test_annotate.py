"""Screen-share annotation (sharer only, single-window shares only), three browsers with different window sizes:
0 the share picker is asked to open on the Window pane; sharing a whole screen (or a tab) offers no Annotate button
1 sharing a window: only the sharer gets the Annotate button and toolbar; viewers can't draw
2 a pen stroke lands on the same spot of the shared picture for viewers with very different windows (wide desktop, tall phone),
  shown about as late as the picture itself (receive buffer)
3 undo removes it; the highlighter fades by itself; the laser pointer disappears when lifted
4 someone who joins mid-share sees the strokes still on screen; stopping the share clears everything"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
        "--auto-select-desktop-capture-source=Entire screen", "--enable-usermedia-screen-capturing"]

# the screen-share tile and the rectangle of the picture inside it (object-fit: contain)
GEOM = """() => { const el = [...document.querySelectorAll('.tile.screen')].find(t => t.querySelector('.anno-layer') && t.offsetParent);
  if (!el) return null; const v = el.querySelector('video'); if (!v.videoWidth) return null;
  const W = el.clientWidth, H = el.clientHeight, s = Math.min(W / v.videoWidth, H / v.videoHeight), cw = v.videoWidth * s, ch = v.videoHeight * s;
  const b = el.getBoundingClientRect(); return { left: b.left + (W - cw) / 2, top: b.top + (H - ch) / 2, w: cw, h: ch, ox: (W - cw) / 2, oy: (H - ch) / 2 }; }"""
# colour of the annotation layer at a point given as a fraction of the picture
PIXEL = """([nx, ny]) => { const el = [...document.querySelectorAll('.tile.screen')].find(t => t.querySelector('.anno-layer') && t.offsetParent);
  const c = el.querySelector('.anno-layer'), v = el.querySelector('video');
  const W = el.clientWidth, H = el.clientHeight, s = Math.min(W / v.videoWidth, H / v.videoHeight), cw = v.videoWidth * s, ch = v.videoHeight * s;
  const k = c.width / W, x = Math.round(((W - cw) / 2 + nx * cw) * k), y = Math.round(((H - ch) / 2 + ny * ch) * k);
  const d = c.getContext('2d').getImageData(x - 1, y - 1, 3, 3).data; let r = 0, g = 0, b = 0, a = 0;
  for (let i = 0; i < d.length; i += 4) { r = Math.max(r, d[i]); g = Math.max(g, d[i + 1]); b = Math.max(b, d[i + 2]); a = Math.max(a, d[i + 3]); }
  return [r, g, b, a]; }"""


async def until(page, js, arg=None, timeout=15000):
    await page.wait_for_function(js, arg=arg, timeout=timeout)


async def pixel(page, nx, ny):
    return await page.evaluate(PIXEL, [nx, ny])


async def wait_pixel(page, nx, ny, test, timeout=8.0):
    px = None
    for _ in range(int(timeout * 10)):
        px = await pixel(page, nx, ny)
        if test(px):
            return px
        await asyncio.sleep(0.1)
    raise AssertionError(f"pixel at {nx},{ny} = {px}")


def red(px): return px[3] > 150 and px[0] > 180 and px[1] < 120
def yellow(px): return px[3] > 40 and px[0] > 150 and px[1] > 120 and px[2] < 100
def empty(px): return px[3] < 20


async def stroke(page, pts, steps=6):
    g = await page.evaluate(GEOM)
    xy = [(g["left"] + x * g["w"], g["top"] + y * g["h"]) for x, y in pts]
    await page.mouse.move(*xy[0]); await page.mouse.down()
    for p in xy[1:]:
        await page.mouse.move(*p, steps=steps)
    await page.mouse.up()


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=ARGS)
        async def page(w, h, **kw):
            c = await b.new_context(permissions=["camera", "microphone"], viewport={"width": w, "height": h}, **kw)
            await c.add_init_script("try{localStorage.setItem('lkm.devicePrefs',JSON.stringify({mic:false,cam:false}));localStorage.setItem('hudd.devicePrefs',JSON.stringify({mic:false,cam:false}))}catch(e){}")
            return await c.new_page()
        a = await page(1280, 800)                 # sharer
        # the test browser can only share a fake "entire screen": record what the page asks the picker for, and let the
        # test decide what the picked surface reports (window.__surface)
        await a.add_init_script("""(() => { const g = navigator.mediaDevices.getDisplayMedia.bind(navigator.mediaDevices);
          navigator.mediaDevices.getDisplayMedia = (o) => { window.__gdm = JSON.stringify(o); return g(o); };
          const gs = MediaStreamTrack.prototype.getSettings;
          MediaStreamTrack.prototype.getSettings = function () { const s = gs.call(this); if (s.displaySurface && window.__surface) s.displaySurface = window.__surface; return s; }; })()""")
        v1 = await page(1600, 900)                # wide desktop viewer
        v2 = await page(390, 844, is_mobile=True, has_touch=True)   # tall phone viewer

        await a.goto(BASE + "/"); await a.click("#newBtn"); await a.fill("#cNick", "Ana")
        await a.click("#createBtn"); await a.wait_for_url("**/r/*"); code = a.url.rsplit("/", 1)[1]
        await a.click("#pjBtn"); await a.wait_for_selector("#meeting:not(.hidden)")
        for p, n in ((v1, "Bo"), (v2, "Cy")):
            await p.goto(f"{BASE}/r/{code}"); await p.fill("#pjNick", n); await p.click("#pjBtn"); await p.wait_for_selector("#meeting:not(.hidden)")

        # 0 whole screen: no Annotate button; the picker was asked to open on windows
        await a.evaluate("window.__surface = 'monitor'")
        await a.click("#cScreen")
        await until(v1, f"({GEOM})() !== null", timeout=20000)
        assert '"displaySurface":"window"' in await a.evaluate("window.__gdm"), await a.evaluate("window.__gdm")
        await asyncio.sleep(1)
        assert await a.locator(".anno-pill").count() == 0, "no Annotate when sharing the whole screen"
        await a.click("#cScreen"); await until(v1, f"({GEOM})() === null")
        print("0 the picker opens on windows; sharing the whole screen offers no Annotate button")

        # 1 share a window: only the sharer gets the Annotate button
        await a.evaluate("window.__surface = 'window'")
        await a.click("#cScreen")
        await until(a, f"({GEOM})() !== null", timeout=20000)
        for p in (v1, v2):
            await until(p, f"({GEOM})() !== null", timeout=20000)
        await a.wait_for_selector(".anno-pill:not(.hidden)")
        assert await v1.locator(".anno-pill").count() == 0 and await v2.locator(".anno-pill").count() == 0
        assert await v1.evaluate("getComputedStyle(document.querySelector('.anno-layer')).pointerEvents") == "none"
        await a.click(".anno-pill"); await a.wait_for_selector(".anno-bar:not(.hidden)")
        assert await a.evaluate("document.querySelector('.anno-bar [data-tool=hl]').classList.contains('on')")   # highlighter first
        print("1 only the sharer has the Annotate button and toolbar; viewers can't draw")

        # 2 pen: same spot on very different windows, shown with the picture's delay
        await a.click(".anno-bar [data-tool=pen]")
        await stroke(a, [(0.30, 0.42), (0.50, 0.42), (0.70, 0.42)])
        await wait_pixel(a, 0.5, 0.42, red, 2)
        g1, g2 = await v1.evaluate(GEOM), await v2.evaluate(GEOM)
        assert abs(g1["w"] / g1["h"] - g2["w"] / g2["h"]) < 0.02 and g1["w"] > 2 * g2["w"], (g1, g2)   # same picture, very different sizes
        early = await pixel(v1, 0.5, 0.42)
        for p in (v1, v2):
            await wait_pixel(p, 0.5, 0.42, red)
            await wait_pixel(p, 0.6, 0.42, red)
            assert empty(await pixel(p, 0.5, 0.55)) and empty(await pixel(p, 0.5, 0.30))   # not shifted up or down
        if os.getenv("SHOTS_DIR"):
            await a.click(".anno-bar [data-tool=hl]"); await stroke(a, [(0.2, 0.6), (0.55, 0.6)]); await asyncio.sleep(1.3)
            for p, n in ((a, "sharer"), (v1, "viewer_wide"), (v2, "viewer_phone")):
                await p.screenshot(path=f"{os.getenv('SHOTS_DIR')}/anno_{n}.png")
            await a.click(".anno-bar [data-act=undo]"); await a.click(".anno-bar [data-tool=pen]")   # take the highlight away again
        print(f"2 pen stroke at the same spot for a {round(g1['w'])}px and a {round(g2['w'])}px wide picture (shown after the receive delay: {'yes' if empty(early) else 'no'})")

        # 3 undo; highlighter fades; laser disappears
        await a.click(".anno-bar [data-act=undo]")
        for p in (a, v1, v2):
            await wait_pixel(p, 0.5, 0.42, empty)
        await a.click(".anno-bar [data-tool=hl]")
        await stroke(a, [(0.2, 0.7), (0.5, 0.7)])
        await wait_pixel(v1, 0.35, 0.7, yellow)
        await wait_pixel(v1, 0.35, 0.7, empty, 8)      # fades out by itself
        await a.click(".anno-bar [data-tool=laser]")
        g = await a.evaluate(GEOM)
        await a.mouse.move(g["left"] + 0.8 * g["w"], g["top"] + 0.2 * g["h"]); await a.mouse.down()
        await a.mouse.move(g["left"] + 0.82 * g["w"], g["top"] + 0.2 * g["h"], steps=4)
        await wait_pixel(v1, 0.82, 0.2, red)
        await a.mouse.up()
        await wait_pixel(v1, 0.82, 0.2, empty, 4)
        print("3 undo removes the stroke; the highlighter fades by itself; the laser pointer disappears when lifted")

        # 4 late joiner sees kept strokes; stopping the share clears them
        await a.click(".anno-bar [data-tool=pen]")
        await stroke(a, [(0.25, 0.3), (0.45, 0.3)])
        await wait_pixel(v1, 0.35, 0.3, red)
        v3 = await page(1024, 768)
        await v3.goto(f"{BASE}/r/{code}"); await v3.fill("#pjNick", "Di"); await v3.click("#pjBtn"); await v3.wait_for_selector("#meeting:not(.hidden)")
        await until(v3, f"({GEOM})() !== null", timeout=20000)
        await wait_pixel(v3, 0.35, 0.3, red, 10)
        await a.click(".anno-bar [data-act=close]"); await a.wait_for_selector(".anno-pill:not(.hidden)")
        await wait_pixel(v1, 0.35, 0.3, red, 2)        # closing the toolbar keeps the strokes
        await a.click("#cScreen")
        await until(v1, f"({GEOM})() === null")
        await a.click("#cScreen")
        await until(v1, f"({GEOM})() !== null", timeout=20000)
        await asyncio.sleep(2.5)
        assert empty(await pixel(v1, 0.35, 0.3)), "a new share starts clean"
        print("4 a late joiner sees the strokes still on screen; a new share starts clean")
        await b.close()
    print("ANNOTATE OK")

asyncio.run(main())
