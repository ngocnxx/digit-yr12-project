// Composition root — imports every screen handler, wires one delegated click
// listener + keyboard shortcuts, and starts the router. This is the only script
// the HTML loads (`<script type="module" src="js/main.js">`).

import { api, clearToken } from './api.js';
import { $, closeModal, toast } from './dom.js';
import { state } from './state.js';
import { navigate, route } from './router.js';
import { doLogin, doSignup, setAuthMode } from './screens/auth.js';
import {
  obAddSubject,
  obAddTopic,
  obFinish,
  obNext,
  obSkip,
} from './screens/onboarding.js';

// ── Global click delegation ──
// One listener reads data-action from every click and dispatches it. `act` is
// the clicked [data-action] element; handlers that hit the network take it so
// they can show a pending state on that button.
document.body.addEventListener('click', async (e) => {
  // Let an open modal manage its own clicks first.
  if (e.target.closest('#modal-overlay')) {
    if (e.target.closest('[data-action="modal-cancel"]')) closeModal();
    return;
  }

  const act = e.target.closest('[data-action]');
  if (!act) return;

  try {
    switch (act.dataset.action) {
      // Auth
      case 'auth-tab':
        setAuthMode(act.dataset.mode);
        break;
      case 'do-login':
        await doLogin(act);
        break;
      case 'do-signup':
        await doSignup(act);
        break;

      // Onboarding
      case 'ob-next':
        obNext();
        break;
      case 'ob-add-subject':
        await obAddSubject(act);
        break;
      case 'ob-add-topic':
        obAddTopic();
        break;
      case 'ob-finish':
        await obFinish(act);
        break;
      case 'ob-skip':
        await obSkip();
        break;

      // Navigation
      case 'nav-dashboard':
        navigate('#dashboard');
        break;
      case 'nav-settings':
        navigate('#settings');
        break;
      case 'do-logout':
        try {
          await api('POST', '/api/auth/logout');
        } catch {
          /* logging out is best-effort */
        }
        clearToken();
        state.currentUser = null;
        navigate('#');
        route();
        break;
    }
  } catch (err) {
    toast(err.message || 'Something went wrong');
  }
});

// ── Keyboard shortcuts ──
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if ($('#modal-overlay').classList.contains('show')) closeModal();
    return;
  }
  // Enter submits the auth form.
  if (e.key === 'Enter' && !$('#screen-auth').classList.contains('hidden')) {
    if (state.authMode === 'login') doLogin($('[data-action="do-login"]'));
    else doSignup($('[data-action="do-signup"]'));
  }
  // Enter adds a topic in onboarding step 3.
  if (e.key === 'Enter' && document.activeElement?.id === 'ob-topic-input') {
    obAddTopic();
  }
});

// ── Startup ──
window.addEventListener('hashchange', route);
route(); // modules are deferred, so the DOM is already parsed here.
