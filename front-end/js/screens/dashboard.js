// Dashboard — F1 placeholder. Confirms the full auth → onboarding → data
// round-trip by reading back the subjects/topics the user just created.
// The real priorities + coverage engine lands in slice 2.

import { api } from '../api.js';
import { $, esc } from '../dom.js';
import { state } from '../state.js';

export async function renderDashboard() {
  const root = $('#screen-dashboard');
  const name = esc(state.currentUser?.name || 'there');

  const { subjects } = await api('GET', '/api/subjects');
  const topicCount = subjects.reduce((n, s) => n + s.topics.length, 0);

  root.innerHTML = `
    <div class="dashboard">
      <h1 class="dashboard-greeting">Kia ora, ${name} 👋</h1>
      <p class="dashboard-sub">${summary(subjects.length, topicCount)}</p>
      ${subjects.length ? subjects.map(subjectCard).join('') : emptyState()}
      <p class="wellbeing-footer">
        Need someone to talk to? Youthline — 0800 376 633 or text 234.
      </p>
    </div>
  `;
}

function summary(subjectCount, topicCount) {
  if (!subjectCount) return "Let's add your first subject to get started.";
  const s = subjectCount === 1 ? 'subject' : 'subjects';
  const t = topicCount === 1 ? 'topic' : 'topics';
  return `You're set up with ${subjectCount} ${s} and ${topicCount} ${t}. Daily review priorities arrive soon.`;
}

function subjectCard(subject) {
  const emoji = esc(subject.emoji || '📚');
  const topics = subject.topics.length
    ? `<ul class="subject-topics">${subject.topics.map(topicChip).join('')}</ul>`
    : '<p class="muted small">No topics yet — you can add them later.</p>';
  return `
    <div class="subject-card">
      <h3>${emoji} ${esc(subject.name)}</h3>
      <p class="subject-meta">${subject.topics.length} ${
        subject.topics.length === 1 ? 'topic' : 'topics'
      }</p>
      ${topics}
    </div>
  `;
}

function topicChip(topic) {
  const std = topic.standardNumber ? `<span class="std">${esc(topic.standardNumber)}</span>` : '';
  return `<li>${esc(topic.name)}${std}</li>`;
}

function emptyState() {
  return `
    <div class="empty-state">
      <p>No subjects yet — but that's okay. You can add them any time.</p>
    </div>
  `;
}
