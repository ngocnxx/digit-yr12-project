// DOM helpers — selectors, show/hide, HTML escaping, toast, and modal plumbing.

export const $ = (sel, root = document) => root.querySelector(sel); //sel (selector= what you're hunting for), searches the root = document ; $= grab 1 specific item
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));//$$ grab every matching item on the screen; array  from packs the messy node list (of all the items) into clean js array(list)

export function show(el) {
  if (el) el.classList.remove('hidden');
}
export function hide(el) {
  if (el) el.classList.add('hidden');
}

// Escape user-supplied text before inserting into innerHTML (XSS-safe).
export function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

let toastTimer = null;
export function toast(msg) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  void el.offsetWidth; // force reflow so the transition re-fires
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
}

export function openModalFromHTML(html) {
  const ov = $('#modal-overlay');
  ov.innerHTML = html;
  ov.classList.add('show');
  ov.onclick = (e) => {
    if (e.target === ov) closeModal();
  };
  return ov;
}

export function closeModal() {
  const ov = $('#modal-overlay');
  ov.classList.remove('show');
  ov.onclick = null;
  setTimeout(() => {
    if (!ov.classList.contains('show')) ov.innerHTML = '';
  }, 220);
}

// Run an async action while disabling a button and showing pending text, so
// API calls never feel frozen. Restores the original label afterwards.
export async function withPending(btn, pendingText, fn) {
  if (!btn) return fn();
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = pendingText;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}
