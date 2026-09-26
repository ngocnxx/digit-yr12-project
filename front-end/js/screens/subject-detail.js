// Subject detail screen. Shows topics, review history, and coverage.

import { api } from '../api.js';
import { $, esc, openModalFromHTML, toast } from '../dom.js';
import { icon, subjectIcon } from '../icons.js';
import { coverageOf, statusBadge, statusOf } from '../schedule.js';
import { openLogReview } from './log-review.js';
import { navigate, route } from '../router.js';
import { trace } from '../debug.js';

const CONF_LABEL = { shaky: 'Need more time', okay: 'Getting there', solid: 'Pretty well' };

// Lucide icon and colour for each confidence level so past reviews stand out.
// This is only how it looks. Confidence never changes the review schedule.
const CONF_META = {
  shaky: { icon: 'sprout', cls: 'conf-shaky' },
  okay: { icon: 'trending-up', cls: 'conf-okay' },
  solid: { icon: 'circle-check-big', cls: 'conf-solid' },
  internal_assessment: { icon: 'book-open', cls: 'conf-internal' },
};

// Build the coloured tag shown next to a review
function confTag(key) {
  if (!key) return '';
  const meta = CONF_META[key] || { icon: 'circle-check-big', cls: 'conf-okay' };
  const label = CONF_LABEL[key] || key.replace(/_/g, ' ');
  return `<span class="conf-tag ${meta.cls}">${icon(meta.icon, { size: 13 })}${esc(label)}</span>`;
}

// True if this review has anything worth opening
function hasNote(review) {
  return !!(review.evidence || review.reflection || review.attachment);
}

// Escape the text first, then turn any web address into a real link.
// Order matters here, otherwise the escaping would break the link.
function linkify(text) {
  return esc(text).replace(
    /(https?:\/\/[^\s<]+)/g,
    (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`,
  );
}

// The confidence from the most recent review of this topic
function avgConfidence(topic) {
  const last = (topic.reviews || []).filter((r) => r.confidence).slice(-1)[0];
  return last ? last.confidence : null;
}

function topicRow(topic, isPriority = false) {
  const badge = statusBadge(topic);
  const pct = topic.reviewCount ? Math.min(100, topic.reviewCount * 25) : 0;
  const conf = avgConfidence(topic);
  const history = (topic.reviews || []).length
    ? `<details class="topic-history"><summary>View history (${topic.reviews.length})</summary>
         <ul>${topic.reviews
           .map(
             (r, i) =>
               `<li>R${i + 1} · ${esc(r.reviewedDate)}${r.confidence ? ` · ${confTag(r.confidence)}` : ''} → due ${esc(r.nextDue)}${
                 hasNote(r)
                   ? ` <button class="hist-open" data-action="view-note" data-topic-id="${topic.id}" data-review-index="${i}">${icon('book-open', { size: 12 })} View note</button>`
                   : ''
               }</li>`,
           )
           .join('')}</ul></details>`
    : '';
  return `
    <div class="topic-row${isPriority ? ' topic-priority' : ''}">
      <div class="topic-main">
        <div class="topic-name">${esc(topic.name)}${topic.standardNumber ? ` <span class="std">${esc(topic.standardNumber)}</span>` : ''}</div>
        <div class="topic-meta">${topic.reviewCount ? `Reviewed ${topic.reviewCount}× · ${pct}%` : 'Not yet reviewed'}${conf ? ` · ${confTag(conf)}` : ''}</div>
        ${history}
      </div>
      <div class="topic-side">
        <button class="btn btn-soft btn-sm" data-action="open-log" data-topic-id="${topic.id}">${icon('circle-check-big', { size: 15 })} Log review</button>
        <span class="status-badge ${badge.cls}">${badge.label}</span>
      </div>
    </div>`;
}

export async function renderSubjectDetail(subjectId) {
  trace('subject-detail: render', subjectId);
  const root = $('#screen-subject');
  const { subjects } = await api('GET', '/api/subjects');
  const subject = subjects.find((s) => String(s.id) === String(subjectId));
  if (!subject) {
    navigate('#dashboard');
    return;
  }

  const topics = subject.topics || [];
  const cov = coverageOf(topics);
  const reviewed = topics.filter((t) => (t.reviewCount || 0) >= 1).length;
  // Find the most urgent topic to show at the top
  const RANK = { overdue: 3, due: 2, new: 1, ok: 0 };
  const sorted = [...topics].sort((a, b) => {
    const ra = statusOf(a);
    const rb = statusOf(b);
    return RANK[rb.status] - RANK[ra.status] || rb.days - ra.days;
  });
  const priority = sorted[0] && statusOf(sorted[0]).status !== 'ok' ? sorted[0] : null;
  const internal = !!subject.internalMode; // true if internal mode is on

  root.innerHTML = `
    <div class="subject-detail">
      <button class="link-back" data-action="nav-dashboard">${icon('log-out', { size: 16, cls: 'flip' })} Back</button>

      <div class="sd-head">
        <h1 class="sd-title">${icon(subjectIcon(subject.name), { size: 30, cls: 'subject-icon' })} ${esc(subject.name)}</h1>
        <div class="sd-actions">
          <button class="btn btn-soft btn-sm" data-action="add-topic" data-subject-id="${subject.id}" data-subject-name="${esc(subject.name)}">${icon('plus', { size: 15 })} Add topics</button>
        </div>
      </div>

      <p class="sd-coverage">Coverage: ${cov}% (${reviewed} of ${topics.length} topics reviewed)</p>
      <div class="progress"><span class="progress-fill" style="width:${cov}%"></span></div>

      ${internal ? `<div class="internal-banner">Internal mode is on. ${esc(subject.name)} is paused while you focus on your assessment.</div>` : ''}

      ${priority ? `<h3 class="sd-section">Today's priority</h3>${topicRow(priority, true)}` : ''}

      <h3 class="sd-section">All topics</h3>
      ${topics.length ? topics.map((t) => topicRow(t)).join('') : '<p class="muted small">No topics yet. Add some to get started.</p>'}

      <div class="internal-box">
        <h3 class="internal-box-title">${icon('book-open', { size: 18 })} Internal assessment mode</h3>
        <p class="internal-box-text">
          ${
            internal
              ? `${esc(subject.name)} is paused right now, so it will not show up in your daily reviews. When you stop it, every topic is marked as revised and set to come back in 7 days.`
              : `Doing an internal for ${esc(subject.name)}? Turning this on pauses it in your daily reviews so you can focus. Nothing is deleted and your topics stay exactly as they are.`
          }
        </p>
        <button class="btn btn-internal" data-action="toggle-internal" data-subject-id="${subject.id}">
          ${internal ? 'Stop' : 'Start'} Internal mode for ${esc(subject.name)}
        </button>
      </div>
    </div>`;
}

// Open one saved review so the student can read it back.
// Wired from main.js by the "view-note" action.
export async function openReviewNote(topicId, reviewIndex) {
  try {
    const { subjects } = await api('GET', '/api/subjects');
    const topic = subjects.flatMap((s) => s.topics).find((t) => String(t.id) === String(topicId));
    const review = topic && (topic.reviews || [])[Number(reviewIndex)];
    if (!review) return toast('That note could not be found.');
    trace('subject-detail: open note', { topicId, reviewIndex });

    openModalFromHTML(`
      <div class="modal-card note-card">
        <h2>Review note</h2>
        <p class="modal-sub">${esc(topic.name)} · ${esc(review.reviewedDate)}</p>
        ${review.confidence ? `<p class="note-conf">${confTag(review.confidence)}</p>` : ''}

        ${
          review.evidence
            ? `<div class="note-block"><h3>Evidence of Learning</h3><p>${linkify(review.evidence)}</p></div>`
            : ''
        }
        ${
          review.reflection
            ? `<div class="note-block"><h3>Reflection</h3><p>${linkify(review.reflection)}</p></div>`
            : ''
        }
        ${
          review.attachment
            ? `<div class="note-block"><h3>Attached photo</h3>
                 <a href="${esc(review.attachment)}" target="_blank" rel="noopener noreferrer">
                   <img class="note-img" src="${esc(review.attachment)}" alt="${esc(review.attachmentName || 'Attached photo')}">
                 </a>
                 <p class="muted small">${esc(review.attachmentName || '')}</p>
               </div>`
            : ''
        }

        <div class="modal-actions">
          <button class="btn btn-ghost" data-action="modal-cancel">Close</button>
        </div>
      </div>`);
  } catch (e) {
    toast(e.message || 'Could not open that note');
  }
}

// Toggle internal (assessment) mode on or off for this subject
export async function onToggleInternal(id) {
  try {
    const { subjects } = await api('GET', '/api/subjects');
    const subject = subjects.find((s) => String(s.id) === String(id));
    const on = subject && subject.internalMode;
    await api('POST', on ? '/api/assessment-mode-end' : '/api/assessment-mode-start', {
      subjectId: Number(id),
    });
    trace('subject-detail: internal mode', on ? 'ended' : 'started', id);
    toast(on ? 'Internal mode ended, topics caught up' : 'Internal mode on, subject paused');
    route();
  } catch (e) {
    toast(e.message || 'Could not update internal mode');
  }
}
