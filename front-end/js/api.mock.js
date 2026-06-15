// In-browser mock backend — front-end-only dev (no Flask, no SQLite).
//
// Enabled by `?mock=1` (see config.js USE_MOCK). It mirrors the real API
// contract exactly — same request bodies, same response shapes, same status
// codes and friendly error messages — so the SPA can't tell the difference and
// switching to the real backend is just removing the flag.
//
// Data persists in localStorage (key `nrn_mock_db`) so reloads keep your state.
// Tokens are `mock.<userId>` (no real crypto — this is a dev stand-in only).

const DB_KEY = 'nrn_mock_db';
const MIN_PASSWORD_LEN = 4;
const MAX_NAME_LEN = 80;
const LATENCY_MS = 120; // a little delay so pending/disabled UI states are visible

function load() {
  try {
    return JSON.parse(localStorage.getItem(DB_KEY)) ?? blank();
  } catch {
    return blank();
  }
}
function blank() {
  return { users: [], subjects: [], topics: [], seq: 0 };
}
function save(db) {
  localStorage.setItem(DB_KEY, JSON.stringify(db));
}
function nextId(db) {
  db.seq += 1;
  return db.seq;
}

// Mirror of errors.py: throws an Error carrying .status, like the real api().
function fail(message, status = 400) {
  const err = new Error(message);
  err.status = status;
  throw err;
}
function requireStr(value, field, maxLen = MAX_NAME_LEN) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) fail(`Please enter a ${field}.`);
  if (text.length > maxLen) fail(`That ${field} is too long (max ${maxLen} characters).`);
  return text;
}
function userFromToken(db, token) {
  const id = token && token.startsWith('mock.') ? Number(token.slice(5)) : NaN;
  const user = db.users.find((u) => u.id === id);
  if (!user) fail('Authentication required.', 401);
  return user;
}

// Serialisers — match the Flask route shapes.
const userPublic = (u) => ({
  id: u.id,
  name: u.name,
  email: u.email,
  yearLevel: u.yearLevel,
  onboarding_done: u.onboarding_done,
});
const subjectPublic = (s) => ({ id: s.id, name: s.name, emoji: s.emoji, colour: s.colour });
const topicPublic = (t) => ({
  id: t.id,
  subjectId: t.subjectId,
  name: t.name,
  emoji: t.emoji,
  standardNumber: t.standardNumber,
  reviewCount: t.reviewCount,
  nextDue: t.nextDue,
});

// Route table keyed by "METHOD path". Each handler gets (db, body, token).
const routes = {
  'POST /api/auth/signup': (db, body) => {
    const name = requireStr(body.name, 'name');
    const email = requireStr(body.email, 'email');
    const password = body.password || '';
    if (password.length < MIN_PASSWORD_LEN)
      fail(`Password must be at least ${MIN_PASSWORD_LEN} characters.`);
    if (db.users.some((u) => u.email.toLowerCase() === email.toLowerCase()))
      fail('An account with that email already exists.');
    const yearLevel = Number(body.yearLevel) || 12;
    const user = { id: nextId(db), name, email, password, yearLevel, onboarding_done: 0 };
    db.users.push(user);
    save(db);
    return { token: `mock.${user.id}`, user: userPublic(user) };
  },

  'POST /api/auth/login': (db, body) => {
    const email = (body.email || '').trim();
    const password = body.password || '';
    if (!email || !password) fail('Please enter your email and password.');
    const user = db.users.find((u) => u.email.toLowerCase() === email.toLowerCase());
    if (!user || user.password !== password) fail('Incorrect email or password.', 401);
    return { token: `mock.${user.id}`, user: userPublic(user) };
  },

  'GET /api/auth/me': (db, _body, token) => ({ user: userPublic(userFromToken(db, token)) }),

  'POST /api/auth/logout': () => ({ ok: true }),

  'PUT /api/user/onboarding': (db, _body, token) => {
    const user = userFromToken(db, token);
    user.onboarding_done = 1;
    save(db);
    return { ok: true };
  },

  'POST /api/subjects': (db, body, token) => {
    const user = userFromToken(db, token);
    const name = requireStr(body.name, 'subject name');
    if (db.subjects.some((s) => s.userId === user.id && s.name === name && !s.archived))
      fail(`You already have a subject called “${name}”.`);
    const subject = {
      id: nextId(db),
      userId: user.id,
      name,
      emoji: (body.emoji || '').trim() || null,
      colour: (body.colour || '').trim() || null,
      archived: 0,
    };
    db.subjects.push(subject);
    save(db);
    return { subject: subjectPublic(subject) };
  },

  'GET /api/subjects': (db, _body, token) => {
    const user = userFromToken(db, token);
    const subjects = db.subjects
      .filter((s) => s.userId === user.id && !s.archived)
      .map((s) => ({
        ...subjectPublic(s),
        topics: db.topics
          .filter((t) => t.subjectId === s.id && !t.archived)
          .map(topicPublic),
      }));
    return { subjects };
  },

  'POST /api/topics': (db, body, token) => {
    const user = userFromToken(db, token);
    const name = requireStr(body.name, 'topic name');
    const subject = db.subjects.find(
      (s) => s.id === body.subjectId && s.userId === user.id && !s.archived,
    );
    if (!subject) fail('That subject could not be found.', 404);
    const topic = {
      id: nextId(db),
      subjectId: subject.id,
      name,
      emoji: (body.emoji || '').trim() || null,
      standardNumber: (body.standardNumber || '').trim() || null,
      reviewCount: 0,
      nextDue: null,
      archived: 0,
    };
    db.topics.push(topic);
    save(db);
    return { topic: topicPublic(topic) };
  },
};

// Same signature the real api() uses internally; token is passed in so this
// module stays decoupled from api.js (no circular import).
export async function mockApi(method, path, body, token) {
  await new Promise((r) => setTimeout(r, LATENCY_MS));
  const handler = routes[`${method} ${path}`];
  if (!handler) fail('Not found.', 404);
  return handler(load(), body || {}, token);
}
