// Display helpers for showing when a topic is due.
// The real scheduling maths lives on the server in back-end/scheduling.py.
// This file only works out what label to show, it never decides a due date.

// Format a date as YYYY-MM-DD
function fmtLocal(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function todayISO() {
  return fmtLocal(new Date());
}

// Whole days from a -> b (b - a). Positive = b is later.
function daysBetween(aISO, bISO) {
  return Math.round((new Date(bISO + 'T00:00:00') - new Date(aISO + 'T00:00:00')) / 86400000);
}

// Work out a topic's status (new, overdue, due today, or ok).
export function statusOf(topic, today = todayISO()) {
  if (!topic.nextDue) return { status: 'new', days: 0 };
  const diff = daysBetween(topic.nextDue, today); // today - nextDue
  if (diff > 0) return { status: 'overdue', days: diff };
  if (diff === 0) return { status: 'due', days: 0 };
  return { status: 'ok', days: -diff }; // due in |diff| days
}

// Return badge text and style for a topic's status.
export function statusBadge(topic) {
  const st = statusOf(topic);
  if (st.status === 'new') return { cls: 'is-new', label: 'NEW' };
  if (st.status === 'overdue') return { cls: 'is-overdue', label: `${st.days}d overdue` };
  if (st.status === 'due') return { cls: 'is-due', label: 'due today' };
  return { cls: 'is-ok', label: `due in ${st.days}d` };
}

// Percentage of topics reviewed at least once.
export function coverageOf(topics = []) {
  if (!topics.length) return 0;
  const reviewed = topics.filter((t) => (t.reviewCount || 0) >= 1).length;
  return Math.round((reviewed / topics.length) * 100);
}
