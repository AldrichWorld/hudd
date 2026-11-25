"""Screen-share annotation (sharer only), three browsers with different window sizes:
1 only the sharer gets the Annotate button and toolbar; viewers can't draw
2 a pen stroke lands on the same spot of the shared picture for viewers with very different windows (wide desktop, tall phone),
  shown about as late as the picture itself (receive buffer)
3 undo removes it; the highlighter fades by itself; the laser pointer disappears when lifted
4 someone who joins mid-share sees the strokes still on screen; stopping the share clears everything
   (steps 1–4: a browser without the floating window, like Safari/Firefox: drawing on the tile in the meeting page)
5 Chrome's floating annotation window: always on top, live preview, drawing there reaches viewers"""
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
        a = await page(1280, 800)                 # sharer (first without the floating window, as in Safari/Firefox)
        await a.add_init_script("try{delete window.documentPictureInPicture}catch(e){}")
        v1 = await page(1600, 900)                # wide desktop viewer
        v2 = await page(390, 844, is_mobile=True, has_touch=True)   # tall phone viewer

        await a.goto(BASE + "/"); await a.click("#newBtn"); await a.fill("#cNick", "Ana")
        await a.click("#createBtn"); await a.wait_for_url("**/r/*"); code = a.url.rsplit("/", 1)[1]
        await a.click("#pjBtn"); await a.wait_for_selector("#meeting:not(.hidden)")
        for p, n in ((v1, "Bo"), (v2, "Cy")):
            await p.goto(f"{BASE}/r/{code}"); await p.fill("#pjNick", n); await p.click("#pjBtn"); await p.wait_for_selector("#meeting:not(.hidden)")

        # 1 share: only the sharer gets the Annotate button
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
        await a.click("#cScreen"); await until(v1, f"({GEOM})() === null")

        # 5 floating window (Document Picture-in-Picture, Chrome/Edge)
        if True:
            hc = await b.new_context(permissions=["camera", "microphone"], viewport={"width": 1100, "height": 700})
            await hc.add_init_script("try{localStorage.setItem('lkm.devicePrefs',JSON.stringify({mic:false,cam:false}));localStorage.setItem('hudd.devicePrefs',JSON.stringify({mic:false,cam:false}))}catch(e){}")
            s2 = await hc.new_page()
            await s2.goto(f"{BASE}/r/{code}"); await s2.fill("#pjNick", "Eve"); await s2.click("#pjBtn"); await s2.wait_for_selector("#meeting:not(.hidden)")
            assert await s2.evaluate("'documentPictureInPicture' in window"), "no Document PiP in this browser"
            assert await s2.is_hidden("#cAnno")                       # only while sharing
            await s2.click("#cScreen"); await s2.wait_for_selector("#cAnno:not(.hidden)")
            await until(v1, f"({GEOM})() !== null", timeout=20000)
            await s2.click("#cAnno")
            await until(s2, "documentPictureInPicture.window && documentPictureInPicture.window.document.querySelector('.anno-pad video').videoWidth > 0")
            # draw in the floating window (pointer events dispatched inside it)
            await s2.evaluate("""() => { const w = documentPictureInPicture.window, d = w.document, el = d.querySelector('.anno-pad'), v = el.querySelector('video'), c = el.querySelector('.anno-layer');
              d.querySelector('[data-tool=pen]').click();
              const W = el.clientWidth, H = el.clientHeight, s = Math.min(W / v.videoWidth, H / v.videoHeight), cw = v.videoWidth * s, ch = v.videoHeight * s, ox = (W - cw) / 2, oy = (H - ch) / 2;
              const at = (nx, ny) => ({ clientX: ox + nx * cw, clientY: oy + ny * ch, pointerId: 1, button: 0, bubbles: true });
              c.dispatchEvent(new w.PointerEvent('pointerdown', at(0.3, 0.5)));
              for (let i = 1; i <= 10; i++) c.dispatchEvent(new w.PointerEvent('pointermove', at(0.3 + i * 0.04, 0.5)));
              c.dispatchEvent(new w.PointerEvent('pointerup', at(0.7, 0.5))); }""")
            for p in (v1, v2):
                await wait_pixel(p, 0.5, 0.5, red)
            pad_px = await s2.evaluate("""() => { const d = documentPictureInPicture.window.document, el = d.querySelector('.anno-pad'), c = el.querySelector('.anno-layer'), v = el.querySelector('video');
              const W = el.clientWidth, H = el.clientHeight, s = Math.min(W / v.videoWidth, H / v.videoHeight), cw = v.videoWidth * s, ch = v.videoHeight * s, k = c.width / W;
              return [...c.getContext('2d').getImageData(Math.round(((W - cw) / 2 + 0.5 * cw) * k), Math.round(((H - ch) / 2 + 0.5 * ch) * k), 1, 1).data]; }""")
            assert red(pad_px), pad_px
            if os.getenv("SHOTS_DIR"):
                await v1.screenshot(path=f"{os.getenv('SHOTS_DIR')}/anno_pad_viewer.png")
            await s2.click("#cScreen")
            await until(s2, "!documentPictureInPicture.window")          # stopping the share closes the floating window
            await hc.close()
            print("5 floating annotation window: live preview, drawing there reaches viewers; closes when the share stops")
        await b.close()
    print("ANNOTATE OK")

asyncio.run(main())
