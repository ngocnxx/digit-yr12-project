// Onboarding screen — 3-step flow: welcome → add subject → add topics.

import { api } from '../api.js';
import { $, $$, esc, toast, withPending } from '../dom.js';
import { icon } from '../icons.js';
import { resetOnboarding, state } from '../state.js';
import { trace } from '../debug.js';
import { navigate } from '../router.js';

const ob = state.onboarding;

export function hydrateOnboarding() {
  resetOnboarding();
  obRender();
}

export function obRender() {
  // Progress dots.
  $$('#ob-dots .dot').forEach((d, i) => {
    d.classList.toggle('done', i + 1 < ob.step);
    d.classList.toggle('active', i + 1 === ob.step);
  });
  // Show only the current step.
  [1, 2, 3].forEach((n) => {
    document.getElementById('ob-step-' + n).classList.toggle('hidden', n !== ob.step);
  });
  // Wire the "Other" custom-subject toggle.
  const sel = $('#ob-subj-select');
  if (sel) {
    sel.onchange = () => {
      $('#ob-custom-field').classList.toggle('hidden', sel.value !== '__custom__');
    };
  }
  // Step 3: subject heading + chips.
  if (ob.step === 3) {
    $('#ob-subject-name').textContent = ob.createdSubject ? ob.createdSubject.name : 'your subject';
    renderObChips();
  }
}

export function obNext() {
  ob.step = 2;
  obRender();
}

function renderObChips() {
  const wrap = $('#ob-topic-chips');
  if (!ob.addedTopics.length) {
    wrap.innerHTML =
      '<span class="muted small"> You dont have any  topics added yet. But you can add them later too.</span>';
    return;
  }
  wrap.innerHTML = ob.addedTopics
    .map(
      (name, i) =>
        `<span class="topic-chip">${esc(name)}
           <span class="chip-remove" data-ob-remove="${i}">${icon('x', { size: 13 })}</span>
         </span>`,
    )
    .join('');
  $$('#ob-topic-chips .chip-remove').forEach((x) => {
    x.onclick = () => {
      ob.addedTopics.splice(+x.dataset.obRemove, 1);
      renderObChips();
    };
  });
}

export async function obAddSubject(btn) {
  const sel = $('#ob-subj-select');
  if (!sel.value) {
    toast('Pick a subject first');
    return;
  }
  // No emoji stored- the dashboard picks a Lucide icon from the subject name
  // (see icons.js subjectIcon). Options carry data-icon just for documentation.
  let name, colour;
  if (sel.value === '__custom__') {
    name = $('#ob-custom').value.trim();
    if (!name) {
      toast('Type a subject name');
      return;
    }
    colour = undefined;
  } else {
    const opt = sel.selectedOptions[0];
    name = sel.value;
    colour = opt.dataset.colour;
  }
  try {
    trace('onboarding: obAddSubject → POST /api/subjects', { name });
    const r = await withPending(btn, 'Adding…', () =>
      api('POST', '/api/subjects', { name, colour }),
    );
    ob.createdSubject = r.subject;
    ob.step = 3;
    obRender();
  } catch (e) {
    toast(e.message);
  }
}

export function obAddTopic() {
  const input = $('#ob-topic-input');
  const name = input.value.trim();
  if (!name) return;
  ob.addedTopics.push(name);
  input.value = '';
  renderObChips();
  input.focus();
}

export async function obFinish(btn) {
  try {
    await withPending(btn, 'Saving…', async () => {
      if (ob.createdSubject) {
        trace('onboarding: obFinish → creating', ob.addedTopics.length, 'topics');
        for (const name of ob.addedTopics) {
          await api('POST', '/api/topics', { subjectId: ob.createdSubject.id, name });
        }
      }
      await finishOnboarding();
    });
  } catch (e) {
    toast(e.message);
  }
}

export async function obSkip() {
  await finishOnboarding();
}

async function finishOnboarding() {
  await api('PUT', '/api/user/onboarding');
  state.currentUser.onboarding_done = 1;
  resetOnboarding();
  navigate('#dashboard');
}
