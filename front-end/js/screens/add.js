// Add-Subject and Add-Topic modals which is reachable from the dashboard, the subjects
// panel, and the subject-detail screen.

import { api } from '../api.js';
import { $, closeModal, esc, openModalFromHTML, toast, withPending } from '../dom.js';
import { trace } from '../debug.js';

// Common NCEA subjects offered as a datalist (still free-type-able).
const COMMON = ['English', 'Mathematics', 'Biology', 'Chemistry', 'Physics', 'History', 'Geography', 'Economics'];

let pending = null; // { onDone, subjectId? }

function showErr(msg) {
  const err = $('#add-err');
  err.textContent = msg;
  err.classList.remove('hidden');
}

export function openAddSubject(onDone) {
  trace('add: open Add Subject modal');
  pending = { onDone };
  // A real <select>, NOT an <input list="...">/<datalist>. A datalist filters its
  // options by whatever text is already in the box, so once "English" is chosen
  // re-opening the list shows only "English" — the user has to clear the field by
  // hand before they can pick anything else. A <select> always offers every
  // option, every time. Same control the onboarding step-2 picker uses.
  openModalFromHTML(`
    <div class="modal-card">
      <h2>Add subject</h2>
      <p class="modal-sub">Pick a common NCEA subject or type your own.</p>
      <div class="field">
        <label for="add-subj-select">Subject</label>
        <select class="input select-input" id="add-subj-select">
          <option value="">— Choose a subject —</option>
          ${COMMON.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join('')}
          <option value="__custom__">Other (type your own)</option>
        </select>
      </div>
      <div class="field hidden" id="add-custom-field">
        <label for="add-subj">Subject name</label>
        <input class="input" id="add-subj" placeholder="e.g. Digital Technology" autocomplete="off">
      </div>
      <p class="error-msg hidden" id="add-err"></p>
      <div class="modal-actions">
        <button class="btn btn-ghost" data-action="modal-cancel">Cancel</button>
        <button class="btn btn-primary" data-action="add-subject-submit">Add subject</button>
      </div>
    </div>`);

  // Reveal the free-text box only for "Other" (mirrors onboarding's behaviour).
  const sel = $('#add-subj-select');
  sel.onchange = () => {
    const isCustom = sel.value === '__custom__';
    $('#add-custom-field').classList.toggle('hidden', !isCustom);
    if (isCustom) $('#add-subj').focus();
    trace('add: subject select →', sel.value);
  };
  setTimeout(() => sel.focus(), 30);
}

export async function submitAddSubject(btn) {
  const sel = $('#add-subj-select');
  const isCustom = sel.value === '__custom__';
  const name = (isCustom ? $('#add-subj').value : sel.value).trim();
  if (!name) return showErr(isCustom ? 'Please type a subject name.' : 'Please choose a subject.');
  try {
    trace('add: POST /api/subjects', { name });
    await withPending(btn, 'Adding…', () => api('POST', '/api/subjects', { name }));
    const done = pending?.onDone;
    pending = null;
    closeModal();
    toast('Subject added');
    if (done) await done();
  } catch (e) {
    showErr(e.message || 'Sorry, you could not add subject.');
  }
}

export function openAddTopic(subjectId, subjectName, onDone) {
  trace('add: open Add Topic modal', { subjectId, subjectName });
  pending = { onDone, subjectId };
  openModalFromHTML(`
    <div class="modal-card">
      <h2>Add topic</h2>
      <p class="modal-sub">${subjectName ? `to ${esc(subjectName)}` : ''}</p>
      <div class="field">
        <label for="add-topic">Topic name</label>
        <input class="input" id="add-topic" placeholder="e.g. Photosynthesis" autocomplete="off">
      </div>
      <div class="field">
        <label for="add-std">Standard number <span class="muted">(optional)</span></label>
        <input class="input" id="add-std" placeholder="e.g. AS 91156" autocomplete="off">
      </div>
      <p class="error-msg hidden" id="add-err"></p>
      <div class="modal-actions">
        <button class="btn btn-ghost" data-action="modal-cancel">Cancel</button>
        <button class="btn btn-primary" data-action="add-topic-submit">Add topic</button>
      </div>
    </div>`);
  setTimeout(() => $('#add-topic')?.focus(), 30);
}

export async function submitAddTopic(btn) {
  const name = $('#add-topic').value.trim();
  const standardNumber = $('#add-std').value.trim();
  if (!name) return showErr('Please type a topic name.');
  try {
    trace('add: POST /api/topics', { subjectId: pending?.subjectId, name });
    await withPending(btn, 'Adding…', () =>
      api('POST', '/api/topics', { subjectId: Number(pending.subjectId), name, standardNumber }),
    );
    const done = pending?.onDone;
    pending = null;
    closeModal();
    toast('Topic added');
    if (done) await done();
  } catch (e) {
    showErr(e.message || 'Sorry, you could not add topic.');
  }
}
