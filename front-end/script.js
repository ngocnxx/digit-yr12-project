'use strict';

/* ==========================================================================
   §1  SERVER COMMUNICATION
   ========================================================================== */

const TOKEN_KEY  = 'ncea_token';
const getToken   = () => localStorage.getItem(TOKEN_KEY);
const setToken   = (t) => localStorage.setItem(TOKEN_KEY, t);
const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function api(method, path, body) {
  const opts = { method, headers: {} };
  const tok = getToken();
  if (tok) opts.headers['Authorization'] = 'Bearer ' + tok;
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* empty body is fine */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ==========================================================================
   §2  STATE
   ========================================================================== */

let currentUser   = null;
let authMode      = 'login';
let obStep        = 1;
let obCreatedSubject = null;
let obAddedTopics = [];

const DEFAULT_TOPIC_EMOJI = '📚';

/* ==========================================================================
   §3  DOM HELPERS
   ========================================================================== */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function show(el) { if (el) el.classList.remove('hidden'); }
function hide(el) { if (el) el.classList.add('hidden'); }

function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

let toastTimer = null;
function toast(msg) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  void el.offsetWidth;          // force reflow so transition re-fires
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
}

/* ==========================================================================
   §4  MODAL PLUMBING
   ========================================================================== */

function openModalFromHTML(html) {
  const ov = $('#modal-overlay');
  ov.innerHTML = html;
  ov.classList.add('show');
  ov.onclick = (e) => { if (e.target === ov) closeModal(); };
  return ov;
}

function closeModal() {
  const ov = $('#modal-overlay');
  ov.classList.remove('show');
  ov.onclick = null;
  setTimeout(() => { if (!ov.classList.contains('show')) ov.innerHTML = ''; }, 220);
}

/* ==========================================================================
   §5  ROUTER
   --------------------------------------------------------------------------
   The key fix: every screen starts hidden in HTML. route() is the ONLY thing
   that decides which screen to show. It runs on DOMContentLoaded (via init)
   and again on every hashchange. Without init() being called, route() never
   runs and everything stays hidden — which was the blank screen bug.
   ========================================================================== */

const SCREENS = [
  'screen-auth', 'screen-onboarding', 'screen-dashboard',
  'screen-subject', 'screen-settings'
];

function showScreen(id) {
  SCREENS.forEach(s => {
    const el = document.getElementById(s);
    if (el) el.classList.toggle('hidden', s !== id);
  });
}

function navigate(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

async function route() {
  // No token → not logged in → show auth screen
  if (!getToken()) {
    currentUser = null;
    hide($('#topbar'));
    showScreen('screen-auth');
    hydrateAuth();
    return;
  }

  // Have a token but no user object yet → fetch it
  if (!currentUser) {
    try {
      currentUser = (await api('GET', '/api/auth/me')).user;
    } catch {
      clearToken();
      return route();
    }
  }

  // Logged in but hasn't finished onboarding
  if (!currentUser.onboarding_done) {
    hide($('#topbar'));
    showScreen('screen-onboarding');
    hydrateOnboarding();
    return;
  }

  // Fully logged in — show topbar and route by hash
  show($('#topbar'));
  const hash = location.hash || '#dashboard';
  try {
    if      (hash === '#settings')             { showScreen('screen-settings'); }
    else if (hash.startsWith('#subject-'))     { showScreen('screen-subject'); }
    else                                       { showScreen('screen-dashboard'); }
  } catch (e) { toast(e.message || 'Something went wrong'); }
}

/* ==========================================================================
   §6  AUTH SCREEN
   ========================================================================== */

function hydrateAuth() {
  setAuthMode('login');
  ['login-email','login-pw','signup-name','signup-email','signup-pw','signup-pw2']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  hide($('#login-err'));
  hide($('#signup-err'));
}

function setAuthMode(mode) {
  authMode = mode;
  $$('.auth-tabs button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  $('#auth-login').classList.toggle('hidden', mode !== 'login');
  $('#auth-signup').classList.toggle('hidden', mode !== 'signup');
}

async function doLogin() {
  const err = $('#login-err');
  hide(err);
  try {
    const email    = $('#login-email').value.trim();
    const password = $('#login-pw').value;
    if (!email || !password) {
      err.textContent = 'Please enter email and password.';
      show(err); return;
    }
    const r = await api('POST', '/api/auth/login', { email, password });
    setToken(r.token); currentUser = r.user; navigate('#dashboard');
  } catch (e) {
    err.textContent = e.message || 'Login failed.'; show(err);
  }
}

async function doSignup() {
  const err = $('#signup-err');
  hide(err);
  try {
    const name      = $('#signup-name').value.trim();
    const email     = $('#signup-email').value.trim();
    const password  = $('#signup-pw').value;
    const password2 = $('#signup-pw2').value;
    const yearLevel = $('#signup-year').value;
    if (!name || !email || !password) {
      err.textContent = 'Please fill in all required fields.'; show(err); return;
    }
    if (password !== password2) {
      err.textContent = "Passwords don't match."; show(err); return;
    }
    if (password.length < 4) {
      err.textContent = 'Password must be at least 4 characters.'; show(err); return;
    }
    const r = await api('POST', '/api/auth/signup', { name, email, yearLevel, password });
    setToken(r.token); currentUser = r.user; navigate('#dashboard');
  } catch (e) {
    err.textContent = e.message || 'Signup failed.'; show(err);
  }
}

/* ==========================================================================
   §7  ONBOARDING
   ========================================================================== */

function hydrateOnboarding() {
  obStep = 1; obCreatedSubject = null; obAddedTopics = [];
  obRender();
}

function obRender() {
  // Update progress dots
  $$('#ob-dots .dot').forEach((d, i) => {
    d.classList.toggle('done',   i + 1 < obStep);
    d.classList.toggle('active', i + 1 === obStep);
  });
  // Show only the current step
  [1, 2, 3].forEach(n => {
    document.getElementById('ob-step-' + n).classList.toggle('hidden', n !== obStep);
  });
  // Wire subject dropdown custom field toggle
  const sel = $('#ob-subj-select');
  if (sel) sel.onchange = () => {
    $('#ob-custom-field').classList.toggle('hidden', sel.value !== '__custom__');
  };
  // If on step 3, update the subject name heading and re-render chips
  if (obStep === 3) {
    $('#ob-subject-name').textContent = obCreatedSubject ? obCreatedSubject.name : 'your subject';
    renderObChips();
  }
}

function renderObChips() {
  const wrap = $('#ob-topic-chips');
  if (!obAddedTopics.length) {
    wrap.innerHTML = '<span class="muted small">No topics added yet — you can add them later too.</span>';
    return;
  }
  wrap.innerHTML = obAddedTopics.map((name, i) =>
    `<span class="topic-chip">${esc(name)}
       <span class="chip-remove" data-ob-remove="${i}">✕</span>
     </span>`
  ).join('');
  $$('#ob-topic-chips .chip-remove').forEach(x => {
    x.onclick = () => { obAddedTopics.splice(+x.dataset.obRemove, 1); renderObChips(); };
  });
}

async function obAddSubject() {
  const sel = $('#ob-subj-select');
  if (!sel.value) { toast('Pick a subject first'); return; }
  let name, emoji, colour;
  if (sel.value === '__custom__') {
    name = $('#ob-custom').value.trim();
    if (!name) { toast('Type a subject name'); return; }
    emoji = '📘'; colour = undefined;
  } else {
    const opt = sel.selectedOptions[0];
    name = sel.value; emoji = opt.dataset.emoji; colour = opt.dataset.colour;
  }
  try {
    const r = await api('POST', '/api/subjects', { name, emoji, colour });
    obCreatedSubject = r.subject; obStep = 3; obRender();
  } catch (e) { toast(e.message); }
}

function obAddTopic() {
  const input = $('#ob-topic-input');
  const name = input.value.trim();
  if (!name) return;
  obAddedTopics.push(name);
  input.value = '';
  renderObChips();
  input.focus();
}

async function obFinish() {
  try {
    if (obCreatedSubject) {
      for (const name of obAddedTopics) {
        await api('POST', '/api/topics', {
          subjectId: obCreatedSubject.id, name, emoji: DEFAULT_TOPIC_EMOJI
        });
      }
    }
    await finishOnboarding();
  } catch (e) { toast(e.message); }
}

async function obSkip() { await finishOnboarding(); }

async function finishOnboarding() {
  await api('PUT', '/api/user/onboarding');
  currentUser.onboarding_done = 1;
  obStep = 1; obCreatedSubject = null; obAddedTopics = [];
  navigate('#dashboard');
}

/* ==========================================================================
   §8  GLOBAL CLICK HANDLER  (event delegation)
   --------------------------------------------------------------------------
   One listener on document.body reads data-action from every click and calls
   the right function. This is why the buttons work — without this, data-action
   is just an HTML label that does nothing on its own.
   ========================================================================== */

document.body.addEventListener('click', async (e) => {
  // Let modals manage their own internal clicks first
  if (e.target.closest('#modal-overlay')) {
    if (e.target.closest('[data-action="modal-cancel"]')) closeModal();
    return;
  }

  const act = e.target.closest('[data-action]');
  if (!act) return;
  const action = act.dataset.action;

  try {
    switch (action) {
      // Auth
      case 'auth-tab':  setAuthMode(act.dataset.mode); break;
      case 'do-login':  await doLogin();  break;
      case 'do-signup': await doSignup(); break;

      // Onboarding
      case 'ob-next':        obStep = 2; obRender(); break;
      case 'ob-add-subject': await obAddSubject(); break;
      case 'ob-skip':        await obSkip();  break;
      case 'ob-back':        obStep = 2; obRender(); break;
      case 'ob-add-topic':   obAddTopic(); break;
      case 'ob-finish':      await obFinish(); break;

      // Navigation (stubs — will expand later)
      case 'nav-dashboard': navigate('#dashboard'); break;
      case 'nav-settings':  navigate('#settings');  break;
      case 'do-logout':
        try { await api('POST', '/api/auth/logout'); } catch {}
        clearToken(); currentUser = null; navigate('#'); route(); break;
    }
  } catch (err) {
    toast(err.message || 'Something went wrong');
  }
});

/* ==========================================================================
   §9  KEYBOARD SHORTCUTS
   ========================================================================== */

document.addEventListener('keydown', (e) => {
  // Escape closes any open modal
  if (e.key === 'Escape') {
    if ($('#modal-overlay').classList.contains('show')) closeModal();
    return;
  }
  // Enter submits the auth form
  if (e.key === 'Enter' && !$('#screen-auth').classList.contains('hidden')) {
    if (authMode === 'login') doLogin(); else doSignup();
  }
  // Enter adds a topic in onboarding step 3
  if (e.key === 'Enter' && document.activeElement?.id === 'ob-topic-input') {
    obAddTopic();
  }
});

/* ==========================================================================
   §10  STARTUP
   --------------------------------------------------------------------------
   THE KEY FIX: init() registers the hashchange listener and calls route()
   once on page load. Without this, the router never runs — all screens stay
   hidden and the page is blank. The DOMContentLoaded guard ensures the HTML
   is fully parsed before we try to query any elements.
   ========================================================================== */

function init() {
  window.addEventListener('hashchange', route);
  route();   // run immediately to show the right screen on first load
}

// If the HTML is still being parsed, wait. If it's already done, run now.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}