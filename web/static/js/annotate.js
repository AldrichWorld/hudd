/* Screen-share annotation: the person sharing their screen can highlight, point and draw on it.
   Strokes are drawn on a transparent layer over the shared-screen tile (never on the shared window itself)
   and sent to everyone as data messages, in coordinates relative to the shared picture (0–1), so they land on
   the same spot whatever the viewer's screen size. Only the sharer draws.
   - Highlighter: wide, translucent; fades out a few seconds after the stroke ends
   - Laser pointer: a red dot with a short trail; gone right after the pointer is lifted
   - Pen: thin line that stays until undone or cleared
   Viewers receive the screen picture through a ~1 s receive buffer, so strokes are shown with the same delay
   (measured from the video receiver when possible) to stay in step with the picture.
   Usage: HuddleAnno.init({ room, LK, t, toast, delayMs }); HuddleAnno.sync([{ key, el, video, identity, local }])
   after every layout render; HuddleAnno.relabel() after a language change. */
(() => {
  const TOPIC = 'huddle.anno';
  const HL_HOLD = 2500, HL_FADE = 800;        // highlighter: visible, then fading (ms)
  const LASER_TRAIL = 450, LASER_GONE = 250;  // laser: trail length, fade after lift (ms)
  const SEND_EVERY = 40;                      // ms between live point batches
  const MAX_PTS = 400;                        // points per stroke (a longer stroke continues as a new one)
  const COLORS = { hl: 'rgba(255, 221, 0, 0.38)', pen: '#ff3b30', laser: '#ff2d2d' };

  let room = null, LK = null, t = (k) => k, toast = () => {};
  let baseDelay = 1000, measuredDelay = null;
  const strokes = new Map();   // sharer identity -> Map(strokeId -> stroke)
  const overlays = new Map();  // tile key -> overlay
  const queue = [];            // incoming messages waiting for the video delay: { at, from, msg }
  let raf = 0;
  // the local sharer's drawing state
  let tool = 'hl', drawing = null, pending = [], sendTimer = 0, order = [], seq = 0, localAspect = 0;

  const now = () => performance.now();
  const enc = (o) => new TextEncoder().encode(JSON.stringify(o));
  const r3 = (v) => Math.round(Math.min(1, Math.max(0, v)) * 1000) / 1000;
  const mapOf = (id) => { let m = strokes.get(id); if (!m) { m = new Map(); strokes.set(id, m); } return m; };
  const localId = () => room && room.localParticipant && room.localParticipant.identity;

  function send(msg, reliable, to) {
    if (!room || !room.localParticipant) return;
    const opts = { reliable, topic: TOPIC };
    if (to) opts.destinationIdentities = to;
    room.localParticipant.publishData(enc(msg), opts).catch(() => {});
  }

  /* ---------- geometry: the picture's rectangle inside the tile (video uses object-fit: contain) ---------- */
  function contentRect(ov) {
    const W = ov.el.clientWidth, H = ov.el.clientHeight, vw = ov.video.videoWidth, vh = ov.video.videoHeight;
    if (!W || !H || !vw || !vh) return null;
    const s = Math.min(W / vw, H / vh), cw = vw * s, ch = vh * s;
    return { x: (W - cw) / 2, y: (H - ch) / 2, w: cw, h: ch };
  }

  /* ---------- drawing ---------- */
  function resize(ov) {
    const dpr = window.devicePixelRatio || 1, W = ov.el.clientWidth, H = ov.el.clientHeight;
    const cw = Math.round(W * dpr), ch = Math.round(H * dpr);
    if (ov.canvas.width !== cw || ov.canvas.height !== ch) { ov.canvas.width = cw; ov.canvas.height = ch; }
  }

  function strokePath(ctx, pts, rc) {
    ctx.beginPath();
    const X = (p) => rc.x + p[0] * rc.w, Y = (p) => rc.y + p[1] * rc.h;
    if (pts.length === 1) { ctx.moveTo(X(pts[0]), Y(pts[0])); ctx.lineTo(X(pts[0]) + 0.01, Y(pts[0])); return; }
    ctx.moveTo(X(pts[0]), Y(pts[0]));
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (X(pts[i]) + X(pts[i + 1])) / 2, my = (Y(pts[i]) + Y(pts[i + 1])) / 2;
      ctx.quadraticCurveTo(X(pts[i]), Y(pts[i]), mx, my);
    }
    ctx.lineTo(X(pts[pts.length - 1]), Y(pts[pts.length - 1]));
  }

  // returns true while something on this layer is still changing (fading, laser trail)
  function draw(ov) {
    resize(ov);
    const ctx = ov.canvas.getContext('2d'), dpr = window.devicePixelRatio || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, ov.canvas.width, ov.canvas.height);
    const rc = contentRect(ov), m = strokes.get(ov.identity);
    if (!rc || !m || !m.size) return false;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    const tnow = now();
    let busy = false;
    for (const [id, s] of m) {
      if (!s.pts.length) continue;
      if (s.tool === 'hl') {
        let a = 1;
        if (s.endAt) {
          const age = tnow - s.endAt;
          if (age > HL_HOLD + HL_FADE) { m.delete(id); continue; }
          if (age > HL_HOLD) a = 1 - (age - HL_HOLD) / HL_FADE;
          busy = true;
        }
        ctx.globalAlpha = a; ctx.strokeStyle = COLORS.hl; ctx.lineWidth = Math.max(8, rc.h * 0.028);
        strokePath(ctx, s.pts, rc); ctx.stroke();
      } else if (s.tool === 'pen') {
        ctx.globalAlpha = 1; ctx.strokeStyle = COLORS.pen; ctx.lineWidth = Math.max(2.5, rc.h * 0.0055);
        strokePath(ctx, s.pts, rc); ctx.stroke();
      } else if (s.tool === 'laser') {
        if (s.endAt && tnow - s.endAt > LASER_GONE) { m.delete(id); continue; }
        busy = true;
        const fade = s.endAt ? 1 - (tnow - s.endAt) / LASER_GONE : 1;
        // trail: the points of the last LASER_TRAIL ms (point times are local arrival times)
        const tail = s.pts.filter((p, i) => (s.times[i] || 0) > (s.endAt || tnow) - LASER_TRAIL);
        const w = Math.max(4, rc.h * 0.009);
        if (tail.length > 1) {
          ctx.globalAlpha = 0.45 * fade; ctx.strokeStyle = COLORS.laser; ctx.lineWidth = w;
          strokePath(ctx, tail, rc); ctx.stroke();
        }
        const p = s.pts[s.pts.length - 1], x = rc.x + p[0] * rc.w, y = rc.y + p[1] * rc.h;
        ctx.globalAlpha = fade; ctx.shadowColor = COLORS.laser; ctx.shadowBlur = w * 2.5;
        ctx.fillStyle = COLORS.laser; ctx.beginPath(); ctx.arc(x, y, w * 0.9, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
      }
    }
    ctx.globalAlpha = 1;
    return busy;
  }

  function tick() {
    raf = 0;
    const tnow = now();
    while (queue.length && queue[0].at <= tnow) { const q = queue.shift(); apply(q.from, q.msg, q.at); }
    let busy = queue.length > 0 || !!drawing;
    for (const ov of overlays.values()) if (draw(ov)) busy = true;
    if (busy) raf = requestAnimationFrame(tick);
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };

  /* ---------- messages ---------- */
  // pt: live points of a stroke (lossy) · end: the whole stroke (reliable) · undo / clear / reset · sync: kept strokes for a late joiner
  function apply(from, msg, at) {
    const m = mapOf(from), tnow = at || now();
    if (msg.t === 'pt' || msg.t === 'end') {
      let s = m.get(msg.id);
      if (!s) { s = { tool: msg.tool, pts: [], times: [], endAt: 0 }; m.set(msg.id, s); }
      if (s.endAt && msg.t === 'pt') return;
      if (msg.t === 'pt') {
        for (const p of msg.pts) { s.pts.push(p); s.times.push(tnow); }
      } else {
        if (s.tool !== 'laser') { s.pts = msg.pts; s.times = msg.pts.map(() => tnow); }
        s.endAt = tnow;
      }
      s.lastAt = tnow;
    } else if (msg.t === 'undo') {
      m.delete(msg.id);
    } else if (msg.t === 'clear' || msg.t === 'reset') {
      m.clear();
    } else if (msg.t === 'sync') {
      m.clear();
      for (const s of msg.strokes || []) m.set(s.id, { tool: s.tool, pts: s.pts, times: s.pts.map(() => tnow), endAt: tnow });
    }
    kick();
  }

  function onData(payload, participant, kind, topic) {
    if (topic !== TOPIC || !participant) return;
    let msg; try { msg = JSON.parse(new TextDecoder().decode(payload)); } catch { return; }
    // a sync is the current state: show it at once; live strokes wait as long as the picture does
    if (msg.t === 'sync') return apply(participant.identity, msg);
    queue.push({ at: now() + currentDelay(), from: participant.identity, msg });
    kick();
  }

  /* ---------- delay of the shared picture at viewers ---------- */
  function currentDelay() { return measuredDelay == null ? baseDelay : measuredDelay; }
  let lastStats = null;
  async function measure() {
    // average time a frame of the screen share waits in the receive buffer (jitterBufferDelay / emitted count)
    try {
      const ov = [...overlays.values()].find((o) => !o.local && o.track && o.track.receiver);
      if (!ov) { lastStats = null; return; }
      const rep = await ov.track.receiver.getStats();
      let d = null, n = null;
      rep.forEach((r) => { if (r.type === 'inbound-rtp' && r.kind === 'video') { d = r.jitterBufferDelay; n = r.jitterBufferEmittedCount; } });
      if (d == null || !n) return;
      if (lastStats && n > lastStats.n) {
        const ms = ((d - lastStats.d) / (n - lastStats.n)) * 1000;
        if (ms > 0 && ms < 4000) measuredDelay = measuredDelay == null ? ms : measuredDelay * 0.7 + ms * 0.3;
      }
      lastStats = { d, n };
    } catch {}
  }

  /* ---------- the sharer's side ---------- */
  function norm(ov, ev) {
    const rc = contentRect(ov); if (!rc) return null;
    const b = ov.el.getBoundingClientRect();
    return [r3((ev.clientX - b.left - rc.x) / rc.w), r3((ev.clientY - b.top - rc.y) / rc.h)];
  }

  function flush() {
    if (!drawing || !pending.length) return;
    send({ t: 'pt', id: drawing.id, tool: drawing.tool, pts: pending }, false);
    pending = [];
  }

  function startStroke(ov, p) {
    const id = `${localId()}.${Date.now().toString(36)}.${seq++}`;
    drawing = { id, tool, ov };
    mapOf(localId()).set(id, { tool, pts: [p], times: [now()], endAt: 0, lastAt: now() });
    pending = [p];
    clearInterval(sendTimer); sendTimer = setInterval(flush, SEND_EVERY);
    kick();
  }

  function endStroke() {
    if (!drawing) return;
    flush(); clearInterval(sendTimer);
    const s = mapOf(localId()).get(drawing.id);
    if (s) {
      s.endAt = now();
      send({ t: 'end', id: drawing.id, tool: drawing.tool, pts: drawing.tool === 'laser' ? s.pts.slice(-1) : s.pts }, true);
      if (drawing.tool !== 'laser') order.push(drawing.id);
    }
    drawing = null; kick();
  }

  function onDown(ov, ev) {
    if (!ov.active || ev.button > 0) return;
    ev.preventDefault(); ev.stopPropagation();
    const p = norm(ov, ev); if (!p) return;
    try { ov.canvas.setPointerCapture(ev.pointerId); } catch {}
    startStroke(ov, p);
  }
  function onMove(ov, ev) {
    if (!drawing || drawing.ov !== ov) return;
    ev.preventDefault();
    const p = norm(ov, ev); if (!p) return;
    const s = mapOf(localId()).get(drawing.id); if (!s) return;
    const q = s.pts[s.pts.length - 1];
    if (q && Math.abs(q[0] - p[0]) < 0.002 && Math.abs(q[1] - p[1]) < 0.002) return;
    s.pts.push(p); s.times.push(now()); s.lastAt = now(); pending.push(p);
    if (s.pts.length >= MAX_PTS) { endStroke(); startStroke(ov, p); }
    kick();
  }

  function undo() {
    const m = mapOf(localId());
    while (order.length) {
      const id = order.pop();
      if (m.has(id)) { m.delete(id); send({ t: 'undo', id }, true); break; }
    }
    kick();
  }
  function clearAll() { mapOf(localId()).clear(); order = []; send({ t: 'clear' }, true); kick(); }

  // a participant who joins mid-share gets the strokes that are still on the screen
  function onJoin(p) {
    const m = strokes.get(localId());
    if (!m || !m.size || !isSharing()) return;
    const kept = [...m.entries()].filter(([, s]) => s.tool === 'pen' && s.endAt).map(([id, s]) => ({ id, tool: s.tool, pts: s.pts }));
    if (kept.length) setTimeout(() => send({ t: 'sync', strokes: kept }, true, [p.identity]), 1500);
  }
  const isSharing = () => { const pub = room && room.localParticipant.getTrackPublication(LK.Track.Source.ScreenShare); return !!(pub && pub.track && !pub.isMuted); };

  /* ---------- overlay and toolbar on a screen-share tile ---------- */
  const ICONS = {
    hl: '<path d="M9 11l-6 6v3h9l3-3"/><path d="M22 12l-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
    laser: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
    clear: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    close: '<path d="M18 6L6 18M6 6l12 12"/>',
    anno: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[k]}</svg>`;

  function makeOverlay(o) {
    const canvas = document.createElement('canvas');
    canvas.className = 'anno-layer';
    const ov = { key: o.key, el: o.el, video: o.video, identity: o.identity, local: o.local, track: o.track, canvas, active: false, bar: null, pill: null };
    o.el.appendChild(canvas);
    if (o.local) {
      const pill = document.createElement('button');
      pill.type = 'button'; pill.className = 'anno-pill';
      pill.onclick = (ev) => { ev.stopPropagation(); setActive(ov, true); };
      const bar = document.createElement('div');
      bar.className = 'anno-bar hidden';
      bar.innerHTML = ['hl', 'laser', 'pen'].map((k) => `<button type="button" data-tool="${k}">${svg(k)}</button>`).join('')
        + '<span class="sep"></span>'
        + ['undo', 'clear', 'close'].map((k) => `<button type="button" data-act="${k}">${svg(k)}</button>`).join('');
      bar.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const b = ev.target.closest('button'); if (!b) return;
        if (b.dataset.tool) { tool = b.dataset.tool; paintBar(ov); }
        if (b.dataset.act === 'undo') undo();
        if (b.dataset.act === 'clear') clearAll();
        if (b.dataset.act === 'close') setActive(ov, false);
      });
      bar.addEventListener('dblclick', (ev) => ev.stopPropagation());
      o.el.appendChild(pill); o.el.appendChild(bar);
      ov.pill = pill; ov.bar = bar;
      canvas.addEventListener('pointerdown', (ev) => onDown(ov, ev));
      canvas.addEventListener('pointermove', (ev) => onMove(ov, ev));
      canvas.addEventListener('pointerup', endStroke);
      canvas.addEventListener('pointercancel', endStroke);
      canvas.addEventListener('dblclick', (ev) => { if (ov.active) ev.stopPropagation(); });
      // the shared picture changed shape (another window, resized window): old strokes no longer fit
      o.video.addEventListener('resize', () => {
        const a = o.video.videoWidth / (o.video.videoHeight || 1);
        if (localAspect && Math.abs(a - localAspect) > 0.01) { mapOf(localId()).clear(); order = []; send({ t: 'reset' }, true); }
        localAspect = a; kick();
      });
      labelOverlay(ov);
    } else {
      o.video.addEventListener('resize', kick);
    }
    const ro = new ResizeObserver(kick); ro.observe(o.el); ov.ro = ro;
    return ov;
  }

  function paintBar(ov) {
    if (!ov.bar) return;
    ov.bar.querySelectorAll('[data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === tool));
    ov.canvas.dataset.tool = tool;
  }

  function labelOverlay(ov) {
    if (!ov.pill) return;
    ov.pill.innerHTML = `${svg('anno')}<span>${t('anno.btn')}</span>`;
    const L = { hl: 'anno.hl', laser: 'anno.laser', pen: 'anno.pen', undo: 'anno.undo', clear: 'anno.clear', close: 'anno.close' };
    ov.bar.querySelectorAll('button').forEach((b) => { const k = L[b.dataset.tool || b.dataset.act]; b.title = t(k); b.setAttribute('aria-label', t(k)); });
  }

  function setActive(ov, on) {
    ov.active = on;
    ov.el.classList.toggle('annotating', on);
    ov.bar.classList.toggle('hidden', !on);
    ov.pill.classList.toggle('hidden', on);
    paintBar(ov);
    if (!on) endStroke();
    if (on) {
      // sharing the whole screen while Huddle is on it shows a picture within a picture
      const st = ov.track && ov.track.mediaStreamTrack && ov.track.mediaStreamTrack.getSettings ? ov.track.mediaStreamTrack.getSettings() : {};
      if (st.displaySurface === 'monitor') toast(t('anno.mirror'), 7000);
    }
  }

  /* ---------- public ---------- */
  let measureTimer = 0;
  function init(opts) {
    room = opts.room; LK = opts.LK; t = opts.t || t; toast = opts.toast || toast;
    baseDelay = opts.delayMs == null ? baseDelay : opts.delayMs;
    room.on(LK.RoomEvent.DataReceived, onData);
    room.on(LK.RoomEvent.ParticipantConnected, onJoin);
    room.on(LK.RoomEvent.LocalTrackPublished, (pub) => {
      if (pub.source !== LK.Track.Source.ScreenShare) return;
      mapOf(localId()).clear(); order = []; localAspect = 0;
      toast(t('anno.tip'), 6000);
    });
    room.on(LK.RoomEvent.LocalTrackUnpublished, (pub) => {
      if (pub.source !== LK.Track.Source.ScreenShare) return;
      endStroke(); mapOf(localId()).clear(); order = []; send({ t: 'reset' }, true);
    });
    room.on(LK.RoomEvent.ParticipantDisconnected, (p) => { strokes.delete(p.identity); kick(); });
    clearInterval(measureTimer); measureTimer = setInterval(measure, 2000);
  }

  // called after each layout render with the screen-share tiles now on screen
  function sync(list) {
    const keep = new Set(list.map((o) => o.key));
    for (const [k, ov] of overlays) if (!keep.has(k) || !ov.el.isConnected || !ov.el.contains(ov.canvas)) {
      if (drawing && drawing.ov === ov) endStroke();
      ov.ro && ov.ro.disconnect(); ov.canvas.remove(); ov.bar && ov.bar.remove(); ov.pill && ov.pill.remove();
      overlays.delete(k);
    }
    const sharing = new Set(list.map((o) => o.identity));
    for (const id of [...strokes.keys()]) if (!sharing.has(id)) strokes.delete(id);
    for (const o of list) {
      const ov = overlays.get(o.key);
      if (!ov) overlays.set(o.key, makeOverlay(o));
      else ov.track = o.track;
    }
    kick();
  }

  function relabel() { for (const ov of overlays.values()) labelOverlay(ov); }

  window.HuddleAnno = { init, sync, relabel };
})();
