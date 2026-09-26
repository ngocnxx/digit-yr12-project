// Router that shows the right screen based on the URL hash and login state.


import { api, clearToken, getToken } from './api.js';
import { $, hide, show, toast } from './dom.js';
import { state } from './state.js';
import { trace } from './debug.js'; // debug tracer (on with ?debug=1)
import { hydrateAuth } from './screens/auth.js';
import { hydrateOnboarding } from './screens/onboarding.js';
import { renderDashboard } from './screens/dashboard.js';
import { renderSubjectDetail } from './screens/subject-detail.js';
import { renderSettings } from './screens/settings.js';

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
  // Trace what the router is doing each time it runs
  trace('router: route()', { hash: location.hash || '#', hasToken: !!getToken() });

  // No token -> not logged in -> show auth.
  if (!getToken()) {
    trace('router: no token → showing AUTH screen');
    state.currentUser = null;
    hide($('#topbar'));
    showScreen('screen-auth');
    hydrateAuth();
    return;
  }

  // No user info yet, so fetch it from the server
  if (!state.currentUser) {
    try {
      state.currentUser = (await api('GET', '/api/auth/me')).user;
    } catch (e) {
      // Server not running (status 0) is not the same as a bad login.
      // Keep the token so the student stays signed in once the server is back.
      if (e.status === 0) {
        trace('router: server is down, keeping the token');
        hide($('#topbar'));
        showScreen('screen-auth');
        hydrateAuth();
        return;
      }
      clearToken(); // the token really was rejected, so sign out
      return route();
    }
  }

  // Still setting up? Send to onboarding
  if (!state.currentUser.onboarding_done) {
    trace('router: logged in, onboarding not done → ONBOARDING screen');
    hide($('#topbar'));
    showScreen('screen-onboarding');
    hydrateOnboarding();
    return;
  }
  trace('router: logged in + onboarded → DASHBOARD');

  // Logged in and ready, show the right screen
  show($('#topbar'));
  const hash = location.hash || '#dashboard';
  try {
    if (hash === '#settings') {
      showScreen('screen-settings');
      await renderSettings();
    } else if (hash.startsWith('#subject-')) {
      showScreen('screen-subject');
      await renderSubjectDetail(hash.slice('#subject-'.length));
    } else {
      showScreen('screen-dashboard');
      await renderDashboard();
    }
  } catch (e) {
    toast(e.message || 'Something went wrong');
  }
}
