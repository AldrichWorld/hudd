/* Shared helpers for all pages */
const Util = (() => {
  const url = (p) => p;
  const store = {
    get(k, d = null) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
    sget(k) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : null; } catch { return null; } },
    sset(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch {} },
    sdel(k) { try { sessionStorage.removeItem(k); } catch {} },
  };

  async function api(path, body, method, headers) {
    const opt = { method: method || (body ? 'POST' : 'GET'), headers: Object.assign({ 'X-Lang': I18N.lang }, headers || {}) };
    if (body) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    const r = await fetch(url(path), opt);
    let data = null;
    try { data = await r.json(); } catch {}
    if (!r.ok) {
      let msg = data && data.detail;
      if (Array.isArray(msg)) msg = I18N.t('err.check');
      const err = new Error(msg || I18N.t('err.request', { status: r.status }));
      err.status = r.status;
      throw err;
    }
    return data;
  }

  // A meeting ID is 9 digits; accept it with spaces, or a whole invite link
  const parseCode = (s) => {
    const m = String(s || '').match(/\/r\/(\d{9})(?!\d)/);
    if (m) return m[1];
    const d = String(s || '').replace(/\D/g, '');
    return d.length === 9 ? d : null;
  };
  const fmtCode = (c) => `${c.slice(0, 3)} ${c.slice(3, 6)} ${c.slice(6)}`;   // 123 456 789

  const COLORS = ['#3d7bfd', '#8e4ec6', '#e5484d', '#30a46c', '#f5a524', '#0091ff', '#d6409f', '#12a594', '#6e56cf', '#e54666'];
  const color = (s) => { let h = 0; for (const ch of String(s)) h = (h * 31 + ch.codePointAt(0)) >>> 0; return COLORS[h % COLORS.length]; };
  const initial = (name) => (String(name || '?').trim()[0] || '?').toUpperCase();
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function toast(msg, ms = 3000) {
    let box = document.querySelector('.toast-box');
    if (!box) { box = document.createElement('div'); box.className = 'toast-box'; document.body.appendChild(box); }
    const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; box.appendChild(t);
    setTimeout(() => t.remove(), ms);
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch {}
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch {}
    ta.remove(); return ok;
  }

  // Close a dialog by clicking its backdrop, but only when both press and release happen on the backdrop:
  // selecting text in an input and releasing outside the dialog also fires a click there.
  function onBackdrop(bg, close) {
    let downOnBg = false;
    bg.addEventListener('pointerdown', (e) => { downOnBg = e.target === bg; });
    bg.addEventListener('click', (e) => { if (e.target === bg && downOnBg) close(); downOnBg = false; });
  }
  return { store, api, parseCode, fmtCode, color, initial, esc, toast, copy, url, onBackdrop };
})();

/* Going "back" on phones may restore a page from the back/forward cache with stale buttons and a dead
   meeting connection. Reload it to get a fresh state. */
window.addEventListener('pageshow', (e) => { if (e.persisted) location.reload(); });

/* ================= PWA: install as a desktop or phone app =================
   - Every page registers the service worker (needed to be installable; shows a notice when offline)
   - The home page "Install app" button: Chrome / Edge / Android open the system install dialog;
     iPhone, iPad and Mac Safari cannot be triggered from a page, so we show step-by-step instructions */
(() => {
  if ('serviceWorker' in navigator && window.isSecureContext) {
    addEventListener('load', () => navigator.serviceWorker.register(Util.url('/sw.js'), { scope: Util.url('/') }).catch(() => {}));
  }
  const standalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (navigator.maxTouchPoints > 1 && /Macintosh/.test(ua));
  const macSafari = !ios && /Macintosh/.test(ua) && /Safari\//.test(ua) && !/Chrome|Chromium|Edg|Firefox/.test(ua);
  const android = /Android/.test(ua);
  let deferred = null;
  const btn = () => document.getElementById('installBtn');
  const show = (on) => { const b = btn(); if (b) b.classList.toggle('hidden', !on || standalone()); };
  addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e; show(true); });
  addEventListener('appinstalled', () => { deferred = null; show(false); });
  function guide(kind) {
    const t = I18N.t;
    let m = document.getElementById('pwaGuide');
    if (!m) {
      m = document.createElement('div'); m.id = 'pwaGuide'; m.className = 'modal-bg pwa-guide';
      Util.onBackdrop(m, () => m.remove());
      document.body.appendChild(m);
    }
    const share = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M6 11v9h12v-9"/></svg>';
    const steps = kind === 'ios' ? [t('pwa.ios1', { icon: '§' }), t('pwa.ios2'), t('pwa.ios3')]
      : kind === 'android' ? [1, 2, 3, 4, 5].map((i) => t(`pwa.and${i}`))
        : [t('pwa.mac1'), t('pwa.mac2')];
    m.innerHTML = `<div class="modal"><h3>${Util.esc(t('pwa.guideTitle'))}</h3>
      <ol class="pg-steps">${steps.map((s, i) => `<li><div class="pg-txt"><span class="pg-n">${i + 1}</span><span>${Util.esc(s).replace('§', share)}</span></div></li>`).join('')}</ol>
      <div class="sub">${Util.esc(t('pwa.guideNote'))}</div><button class="btn block" type="button">${Util.esc(t('pwa.ok'))}</button></div>`;
    m.querySelector('button').onclick = () => m.remove();
  }
  addEventListener('DOMContentLoaded', () => {
    const b = btn();
    if (!b || standalone()) return;
    if (ios || macSafari || android) show(true);   // these browsers may never fire the install event: the button shows instructions
    b.onclick = async () => {
      if (deferred) { deferred.prompt(); const r = await deferred.userChoice.catch(() => null); if (r && r.outcome === 'accepted') show(false); deferred = null; return; }
      guide(ios ? 'ios' : android ? 'android' : 'mac');
    };
  });
  Util.pwa = { standalone, guide };
})();
