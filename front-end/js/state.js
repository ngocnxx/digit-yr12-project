// Central app state. A single mutable object so modules share one source of
// truth (ES module exports are live bindings like mutate properties, don't reassign).

export const state = { //run only once the site first loads up
  currentUser: null, // { id, name, email, yearLevel, onboarding_done }
  authMode: 'login', // 'login' | 'signup'
  onboarding: {
    step: 1, // 1 | 2 | 3 (which card/step user is on)
    createdSubject: null, // { id, name, emoji, colour }
    addedTopics: [], // string[]
  },
};

export function resetOnboarding() {
  state.onboarding.step = 1;
  state.onboarding.createdSubject = null;
  state.onboarding.addedTopics = [];
}
