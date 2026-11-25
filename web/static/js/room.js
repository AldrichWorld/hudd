/* Meeting page: before joining, in the meeting, and after leaving. */
(() => {
  const LK = window.LivekitClient;
  const { store, api, fmtCode, color, initial, esc, toast, copy, url } = Util;
  const t = I18N.t;
  const $ = (id) => document.getElementById(id);
  const show = (id) => {
    ['prejoin', 'meeting', 'ended'].forEach((s) => $(s).classList.toggle('hidden', s !== id));
    $('langFloat').classList.toggle('hidden', id === 'meeting');
    $('brandFloat').classList.toggle('hidden', id === 'meeting');
  };

  const code = (location.pathname.match(/\/r\/(\d{9})(?!\d)/) || [])[1];
  const ownerKeys = store.get('hudd.ownerKeys', {});
  const ownerKey = code ? ownerKeys[code] || null : null;
  const prefs = store.get('hudd.devicePrefs', { mic: true, cam: false });

  let roomInfo = null;   // meeting info from the server
  let joinInfo = null;   // the join response
  let room = null;       // LiveKit Room
  let leaving = false;
  let previewTrack = null;
  let config = { share_base: '' };
  // A ?pwd= in the invite link is kept for this tab only, then removed from the address bar (and history)
  const qsPwd = new URLSearchParams(location.search).get('pwd');
  if (code && qsPwd) {
    store.sset('hudd.pwd.' + code, qsPwd);
    try { history.replaceState(null, '', location.pathname + location.hash); } catch {}
  }
  const savedPwd = () => (code && store.sget('hudd.pwd.' + code)) || '';
  let pwdNeeded = false;  // the server asked for a password when joining
  // The host also sees the meeting password next to the meeting ID, to read it out to people.
  // (The server forgets plain passwords when it restarts; the host's browser keeps its own copy.)
  const hostPwd = () => (roomInfo && roomInfo.password) || (code && store.get('hudd.hostPwd', {})[code]) || '';
  const codeLabel = () => t('m.code', { code: fmtCode(code) }) + (isOwnerRole() && hostPwd() ? ' · ' + t('pwd.inRoom', { pwd: hostPwd() }) : '');
  const metaOf = (p) => { try { return JSON.parse(p.metadata || '{}'); } catch { return {}; } };
  const isOwnerRole = () => joinInfo && joinInfo.role === 'owner';

  const APPNAME = (window.APP && window.APP.name) || 'Hudd';

  /* ================= start ================= */
  async function init() {
    if (!code) { location.href = url('/'); return; }
    try { config = await api('/api/config'); } catch {}
    try {
      roomInfo = await api(`/api/rooms/${code}`, null, null, ownerKey ? { 'X-Owner-Key': ownerKey } : null);
    } catch (e) {
      return showEnded({ title: () => t(e.status === 404 ? 'ed.ended' : 'ed.cantJoin'), sub: e.message });
    }
    document.title = `${roomInfo.title} · ${APPNAME}`;
    setupPrejoin();
  }

  /* ================= before joining ================= */
  function setupPrejoin() {
    show('prejoin');
    const pending = store.sget('hudd.join.' + code);
    $('pjTitle').textContent = roomInfo.title;
    if (pending) {
      $('pjFields').classList.add('hidden');
      $('pjNick').required = false;
      const p = store.get('hudd.profile', {});
      const who = document.createElement('p'); who.className = 'sub'; who.style.marginTop = '18px'; who.id = 'pjWho';
      who.dataset.name = p.nickname || ''; who.dataset.host = pending.role === 'owner' ? '1' : '';
      $('pjFields').after(who);
    } else {
      const p = store.get('hudd.profile', {});
      $('pjNick').value = p.nickname || '';
    }
    relabelPrejoin();
    if (prefs.cam) startPreview();

    $('pvMic').onclick = (e) => { e.preventDefault(); prefs.mic = !prefs.mic; store.set('hudd.devicePrefs', prefs); renderPrejoinButtons(); };
    $('pvCam').onclick = (e) => {
      e.preventDefault(); prefs.cam = !prefs.cam; store.set('hudd.devicePrefs', prefs); renderPrejoinButtons();
      prefs.cam ? startPreview() : stopPreview();
    };

    $('pjForm').onsubmit = async (e) => {
      e.preventDefault();
      const btn = $('pjBtn'); btn.disabled = true; $('pjErr').textContent = '';
      try {
        let info = store.sget('hudd.join.' + code);
        if (!info) {
          const nickname = $('pjNick').value.trim();
          const pass = $('pjPass').value.trim();
          if (pass) store.sset('hudd.pwd.' + code, pass);
          info = await api(`/api/rooms/${code}/join`, { nickname, owner_key: ownerKey || null, room_pass: pass || null });
          store.set('hudd.profile', Object.assign(store.get('hudd.profile', {}), { nickname }));
        }
        store.sdel('hudd.join.' + code);
        stopPreview();
        await connect(info);
      } catch (err) {
        $('pjErr').textContent = err.message || String(err);
        if (err.status === 403 && !hostLike()) { pwdNeeded = true; relabelPrejoin(); $('pjPass').focus(); }
        btn.disabled = false;
      }
    };
  }

  const hostLike = () => !!ownerKey;
  const roomSub = () => (roomInfo ? `${roomInfo.title} (${fmtCode(code)})` : fmtCode(code));
  function relabelPrejoin() {
    $('pjSub').textContent = t('pj.sub', { code: fmtCode(code), host: roomInfo.owner_nickname });
    $('pjBtn').textContent = t('pj.enter');
    // Meeting password box: shown to guests when the meeting has a password
    const askPwd = !store.sget('hudd.join.' + code) && !hostLike() && (roomInfo.has_password || pwdNeeded);
    $('pjPassWrap').classList.toggle('hidden', !askPwd);
    if (!$('pjPass').dataset.filled) { $('pjPass').value = savedPwd(); $('pjPass').dataset.filled = '1'; }
    const who = $('pjWho');
    if (who) who.textContent = t('pj.as', { name: who.dataset.name, host: who.dataset.host ? t('pj.asHost') : '' });
    if (!previewTrack) $('pvOff').textContent = $('pvOff').dataset.err || t('pj.camOff');
    renderPrejoinButtons();
  }
  function renderPrejoinButtons() {
    const st = (on) => t(on ? 'pj.on' : 'pj.off');
    $('pvMic').innerHTML = `<svg width="18" height="18"><use href="#i-${prefs.mic ? 'mic' : 'mic-off'}"/></svg>${esc(t('pj.mic', { state: st(prefs.mic) }))}`;
    $('pvCam').innerHTML = `<svg width="18" height="18"><use href="#i-${prefs.cam ? 'cam' : 'cam-off'}"/></svg>${esc(t('pj.cam', { state: st(prefs.cam) }))}`;
  }
  async function startPreview() {
    try {
      previewTrack = await LK.createLocalVideoTrack({ resolution: LK.VideoPresets.h540.resolution });
      previewTrack.attach($('pvVideo'));
      $('pvVideo').classList.remove('hidden'); $('pvOff').classList.add('hidden');
    } catch (e) {
      $('pvOff').dataset.err = t('pj.camErr', { err: e.message || e.name });
      $('pvOff').textContent = $('pvOff').dataset.err;
    }
  }
  function stopPreview() {
    if (previewTrack) { previewTrack.stop(); previewTrack = null; }
    $('pvVideo').classList.add('hidden'); $('pvOff').classList.remove('hidden'); delete $('pvOff').dataset.err; $('pvOff').textContent = t('pj.camOff');
  }

  /* ================= connect ================= */
  const SCREEN_BUFFER_MS = 1000;  // receive buffer for screen sharing (picture + shared audio)
  async function connect(info) {
    joinInfo = info;
    roomInfo = Object.assign({}, roomInfo, info.room);
    if (info.role === 'owner' && info.room.password) { const hp = store.get('hudd.hostPwd', {}); hp[code] = info.room.password; store.set('hudd.hostPwd', hp); }
    room = new LK.Room({ adaptiveStream: true, dynacast: true });
    bindRoomEvents();
  // Screen-share annotation: only the sharer draws (highlighter, laser pointer, pen); viewers see the strokes
    HuddleAnno.init({ room, LK, t: I18N.t, toast, delayMs: SCREEN_BUFFER_MS });
    const lkUrl = info.livekit_url || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;
    await room.connect(lkUrl, info.token);
    try { await room.startAudio(); } catch {}

    show('meeting');
    guardBack();
    $('mTitle').textContent = roomInfo.title;
    $('mCode').textContent = codeLabel();
    // Most phone and tablet browsers cannot share the screen: hide the button there
    $('cScreen').classList.toggle('hidden', !(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia));
    // On phones the video comes first; the members and chat panel opens from the "Members" button
    if (narrow()) setPanel(false);

    try { await room.localParticipant.setMicrophoneEnabled(prefs.mic); } catch (e) { toast(t('t.micErr', { err: e.message || e.name })); }
    try { await enableCamera(prefs.cam); } catch (e) { toast(t('t.camErr', { err: e.message || e.name })); }
    renderAll();
    if (isOwnerRole()) toast(t('t.started'));
  }

  function bindRoomEvents() {
    const E = LK.RoomEvent;
    const rerender = () => renderAll();
    [E.ParticipantConnected, E.ParticipantDisconnected, E.TrackSubscribed, E.TrackUnsubscribed, E.TrackMuted, E.TrackUnmuted,
      E.TrackPublished, E.TrackUnpublished, E.LocalTrackPublished, E.LocalTrackUnpublished,
      E.ParticipantNameChanged, E.ParticipantMetadataChanged, E.ParticipantAttributesChanged].forEach((ev) => room.on(ev, rerender));
    // Retry a failed subscription once (e.g. a screen share lost to a network hiccup)
    room.on(E.TrackSubscriptionFailed, (sid, p) => {
      const pub = p && p.getTrackPublicationBySid ? p.getTrackPublicationBySid(sid) : null;
      if (pub) setTimeout(() => { try { pub.setSubscribed(false); pub.setSubscribed(true); } catch {} }, 1000);
    });

    room.on(E.TrackSubscribed, (track) => {
      if (track.kind === LK.Track.Kind.Audio) { const el = track.attach(); el.style.display = 'none'; document.body.appendChild(el); }
    });
    // Screen sharing (and the shared tab/system audio) gets a ~1 s receive buffer: on lossy links lost packets
    // have time to be resent instead of asking the sharer for a new key frame, so the picture stays sharp.
    // The sharer's microphone is not delayed, so the picture runs about 1 s behind their voice.
    room.on(E.TrackSubscribed, (track, pub) => {
      const S = LK.Track.Source;
      const ms = (pub.source === S.ScreenShare || pub.source === S.ScreenShareAudio) ? SCREEN_BUFFER_MS : 0;
      if (!ms) return;
      try { track.setPlayoutDelay && track.setPlayoutDelay(ms / 1000); } catch {}
      try { if (track.receiver && 'jitterBufferTarget' in track.receiver) track.receiver.jitterBufferTarget = ms; } catch {}
    });
    room.on(E.TrackUnsubscribed, (track) => { if (track.kind === LK.Track.Kind.Audio) track.detach().forEach((el) => el.remove()); });
    room.on(E.ParticipantConnected, (p) => toast(t('t.joined', { name: p.name || p.identity })));
    room.on(E.ParticipantDisconnected, (p) => toast(t('t.left', { name: p.name || p.identity })));
    room.on(E.ActiveSpeakersChanged, (speakers) => {
      onSpeakers(speakers);
      const ids = new Set(speakers.map((s) => s.identity));
      document.querySelectorAll('.tile').forEach((t) => t.classList.toggle('speaking', ids.has(t.dataset.identity) && !t.classList.contains('screen')));
    });
    room.on(E.DataReceived, (payload, participant, kind, topic) => {
      // Chat goes straight between participants over LiveKit's data channel (the server keeps nothing,
      // so people who join later don't see earlier messages)
      if (topic === 'hudd.chat' && participant) { try { onChat(participant, JSON.parse(new TextDecoder().decode(payload))); } catch {} }
      // Host controls: only accepted from the server (participant is empty), so participants cannot fake them
      if (topic === 'hudd.ctl' && !participant) { try { onCtl(JSON.parse(new TextDecoder().decode(payload))); } catch {} }
    });
    room.on(E.AudioPlaybackStatusChanged, () => $('audioBanner').classList.toggle('hidden', room.canPlaybackAudio));
    $('audioBanner').onclick = () => room.startAudio();
    room.on(E.Disconnected, (reason) => onDisconnected(reason));
  }

  /* ================= video area: grid / speaker layout (each viewer chooses; affects only their screen) ================= */
  const tiles = new Map();
  const lay = Object.assign(
    { mode: 'auto', strip: 'right', hideStrip: false, hideSelf: false, stripW: 220, stripH: 140 },
    store.get('hudd.layout', {}),
  );
  let pinnedKey = null;          // the tile the viewer pinned
  let speakerKey = null;         // latest speaker (speaker layout without a pin or screen share)
  let speakerSwitchAt = 0;
  let knownScreens = new Set();  // to announce "X started sharing"
  const saveLay = () => store.set('hudd.layout', lay);
  const narrow = () => window.matchMedia('(max-width: 760px)').matches;

  function tileEntries() {
    const out = [];
    const all = [room.localParticipant, ...room.remoteParticipants.values()];
    for (const p of all) {
      const cam = p.getTrackPublication(LK.Track.Source.Camera);
      const mic = p.getTrackPublication(LK.Track.Source.Microphone);
      out.push({ key: p.identity, p, track: cam && !cam.isMuted ? cam.track : null, micOn: !!(mic && !mic.isMuted && mic.track), screen: false });
      const scr = p.getTrackPublication(LK.Track.Source.ScreenShare);
      if (scr && scr.track && !scr.isMuted) out.unshift({ key: p.identity + ':screen', p, track: scr.track, micOn: true, screen: true });
    }
    return out;
  }

  function makeTile(key) {
    const el = document.createElement('div');
    el.className = 'tile';
    el.innerHTML = `<video autoplay playsinline muted class="cam"></video><div class="avatar"><span></span></div>
      <div class="name"><span class="mic"></span><span class="n"></span></div>
      <div class="tile-act"><button class="b-pin"><svg><use href="#i-pin"/></svg></button><button class="b-full"><svg><use href="#i-full"/></svg></button></div>`;
    const t = { el, video: el.querySelector('video'), track: null, key };
    el.querySelector('.b-pin').onclick = (ev) => { ev.stopPropagation(); togglePin(key); };
    el.querySelector('.b-full').onclick = (ev) => { ev.stopPropagation(); fullscreen(t); };
    el.ondblclick = () => fullscreen(t);
    return t;
  }

  function togglePin(key) {
    pinnedKey = pinnedKey === key ? null : key;
    if (pinnedKey && lay.mode === 'grid') { lay.mode = 'speaker'; saveLay(); syncLayMenu(); }
    renderGrid();
  }

  function fullscreen(t) {
    const el = t.el;
    if (document.fullscreenElement) return document.exitFullscreen();
    if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
    else if (t.video.webkitEnterFullscreen) t.video.webkitEnterFullscreen(); // iOS Safari
  }

  function chooseMain(entries) {
    const has = (k) => k && entries.some((e) => e.key === k);
    if (has(pinnedKey)) return pinnedKey;
    if (pinnedKey) pinnedKey = null; // the pinned person left or stopped sharing
    const screen = entries.find((e) => e.screen);
    if (screen) return screen.key;
    if (has(speakerKey)) return speakerKey;
    const remote = entries.find((e) => e.p !== room.localParticipant);
    return (remote || entries[0] || {}).key;
  }

  function renderGrid() {
    if (!room) return;
    const all = tileEntries();
    // Announce new screen shares (auto mode switches to the speaker view)
    const screensNow = new Set(all.filter((e) => e.screen).map((e) => e.key));
    for (const k of screensNow) if (!knownScreens.has(k)) {
      const e = all.find((x) => x.key === k);
      if (e.p !== room.localParticipant) toast(t('t.shareStart', { name: e.p.name || e.p.identity }) + (lay.mode === 'auto' ? t('t.shareAuto') : ''), 4000);
    }
    knownScreens = screensNow;

    const entries = all.filter((e) => !(lay.hideSelf && e.p === room.localParticipant && !e.screen));
    const keys = new Set(entries.map((e) => e.key));
    for (const [k, t] of tiles) if (!keys.has(k)) { if (t.track) t.track.detach(t.video); t.el.remove(); tiles.delete(k); }

    const mode = lay.mode === 'grid' ? 'grid'
      : lay.mode === 'speaker' ? 'speaker'
      : (screensNow.size || (pinnedKey && keys.has(pinnedKey)) ? 'speaker' : 'grid');
    const speakerMode = mode === 'speaker' && entries.length > 1;
    const mainKey = speakerMode ? chooseMain(entries) : null;

    const grid = $('grid'), sv = $('speakerView'), mainArea = $('mainArea'), strip = $('strip');
    grid.classList.toggle('hidden', speakerMode);
    sv.classList.toggle('hidden', !speakerMode);
    const pos = narrow() ? 'bottom' : lay.strip;
    sv.classList.toggle('pos-right', pos === 'right');
    sv.classList.toggle('pos-bottom', pos === 'bottom');
    sv.classList.toggle('strip-hidden', !!lay.hideStrip);
    sv.style.setProperty('--strip-w', lay.stripW + 'px');
    sv.style.setProperty('--strip-h', lay.stripH + 'px');

    const place = (container, el, idx) => { if (container.children[idx] !== el) container.insertBefore(el, container.children[idx] || null); };
    let gi = 0, si = 0;
    for (const e of entries) {
      let t = tiles.get(e.key);
      if (!t) { t = makeTile(e.key); tiles.set(e.key, t); }
      const isLocal = e.p === room.localParticipant;
      t.el.dataset.identity = e.p.identity;
      t.el.classList.toggle('local', isLocal && !e.screen);
      t.el.classList.toggle('screen', e.screen);
      t.el.classList.toggle('pinned', e.key === pinnedKey);
      t.el.querySelector('.b-pin').classList.toggle('on', e.key === pinnedKey);
      t.el.querySelector('.b-pin').title = e.key === pinnedKey ? I18N.t('tile.unpin') : I18N.t('tile.pin');
      t.el.querySelector('.b-full').title = I18N.t('tile.full');
      if (t.track !== e.track) {
        if (t.track) t.track.detach(t.video);
        if (e.track) e.track.attach(t.video);
        t.track = e.track;
      }
      t.video.classList.toggle('hidden', !e.track);
      t.el.querySelector('.avatar').classList.toggle('hidden', !!e.track);
      const name = e.p.name || e.p.identity;
      const av = t.el.querySelector('.avatar span'); av.textContent = initial(name); av.style.background = color(e.p.identity);
      t.el.querySelector('.n').textContent = e.screen ? I18N.t('tile.screen', { name }) : isLocal ? I18N.t('tile.me', { name }) : name;
      t.el.querySelector('.mic').innerHTML = e.screen || e.micOn ? '' : '<svg width="14" height="14" class="mic-off"><use href="#i-mic-off"/></svg>';
      if (!speakerMode) place(grid, t.el, gi++);
      else if (e.key === mainKey) place(mainArea, t.el, 0);
      else place(strip, t.el, si++);
    }
    // Clear leftovers after a layout change
    if (!speakerMode) { mainArea.replaceChildren(); strip.replaceChildren(); }
    else { grid.replaceChildren(); while (mainArea.children.length > 1) strip.prepend(mainArea.lastElementChild); }
    const n = entries.length;
    grid.style.setProperty('--cols', n <= 1 ? 1 : n <= 4 ? 2 : n <= 9 ? 3 : 4);
    HuddleAnno.sync(entries.filter((e) => e.screen && !e.media && e.track).map((e) => ({ key: e.key, el: tiles.get(e.key).el, video: tiles.get(e.key).video, identity: e.p.identity, local: e.p === room.localParticipant, track: e.track })));
  }

  // Speaker layout without a pin or share follows the active speaker (at most every 2 s, to avoid jumping)
  function onSpeakers(speakers) {
    const remote = speakers.find((s) => s !== room.localParticipant);
    if (!remote || remote.identity === speakerKey) return;
    if (Date.now() - speakerSwitchAt < 2000) return;
    speakerKey = remote.identity; speakerSwitchAt = Date.now();
    if (!$('speakerView').classList.contains('hidden') && !pinnedKey && !knownScreens.size) renderGrid();
  }

  /* ---------- layout menu ---------- */
  function syncLayMenu() {
    document.querySelectorAll('input[name=lay]').forEach((r) => (r.checked = r.value === lay.mode));
    document.querySelectorAll('input[name=strip]').forEach((r) => (r.checked = r.value === lay.strip));
    $('layHideStrip').checked = !!lay.hideStrip; $('layHideSelf').checked = !!lay.hideSelf;
  }
  syncLayMenu();
  $('mLayout').onclick = (ev) => { ev.stopPropagation(); $('layMenu').classList.toggle('hidden'); };
  $('layMenu').onclick = (ev) => ev.stopPropagation();
  document.addEventListener('click', () => $('layMenu').classList.add('hidden'));
  document.querySelectorAll('input[name=lay]').forEach((r) => r.onchange = () => {
    lay.mode = r.value; if (lay.mode === 'grid') pinnedKey = null; saveLay(); renderGrid();
  });
  document.querySelectorAll('input[name=strip]').forEach((r) => r.onchange = () => { lay.strip = r.value; saveLay(); renderGrid(); });
  $('layHideStrip').onchange = (ev) => { lay.hideStrip = ev.target.checked; saveLay(); renderGrid(); };
  $('layHideSelf').onchange = (ev) => { lay.hideSelf = ev.target.checked; saveLay(); renderGrid(); };
  window.addEventListener('resize', () => renderGrid());

  /* ---------- drag the divider to resize the thumbnail strip ---------- */
  (() => {
    const div = $('divider');
    let drag = null;
    div.addEventListener('pointerdown', (ev) => {
      const sv = $('speakerView').getBoundingClientRect();
      drag = { right: $('speakerView').classList.contains('pos-right'), sv };
      div.classList.add('drag'); div.setPointerCapture(ev.pointerId); ev.preventDefault();
    });
    div.addEventListener('pointermove', (ev) => {
      if (!drag) return;
      if (drag.right) lay.stripW = Math.round(Math.min(Math.max(drag.sv.right - ev.clientX - 5, 120), drag.sv.width * 0.6));
      else lay.stripH = Math.round(Math.min(Math.max(drag.sv.bottom - ev.clientY - 5, 80), drag.sv.height * 0.6));
      $('speakerView').style.setProperty('--strip-w', lay.stripW + 'px');
      $('speakerView').style.setProperty('--strip-h', lay.stripH + 'px');
    });
    const end = () => { if (drag) { drag = null; div.classList.remove('drag'); saveLay(); } };
    div.addEventListener('pointerup', end); div.addEventListener('pointercancel', end);
  })();

  /* ================= members ================= */
  function renderMembers() {
    const list = [room.localParticipant, ...room.remoteParticipants.values()];
    list.sort((a, b) => (metaOf(b).role === 'owner') - (metaOf(a).role === 'owner'));
    $('memHead').textContent = t('m.members', { n: list.length });
    $('memTools').classList.toggle('hidden', !isOwnerRole() || list.length < 2);
    $('memberList').innerHTML = list.map((p) => {
      const name = p.name || p.identity;
      const mic = p.getTrackPublication(LK.Track.Source.Microphone);
      const micOn = mic && !mic.isMuted && mic.track;
      const badges = [
        metaOf(p).role === 'owner' ? `<span class="badge owner">${t('badge.host')}</span>` : '',
        p === room.localParticipant ? `<span class="badge me">${t('badge.me')}</span>` : '',
      ].join(' ');
      const icon = micOn ? '<svg width="16" height="16" style="color:var(--muted)"><use href="#i-mic"/></svg>' : '<svg width="16" height="16" class="mic-off"><use href="#i-mic-off"/></svg>';
      // Host: clicking someone else's microphone icon mutes them / asks them to unmute
      const ctl = isOwnerRole() && p !== room.localParticipant;
      const micEl = ctl
        ? `<button class="mic-btn" data-id="${esc(p.identity)}" data-on="${micOn ? 1 : 0}" title="${esc(t(micOn ? 'mem.mute' : 'mem.unmute', { name }))}" aria-label="${esc(t(micOn ? 'mem.mute' : 'mem.unmute', { name }))}">${icon}</button>`
        : icon;
      return `<div class="member"><div class="av" style="background:${color(p.identity)}">${esc(initial(name))}</div>
        <div class="nm">${esc(name)}</div>${badges}
        ${micEl}</div>`;
    }).join('');
  }

  /* ---------- host microphone control: mute all / unmute all / mute one / unmute one ---------- */
  async function setMics(identity, mute) {
    try {
      const r = await api(`/api/rooms/${code}/mute`, { owner_key: ownerKey, identity, mute });
      if (identity) {
        const p = room.remoteParticipants.get(identity), name = (p && (p.name || p.identity)) || identity;
        toast(r.count ? t(mute ? 't.mutedOne' : 't.askedOne', { name }) : t(mute ? 't.noneToMute' : 't.noneToUnmute'));
      } else {
        toast(r.count ? t(mute ? 't.mutedN' : 't.askedN', { n: r.count }) : t(mute ? 't.noneToMute' : 't.noneToUnmute'));
      }
    } catch (e) { toast(e.message); }
  }
  $('muteAll').onclick = () => setMics(null, true);
  $('unmuteAll').onclick = () => setMics(null, false);
  $('memberList').addEventListener('click', (e) => {
    const b = e.target.closest('.mic-btn');
    if (b) setMics(b.dataset.id, b.dataset.on === '1');
  });
  // A participant receives a host instruction (only accepted from the server)
  function onCtl(d) {
    if (d.action === 'muted') { renderAll(); toast(t('t.mutedByHost')); }
    if (d.action === 'unmute' && !room.localParticipant.isMicrophoneEnabled) $('askUnmute').classList.remove('hidden');
  }
  $('auNo').onclick = () => $('askUnmute').classList.add('hidden');
  $('auYes').onclick = async () => {
    $('askUnmute').classList.add('hidden');
    try { await room.localParticipant.setMicrophoneEnabled(true); } catch (e) { toast(t('t.micErr', { err: e.message || e.name })); }
    renderAll();
  };

  function renderControls() {
    const lp = room.localParticipant;
    const micOn = lp.isMicrophoneEnabled, camOn = lp.isCameraEnabled, scrOn = lp.isScreenShareEnabled;
    const set = (id, on, iconOn, iconOff, lblOn, lblOff, offClass = true) => {
      const b = $(id);
      b.querySelector('svg').innerHTML = `<use href="#${on ? iconOn : iconOff}"/>`;
      b.querySelector('.lbl').textContent = on ? lblOn : lblOff;
      if (offClass) b.classList.toggle('off', !on);
    };
    set('cMic', micOn, 'i-mic', 'i-mic-off', t('c.mute'), t('c.unmute'));
    set('cCam', camOn, 'i-cam', 'i-cam-off', t('c.stopVideo'), t('c.startVideo'));
    set('cScreen', scrOn, 'i-screen', 'i-screen', t('c.stopShare'), t('c.share'), false);
    $('cScreen').classList.toggle('on-accent', scrOn);
    $('cAnno').classList.toggle('hidden', !scrOn);
  }

  function renderAll() {
    if (!room) return;
    renderGrid(); renderMembers(); renderControls();
  }

  /* ================= control bar ================= */
  $('cMic').onclick = async () => { await room.localParticipant.setMicrophoneEnabled(!room.localParticipant.isMicrophoneEnabled).catch((e) => toast(t('t.mic', { err: e.message }))); prefs.mic = room.localParticipant.isMicrophoneEnabled; store.set('hudd.devicePrefs', prefs); renderAll(); };
  const enableCamera = (on) => room.localParticipant.setCameraEnabled(on);
  $('cCam').onclick = async () => { await enableCamera(!room.localParticipant.isCameraEnabled).catch((e) => toast(t('t.cam', { err: e.message }))); prefs.cam = room.localParticipant.isCameraEnabled; store.set('hudd.devicePrefs', prefs); renderAll(); };
  /* Screen sharing: mostly slides, documents and demos, where sharpness matters more than smoothness.
     - At most 10 frames per second and 2.5 Mbps; when the network or computer is busy, drop frames, keep resolution
       (maintain-resolution), and tell the browser this is detailed content (contentHint=detail).
     - A single stream of up to 1920×1080 (720p made wide pages and small text blurry; still screens cost
       little extra bitrate at the higher resolution), without a low-quality fallback: on lossy links the browser underestimates bandwidth,
       and with a fallback layer the server would keep sending the blurry one. Screens are mostly still, so the
       bitrate is usually low anyway.
     - When the sharer's own upload is tight, the screen gets priority over the camera. */
  const SCREEN_FPS = 10;
  const SCREEN_CAPTURE = { resolution: { width: 1920, height: 1080, frameRate: SCREEN_FPS }, contentHint: 'detail' };
  const SCREEN_PUBLISH = {
    screenShareEncoding: { maxBitrate: 2_500_000, maxFramerate: SCREEN_FPS, priority: 'high' },
    simulcast: false,
    // VP9 keeps text sharper than VP8 at the same bitrate and has temporal layers (L1T3), so on packet loss the server
    // can drop frames instead of freezing. Viewers who can't decode VP9 get a VP8 copy (backupCodec), encoded only when needed.
    videoCodec: 'vp9', backupCodec: true,
    degradationPreference: 'maintain-resolution',
  };
  $('cAnno').onclick = () => HuddleAnno.open();
  $('cScreen').onclick = async () => {
    const on = !room.localParticipant.isScreenShareEnabled;
    await room.localParticipant.setScreenShareEnabled(on, on ? HuddleAnno.captureOptions(SCREEN_CAPTURE) : undefined, on ? SCREEN_PUBLISH : undefined)
      .catch((e) => { if (e.name !== 'NotAllowedError') toast(t('t.screen', { err: e.message })); });
    renderAll();
  };
  const panelOpen = () => !$('mBody').classList.contains('nopanel');
  function setPanel(open) {
    $('mBody').classList.toggle('nopanel', !open);
    $('cPanel').classList.toggle('on-accent', open);
    if (chatShown()) { chatUnread(false); const box = $('chatList'); box.scrollTop = box.scrollHeight; }
  }
  // New chat messages while the panel is closed: a dot on the "Members" button ("@" when you were mentioned)
  const unread = { chat: false, at: false };
  function chatUnread(on) { unread.chat = on; if (!on) unread.at = false; paintDots(); }
  function paintDots() {
    const dot = (el, on) => {
      let d = el.querySelector('.dot');
      if (on && !d) { d = document.createElement('span'); d.className = 'dot'; el.appendChild(d); }
      if (!on && d) d.remove();
    };
    dot($('cPanel'), unread.chat);
    const d = $('cPanel').querySelector('.dot');
    if (d) { d.classList.toggle('at', unread.at); d.textContent = unread.at ? '@' : ''; }
  }
  const chatShown = () => panelOpen();

  /* ================= chat (only within this meeting, never stored) ================= */
  const CHAT_MAX = 500;
  let chatLast = 0;
  const pad2 = (n) => String(n).padStart(2, '0');
  const linkify = (s) => esc(s).replace(/\bhttps?:\/\/[^\s<>"']+/g, (u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  // "@everyone" is recognised in every interface language (the sender writes it in their own language)
  const ALL_TOKENS = [...new Set(I18N.LANGS.map((l) => '@' + ((I18N.dict(l.code) || {})['chat.all'] || '')).filter((x) => x.length > 1))];
  // Find @tags left to right; at the same position the longest wins ("@Anna Lee" is not read as "@Anna")
  function scanTokens(text, tokens) {
    const toks = [...new Set(tokens.filter(Boolean))];
    const parts = []; let i = 0;
    while (i < text.length) {
      let best = -1, tok = '';
      for (const k of toks) { const j = text.indexOf(k, i); if (j >= 0 && (best < 0 || j < best || (j === best && k.length > tok.length))) { best = j; tok = k; } }
      if (best < 0) { parts.push([text.slice(i), false]); break; }
      if (best > i) parts.push([text.slice(i, best), false]);
      parts.push([tok, true]); i = best + tok.length;
    }
    return parts;
  }
  // Split the text into plain text (escaped, with links) and highlighted @tags
  const renderChatText = (text, tokens) => scanTokens(text, tokens).map(([s, at]) => (at ? `<span class="cm-at">${esc(s)}</span>` : linkify(s))).join('');
  function addChat({ name, identity, text, ts, mine, mentions = [], all = false }) {
    const box = $('chatList');
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    $('chatEmpty').classList.add('hidden');
    const d = new Date(ts);
    const me = room && room.localParticipant.identity;
    const toMe = !mine && (all || mentions.some((m) => m.id === me));
    const el = document.createElement('div');
    el.className = 'chat-msg' + (mine ? ' mine' : '') + (toMe ? ' to-me' : '');
    const tokens = mentions.map((m) => '@' + m.name).concat(all ? ALL_TOKENS : []);
    el.innerHTML = `<div class="cm-meta"><span class="cm-name" style="color:${mine ? 'var(--accent)' : color(identity)}">${esc(mine ? t('badge.me') : name)}</span><span class="cm-time">${pad2(d.getHours())}:${pad2(d.getMinutes())}</span></div><div class="cm-text">${renderChatText(text, tokens)}</div>`;
    box.appendChild(el);
    while (box.querySelectorAll('.chat-msg').length > 300) box.querySelector('.chat-msg').remove();   // keep the last 300
    if (atBottom || mine || toMe) box.scrollTop = box.scrollHeight;
    return toMe;
  }
  // A soft "ding-dong" when someone @mentions you
  let dingAc = null;
  function ding() {
    try {
      dingAc = dingAc || new (window.AudioContext || window.webkitAudioContext)();
      if (dingAc.state === 'suspended') dingAc.resume();
      const t0 = dingAc.currentTime + 0.02;
      [[1318.5, 0], [987.8, 0.13]].forEach(([f, dt]) => {
        const o = dingAc.createOscillator(), g = dingAc.createGain(); o.type = 'sine'; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t0 + dt); g.gain.exponentialRampToValueAtTime(0.12, t0 + dt + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dt + 0.5);
        o.connect(g); g.connect(dingAc.destination); o.start(t0 + dt); o.stop(t0 + dt + 0.55);
      });
    } catch {}
  }
  function onChat(p, d) {
    const text = String((d && d.text) || '').trim().slice(0, CHAT_MAX);
    if (!text) return;
    const name = p.name || p.identity;
    const mentions = Array.isArray(d.m) ? d.m.filter((m) => m && typeof m.id === 'string' && typeof m.name === 'string').slice(0, 50) : [];
    const toMe = addChat({ name, identity: p.identity, text, ts: Date.now(), mentions, all: !!d.all });
    const short = text.length > 60 ? text.slice(0, 60) + '…' : text;
    if (toMe) {   // mentioned: notify whether or not the panel is open
      toast(t('chat.mentioned', { name, text: short }), 6000);
      ding();
      if (!chatShown()) { unread.at = true; chatUnread(true); }
      return;
    }
    if (!chatShown()) {
      chatUnread(true);
      if (!panelOpen()) toast(`${name}: ${short}`);
    }
  }

  /* ---------- @mention picker ---------- */
  const picked = new Map();   // @name picked from the menu in this message → identity (decides between equal names)
  const people = () => room ? [room.localParticipant, ...room.remoteParticipants.values()] : [];
  let atState = null;         // { start, items, sel }
  function atQuery() {
    const inp = $('chatInput'), pos = inp.selectionStart ?? inp.value.length;
    const before = inp.value.slice(0, pos), k = before.lastIndexOf('@');
    if (k < 0) return null;
    const q = before.slice(k + 1);
    if (q.length > 24 || /[\n@]/.test(q) || (k > 0 && /[\w.]/.test(before[k - 1]))) return null;   // an @ inside an email address does not count
    return { start: k, q: q.toLowerCase() };
  }
  function renderAtMenu() {
    const box = $('atMenu');
    const qq = atQuery();
    if (!qq) { box.classList.add('hidden'); atState = null; return; }
    const meId = room.localParticipant.identity;
    const all = { id: '*', name: t('chat.all'), all: true };
    const list = [all, ...people().filter((p) => p.identity !== meId).map((p) => ({ id: p.identity, name: p.name || p.identity }))]
      .filter((x) => !qq.q || x.name.toLowerCase().includes(qq.q) || (x.all && ALL_TOKENS.some((tk) => tk.slice(1).toLowerCase().startsWith(qq.q))));
    if (!list.length) { box.classList.add('hidden'); atState = null; return; }
    const sel = atState && atState.start === qq.start ? Math.min(atState.sel, list.length - 1) : 0;
    atState = { start: qq.start, items: list, sel };
    box.innerHTML = list.slice(0, 8).map((x, i) => `<button type="button" class="at-opt${i === sel ? ' on' : ''}" data-i="${i}">${x.all ? '<span class="at-all">@</span>' : `<span class="at-av" style="background:${color(x.id)}">${esc(initial(x.name))}</span>`}<span>${esc(x.name)}</span></button>`).join('');
    box.classList.remove('hidden');
    box.querySelectorAll('.at-opt').forEach((b) => (b.onmousedown = (e) => { e.preventDefault(); pickAt(+b.dataset.i); }));
  }
  function pickAt(i) {
    if (!atState) return;
    const x = atState.items[i], inp = $('chatInput'), pos = inp.selectionStart ?? inp.value.length;
    const ins = '@' + x.name + ' ';
    inp.value = inp.value.slice(0, atState.start) + ins + inp.value.slice(pos);
    const caret = atState.start + ins.length;
    inp.setSelectionRange(caret, caret);
    if (!x.all) picked.set(x.name, x.id);
    $('atMenu').classList.add('hidden'); atState = null;
    inp.focus();
  }
  $('chatInput').addEventListener('input', renderAtMenu);
  $('chatInput').addEventListener('click', renderAtMenu);
  $('chatInput').addEventListener('blur', () => setTimeout(() => { $('atMenu').classList.add('hidden'); atState = null; }, 150));
  $('chatInput').addEventListener('keydown', (e) => {
    if (!atState) return;
    const n = Math.min(atState.items.length, 8);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); atState.sel = (atState.sel + (e.key === 'ArrowDown' ? 1 : n - 1)) % n; renderAtMenu(); }
    else if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pickAt(atState.sel); }
    else if (e.key === 'Escape') { e.preventDefault(); $('atMenu').classList.add('hidden'); atState = null; }
  });
  // Before sending, find who is mentioned: picked names count as picked; a typed @name that exactly matches someone counts too
  function collectMentions(text) {
    const meId = room.localParticipant.identity;
    const byName = new Map();   // name → [identity] (picked names take priority)
    for (const p of people()) { if (p.identity === meId) continue; const nm = p.name || p.identity; byName.set(nm, [...(byName.get(nm) || []), p.identity]); }
    for (const [nm, id] of picked) byName.set(nm, [id]);
    const found = new Set(scanTokens(text, [...[...byName.keys()].map((n) => '@' + n), ...ALL_TOKENS]).filter(([, at]) => at).map(([s]) => s));
    const out = [];
    for (const [nm, ids] of byName) if (found.has('@' + nm)) ids.forEach((id) => out.push({ id, name: nm }));
    return { mentions: out, all: ALL_TOKENS.some((k) => found.has(k)) };
  }
  $('chatForm').onsubmit = async (e) => {
    e.preventDefault();
    if (atState) return;   // Enter picks from the menu while it is open
    const inp = $('chatInput'), text = inp.value.trim().slice(0, CHAT_MAX);
    if (!text || !room) return;
    if (Date.now() - chatLast < 700) { toast(t('chat.slow')); return; }   // no flooding
    chatLast = Date.now();
    const { mentions, all } = collectMentions(text);
    const msg = { text };
    if (mentions.length) msg.m = mentions;
    if (all) msg.all = true;
    try {
      await room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(msg)), { reliable: true, topic: 'hudd.chat' });
      addChat({ name: room.localParticipant.name, identity: room.localParticipant.identity, text, ts: Date.now(), mine: true, mentions, all });
      inp.value = ''; picked.clear();
    } catch (err) { toast(err.message); }
  };
  $('cPanel').onclick = () => setPanel(!panelOpen());

  $('mInvite').onclick = async () => {
    const local = ['localhost', '127.0.0.1'].includes(location.hostname);
    const base = local && config.share_base ? config.share_base : location.origin;
    const pwd = hostLike() ? hostPwd() : '';
    const link = `${base}/r/${code}` + (pwd ? `?pwd=${encodeURIComponent(pwd)}` : '');
    const text = pwd ? t('invite.textPwd', { title: roomInfo.title, code: fmtCode(code), link, pwd })
      : t('invite.text', { title: roomInfo.title, code: fmtCode(code), link });
    toast((await copy(text)) ? t('t.inviteCopied') : link, 4000);
  };

  /* ================= leave / end ================= */
  // "Back" during a meeting: the host gets the leave dialog; others must press it twice (no accidental exits)
  let lastBack = 0;
  function guardBack() {
    if (!(history.state && history.state.huddGuard)) history.pushState({ huddGuard: 1 }, '');
  }
  window.addEventListener('popstate', () => {
    if (!room || $('meeting').classList.contains('hidden')) return;
    history.pushState({ huddGuard: 1 }, '');
    if (isOwnerRole()) { $('leaveModal').classList.remove('hidden'); return; }
    if (Date.now() - lastBack < 2500) { $('cLeave').click(); return; }
    lastBack = Date.now();
    toast(t('m.backAgain'), 2500);
  });
  $('cLeave').onclick = () => {
    if (!isOwnerRole()) { leaving = true; room.disconnect(); return; }
    $('leaveModal').classList.remove('hidden');
  };
  $('lmCancel').onclick = () => $('leaveModal').classList.add('hidden');
  $('lmLeave').onclick = () => { $('leaveModal').classList.add('hidden'); leaving = true; room.disconnect(); };
  $('lmEnd').onclick = async () => {
    const b = $('lmEnd'); b.disabled = true;
    try {
      await api(`/api/rooms/${code}/end`, { owner_key: ownerKey });
      leaving = 'end';
      $('leaveModal').classList.add('hidden');
      await room.disconnect();
    } catch (e) { toast(e.message); b.disabled = false; }
  };

  async function onDisconnected(reason) {
    document.querySelectorAll('audio').forEach((a) => a.remove());
    if (leaving === 'end' || reason === LK.DisconnectReason?.ROOM_DELETED) {
      return showEnded({ title: () => t('ed.ended'), sub: () => (leaving === 'end' ? roomSub() : t('ed.byHost')) });
    }
    // Not sure why we were disconnected: if the meeting no longer exists, the host ended it
    let gone = false; try { await api(`/api/rooms/${code}`); } catch (e) { gone = e.status === 404; }
    if (gone) return showEnded({ title: () => t('ed.ended'), sub: () => t('ed.byHost') });
    const wasLeaving = leaving;
    showEnded({ title: () => (wasLeaving ? t('ed.left') : t('ed.lost')), sub: roomSub, rejoin: true });
  }

  let ended = null;      // what the end screen shows (repainted when the language changes)
  const val = (x) => (typeof x === 'function' ? x() : x || '');
  function paintEnded() {
    if (!ended) return;
    $('edTitle').textContent = val(ended.title);
    $('edSub').textContent = val(ended.sub);
    const rj = $('edRejoin'); if (rj) rj.textContent = t('ed.rejoin');
  }
  function showEnded({ title, sub, rejoin }) {
    show('ended');
    ended = { title, sub };
    paintEnded();
    $('edStatus').innerHTML = '';
    if (rejoin) {
      const b = document.createElement('button'); b.className = 'btn'; b.id = 'edRejoin'; b.textContent = t('ed.rejoin');
      b.onclick = () => location.reload();
      $('edStatus').appendChild(b);
    }
  }

  // Language switch: repaint the dynamic text
  I18N.onChange(() => {
    if (window.HuddleAnno) HuddleAnno.relabel();
    if (!$('prejoin').classList.contains('hidden')) relabelPrejoin();
    if (room && !$('meeting').classList.contains('hidden')) { $('mCode').textContent = codeLabel(); renderAll(); }
    if (!$('ended').classList.contains('hidden')) paintEnded();
  });

  window.addEventListener('beforeunload', () => { if (room) room.disconnect(); });
  init();
})();
