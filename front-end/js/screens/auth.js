// Auth screen (#screen-auth) — login + create-account forms.
//
// Responsibilities: read the form inputs, run cheap client-side validation, call
// the auth API (mock or Flask via api()), and on success store the JWT and route
// to the dashboard. Every failure surfaces as a friendly message in the screen's
// `.error-msg` slot — never a blank screen or a raw error.
//
// Behaviour is attached through `data-action` attributes, dispatched by the single
// delegated click handler in main.js (e.g. data-action="do-login" → doLogin), so
// the HTML stays free of inline JS. Full event flow: docs/design/auth-screen.md.

import { api, setToken } from '../api.js';
import { $, $$, hide, show, withPending } from '../dom.js';
import { state } from '../state.js';
import { navigate } from '../router.js';

// Mirrors the backend's minimum; the server re-checks, this is just fast feedback.
const MIN_PASSWORD_LEN = 4;

// Reset the screen to a clean slate every time it is (re)entered: default to the
// login tab, clear all fields, hide any leftover error. Called by route().
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

// Switch between the login and signup tabs: highlight the active tab and reveal
// the matching form (the other is hidden). Records the mode so the Enter-key
// shortcut in main.js knows which form to submit.
export function setAuthMode(mode) {
  state.authMode = mode;
  $$('.auth-tabs button').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  $('#auth-login').classList.toggle('hidden', mode !== 'login');
  $('#auth-signup').classList.toggle('hidden', mode !== 'signup');
}

// Handle a "Sign in" click. `btn` is the clicked button so withPending() can
// disable it and show a pending label for the duration of the request (which both
// gives feedback and prevents a double-submit).
export async function doLogin(btn) {
  const err = $('#login-err');
  hide(err);

  // Layer 1 — client-side guard: avoid a pointless round-trip on empty input.
  const email = $('#login-email').value.trim();
  const password = $('#login-pw').value;
  if (!email || !password) {
    err.textContent = 'Please enter email and password.';
    show(err);
    return;
  }

  try {
    // Layer 2 — the backend authenticates. On success it returns { token, user }.
    const r = await withPending(btn, 'Signing in…', () =>
      api('POST', '/api/auth/login', { email, password }),
    );
    setToken(r.token); // persist the JWT (localStorage: ncea_token)
    state.currentUser = r.user;
    navigate('#dashboard');
  } catch (e) {
    // 401 (bad credentials), 400, or a network/timeout error — all friendly here.
    err.textContent = e.message || 'Login failed.';
    show(err);
  }
}

// Handle a "Create account" click. Runs three client-side guards (required fields,
// passwords match, min length) BEFORE the network call; the backend still
// re-validates everything and owns duplicate-email detection (→ 400).
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
    // New accounts come back with onboarding_done = 0, so route() will send the
    // user to onboarding (not the dashboard) on the next pass.
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
