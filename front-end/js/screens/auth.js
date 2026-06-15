// Auth screen — login / signup forms.

import { api, setToken } from '../api.js';
import { $, $$, hide, show, withPending } from '../dom.js';
import { state } from '../state.js';
import { navigate } from '../router.js';

const MIN_PASSWORD_LEN = 4;

export function hydrateAuth() {
  setAuthMode('login');
  ['login-email', 'login-pw', 'signup-name', 'signup-email', 'signup-pw', 'signup-pw2'].forEach(
    (id) => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    },
  );
  hide($('#login-err'));
  hide($('#signup-err'));
}

export function setAuthMode(mode) {
  state.authMode = mode;
  $$('.auth-tabs button').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  $('#auth-login').classList.toggle('hidden', mode !== 'login');
  $('#auth-signup').classList.toggle('hidden', mode !== 'signup');
}

export async function doLogin(btn) {
  const err = $('#login-err');
  hide(err);
  const email = $('#login-email').value.trim();
  const password = $('#login-pw').value;
  if (!email || !password) {
    err.textContent = 'Please enter email and password.';
    show(err);
    return;
  }
  try {
    const r = await withPending(btn, 'Signing in…', () =>
      api('POST', '/api/auth/login', { email, password }),
    );
    setToken(r.token);
    state.currentUser = r.user;
    navigate('#dashboard');
  } catch (e) {
    err.textContent = e.message || 'Login failed.';
    show(err);
  }
}

export async function doSignup(btn) {
  const err = $('#signup-err');
  hide(err);
  const name = $('#signup-name').value.trim();
  const email = $('#signup-email').value.trim();
  const password = $('#signup-pw').value;
  const password2 = $('#signup-pw2').value;
  const yearLevel = $('#signup-year').value;

  if (!name || !email || !password) {
    err.textContent = 'Please fill in all required fields.';
    show(err);
    return;
  }
  if (password !== password2) {
    err.textContent = "Passwords don't match.";
    show(err);
    return;
  }
  if (password.length < MIN_PASSWORD_LEN) {
    err.textContent = `Password must be at least ${MIN_PASSWORD_LEN} characters.`;
    show(err);
    return;
  }

  try {
    const r = await withPending(btn, 'Creating account…', () =>
      api('POST', '/api/auth/signup', { name, email, yearLevel, password }),
    );
    setToken(r.token);
    state.currentUser = r.user;
    navigate('#dashboard');
  } catch (e) {
    err.textContent = e.message || 'Signup failed.';
    show(err);
  }
}
