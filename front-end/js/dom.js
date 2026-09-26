// Helper functions for the page: find elements, show/hide, safe text, messages.

import { icon } from './icons.js';

export const $ = (sel, root = document) => root.querySelector(sel); // find one element
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel)); // find all matching elements

export function show(el) {
  if (el) el.classList.remove('hidden');
}
export function hide(el) {
  if (el) el.classList.add('hidden');
}

// Make user text safe to put in HTML (stops broken characters).
export function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Toast notification. "success" shows a green pill that stays longer.
const TOAST_MS = { success: 3600, default: 2200 };

let toastTimer = null;
export function toast(msg, variant = 'default') {
  const el = $('#toast');
  if (!el) return;
  clearTimeout(toastTimer);
  const isSuccess = variant === 'success';
  // Set className first so it does not remove the .show class we add next
  el.className = 'toast' + (isSuccess ? ' is-success' : '');
  el.innerHTML =
    (isSuccess ? icon('circle-check-big', { size: 17 }) : '') + `<span>${esc(msg)}</span>`;
  void el.offsetWidth; // reset the animation
  el.classList.add('show');
  toastTimer = setTimeout(
    () => el.classList.remove('show'),
    isSuccess ? TOAST_MS.success : TOAST_MS.default,
  );
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

// Disable a button while waiting for the server, then restore it.
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
