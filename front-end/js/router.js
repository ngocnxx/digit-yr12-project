// Hash router — decides which screen is visible based on auth + onboarding
// state and the current hash. Runs once on load and again on every hashchange.

import { api, clearToken, getToken } from './api.js';
import { $, hide, show, toast } from './dom.js';
import { state } from './state.js';
import { hydrateAuth } from './screens/auth.js';
import { hydrateOnboarding } from './screens/onboarding.js';
import { renderDashboard } from './screens/dashboard.js';

const SCREENS = [
  'screen-auth',
  'screen-onboarding',
  'screen-dashboard',
  'screen-subject',
  'screen-settings',
];

export function showScreen(id) {
  SCREENS.forEach((s) => {
    const el = document.getElementById(s);
    if (el) el.classList.toggle('hidden', s !== id);
  });
}

export function navigate(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

export async function route() {
  // No token → not logged in → show auth.
  if (!getToken()) {
    state.currentUser = null;
    hide($('#topbar'));
    showScreen('screen-auth');
    hydrateAuth();
    return;
  }

  // Have a token but no user object yet → fetch it (token may be expired).
  if (!state.currentUser) {
    try {
      state.currentUser = (await api('GET', '/api/auth/me')).user;
    } catch {
      clearToken();
      return route();
    }
  }

  // Logged in but onboarding not finished → onboarding flow.
  if (!state.currentUser.onboarding_done) {
    hide($('#topbar'));
    showScreen('screen-onboarding');
    hydrateOnboarding();
    return;
  }

  // Fully logged in — show topbar and route by hash.
  show($('#topbar'));
  const hash = location.hash || '#dashboard';
  try {
    if (hash === '#settings') {
      showScreen('screen-settings');
    } else if (hash.startsWith('#subject-')) {
      showScreen('screen-subject');
    } else {
      showScreen('screen-dashboard');
      await renderDashboard();
    }
  } catch (e) {
    toast(e.message || 'Something went wrong');
  }
}
