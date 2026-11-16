/* Home page: start a meeting, or join one by ID or link. */
(() => {
  const { store, api, parseCode } = Util;
  const $ = (id) => document.getElementById(id);
  const t = I18N.t;
  $('cNick').value = store.get('hudd.profile', {}).nickname || '';

  // Footer link to the source code (set by the server; hidden when empty)
  const src = (window.APP && window.APP.source) || '';
  $('srcLink').href = src; $('srcLink').classList.toggle('hidden', !src);
  if (!src) $('srcLink').previousSibling.textContent = '';

  let config = {};
  function render() {
    const pass = !!config.require_passcode;
    $('cPassWrap').classList.toggle('hidden', !pass); $('cPass').required = pass;
    if (pass && !$('cPass').value) $('cPass').value = store.get('hudd.passcode', '');
    $('mockTitle').textContent = `${t('mock.title')} · ${t('m.code', { code: '482 913 650' })}`;
  }
  api('/api/config').then((c) => { config = c; render(); }).catch(() => {});
  render();
  I18N.onChange(render);

  // Meeting password: prefilled with the one used last time (change or clear it for each meeting)
  $('cRoomPass').value = store.get('hudd.lastRoomPass', '');

  // "New meeting" opens a small dialog (name; topic and meeting password under "More options")
  const box = $('newBox');
  const openNew = () => {
    box.classList.remove('hidden'); $('cErr').textContent = '';
    if ($('cTitle').value || $('cRoomPass').value) $('cMore').open = true;
    const first = [$('cNick'), $('cPass')].find((x) => x.offsetParent && !x.value);
    (first || $('createBtn')).focus();
  };
  const closeNew = () => box.classList.add('hidden');
  $('newBtn').onclick = openNew;
  $('newClose').onclick = closeNew;
  Util.onBackdrop(box, closeNew);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.classList.contains('hidden')) closeNew(); });
  const qs = new URLSearchParams(location.search);
  if (qs.get('new') === '1') openNew();

  // Join: only the meeting ID or link here; name and password are asked on the meeting's own page (with a camera preview)
  if (qs.get('code')) $('jCode').value = qs.get('code');
  const qsPwd = qs.get('pwd');
  const pwdFromLink = (s) => { const m = String(s || '').match(/[?&]pwd=([^&#\s]+)/); if (!m) return null; try { return decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch { return m[1]; } };

  $('createForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('createBtn'); btn.disabled = true; $('cErr').textContent = '';
    const body = { nickname: $('cNick').value.trim(), title: $('cTitle').value.trim() || null, passcode: $('cPass').value || null, room_pass: $('cRoomPass').value.trim() };
    try {
      const res = await api('/api/rooms', body);
      store.set('hudd.profile', Object.assign(store.get('hudd.profile', {}), { nickname: body.nickname }));
      if (body.passcode) store.set('hudd.passcode', body.passcode);
      store.set('hudd.lastRoomPass', body.room_pass);
      // Host key (and password) for this meeting, kept in this browser; only the latest 50 meetings are kept
      const remember = (k, v) => { const m = store.get(k, {}); m[res.room.code] = v; store.set(k, Object.fromEntries(Object.entries(m).slice(-50))); };
      remember('hudd.ownerKeys', res.owner_key);
      if (body.room_pass) remember('hudd.hostPwd', body.room_pass);
      store.sset('hudd.join.' + res.room.code, res);
      location.href = '/r/' + res.room.code;
    } catch (err) { $('cErr').textContent = err.message; btn.disabled = false; }
  });

  $('joinForm').addEventListener('submit', (e) => {
    e.preventDefault();
    $('jErr').textContent = '';
    const raw = $('jCode').value;
    const code = parseCode(raw);
    if (!code) { $('jErr').textContent = t('err.code9'); $('jCode').focus(); return; }
    const pwd = pwdFromLink(raw) || qsPwd || '';
    if (pwd) store.sset('hudd.pwd.' + code, pwd);
    location.href = '/r/' + code;
  });
})();
