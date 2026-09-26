// Settings screen. Shows account info and lets the student change their daily review cap.

import { api } from '../api.js';
import { $, esc, toast } from '../dom.js';
import { icon } from '../icons.js';
import { state } from '../state.js';
import { trace } from '../debug.js';

export async function renderSettings() {
  trace('settings: render');
  const root = $('#screen-settings');
  const u = state.currentUser || {};
  const cap = u.dailyCap ?? 5;
  root.innerHTML = `
    <div class="settings">
      <button class="link-back" data-action="nav-dashboard">${icon('log-out', { size: 16, cls: 'flip' })} Back</button>
      <h1 class="settings-title">${icon('settings', { size: 24 })} Settings</h1>

      <div class="settings-card">
        <div class="setting-row"><span>Name</span><strong>${esc(u.name || '')}</strong></div>
        <div class="setting-row"><span>Email</span><strong>${esc(u.email || '')}</strong></div>
        <div class="setting-row"><span>Year level</span><strong>Year ${esc(String(u.yearLevel || 12))}</strong></div>
      </div>

      <div class="settings-card">
        <div class="field">
          <label for="set-cap">Daily review cap</label>
          <select class="input select-input" id="set-cap">
            ${[3, 4, 5, 6, 7, 8].map((n) => `<option${n === cap ? ' selected' : ''}>${n}</option>`).join('')}
          </select>
          <p class="muted small">The most topics we'll suggest each day, so it never feels overwhelming.</p>
        </div>
      </div>

      <button class="btn btn-danger btn-block" data-action="do-logout">${icon('log-out', { size: 16 })} Log out</button>
    </div>`;

  // Save the new cap as soon as the student changes it
  $('#set-cap').onchange = async (e) => {
    try {
      const { dailyCap } = await api('PUT', '/api/settings', { dailyCap: Number(e.target.value) });
      if (state.currentUser) state.currentUser.dailyCap = dailyCap;
      trace('settings: dailyCap saved →', dailyCap);
      toast('Daily cap updated');
    } catch (err) {
      toast(err.message || 'Could not save that setting');
    }
  };
}
