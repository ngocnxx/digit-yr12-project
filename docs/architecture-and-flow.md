# Architecture & Flow — how the NCEA Review Navigator actually works

> **Who this is for:** you, the student-developer, learning this codebase so you can rebuild and explain
> it. Read this once end-to-end, then keep it open while you read the code. Companion docs:
> [`rebuild-roadmap.md`](rebuild-roadmap.md) (how to build it yourself, slice by slice) and
> [`user-testing-guide.md`](user-testing-guide.md) (how to get real testers on it).

---

## 1. The one idea to hold onto: **mock vs. real**

When you open the site the normal way (`http://127.0.0.1:5500/`), **nothing touches Flask or the
database.** Every "save" goes into your own browser's `localStorage` through a *fake backend*
(`js/api.mock.js`). That's why the dashboard, priorities and "Log review" all appear to work even though
the real Python backend can't do them yet.

- **Default → MOCK** — browser-only, data in `localStorage`. No server, no database needed.
- **`?real=1` in the URL → REAL** — the same code calls Flask on `:5050`, which reads/writes SQLite.
- The switch lives in `js/config.js` (`USE_MOCK`), and **both paths go through the same `api()` function**
  in `js/api.js`, so the screens never know which backend answered.

> **Remember:** *today = mock; the real backend has only finished "F1" (accounts + adding
> subjects/topics). Everything about reviewing is faked in the browser for now.*

---

## 2. The three tiers (the big picture)

```
┌─ BROWSER (front-end/) ──────────┐     ┌─ FLASK API (back-end/) ─────┐     ┌─ DATABASE ─────┐
│  index.html   5 screen shells   │     │  app.py    app factory      │     │ navigator.db   │
│  js/main.js   1 click listener  │     │  routes/*  endpoints        │     │ (SQLite)       │
│  js/router.js hash → screen     │ ──► │  auth.py   passwords + JWT  │ ──► │  users         │
│  js/api.js    fetch wrapper  ───┼──┐  │  db.py     SQLite access    │     │   └ subjects   │
│  js/api.mock  fake backend  ◄───┼──┘  │  schema.sql table shapes    │     │      └ topics  │
│  js/schedule  review maths      │mock │  scheduling.py engine (STUB)│     │        └ reviews│
│  css/*.css    looks             │     │  errors.py ApiError         │     │                │
└─────────────────────────────────┘     └─────────────────────────────┘     └────────────────┘
        served on :5500                       served on :5050 (real path only)
```

- **No build tools, no npm.** The front-end is plain ES modules; the back-end is plain Flask. This is
  deliberate — fewer moving parts to learn.
- **Two origins.** The web page (`:5500`) and the API (`:5050`) are separate servers; the browser talks to
  the API with `fetch()` + a `Bearer` token. (That's why CORS is configured on the API.)

---

## 3. Spine vs. Features — the mental model that makes the file count manageable

Every file is either **spine** (shared plumbing, built once and extended a little per feature) or a
**feature** (one screen's own code). This is the key to *"which lines do I take for this screen?"* —
answered fully in [`rebuild-roadmap.md`](rebuild-roadmap.md).

### 🦴 Spine (shared) — front-end
| File | Its one job |
|---|---|
| `index.html` | Five `<section class="screen">` shells (`auth`, `onboarding`, `dashboard`, `subject`, `settings`) + topbar + a tiny classic "serve-guard" script. Auth & onboarding have real HTML; the other three are **empty shells filled by JS**. |
| `js/config.js` | Constants: `API_BASE` (`:5050`), `USE_MOCK` (the mock/real switch), `TOKEN_KEY` (`ncea_token`). |
| `js/dom.js` | Tiny helpers: `$`/`$$` (find elements), `show`/`hide`, `esc` (escape HTML), `toast`, and modal open/close. |
| `js/state.js` | One shared object `state` = the current user + UI state, so modules agree on "truth". |
| `js/debug.js` | `DEBUG` flag (on with `?debug=1`) + `trace()` — a `console.log` that only prints when debugging. |
| `js/icons.js` | Lucide icons vendored as inline SVG strings; `icon()`, `subjectIcon()`, `hydrateIcons()`. |
| `js/api.js` | **The only file that talks to a backend.** Adds the token, picks mock vs real, returns JSON or throws a friendly error. |
| `js/api.mock.js` | The fake backend (a route table keyed by `"METHOD /path"`), persisting to `localStorage`. |
| `js/router.js` | `route()` — the "bouncer": decides which screen to show from the token + onboarding state + URL hash. |
| `js/main.js` | **One** click listener for the whole app; a `switch` with one `case` per button action. |
| `css/tokens.css`, `css/base.css` | Colour/spacing variables and resets. (`components.css`, `screens.css` grow per feature.) |

### 🦴 Spine (shared) — back-end
| File | Its one job |
|---|---|
| `app.py` | App factory: registers the route blueprints, CORS, the error handler, `/api/health`. |
| `db.py` | `get_db()` / `close_db()` / `init_db()` — SQLite connection per request. |
| `schema.sql` | The four tables. `topics` already has `review_count` + `next_due`; `reviews` already exists — both waiting for the engine. |
| `auth.py` | `hash_password`, `verify_password`, JWT `encode/decode_token`, `@require_auth` decorator. |
| `errors.py` | `ApiError` (message + HTTP status) + `require_str` validation helper. |
| `scheduling.py` | **The engine — currently a STUB** (only `INTERVALS` + `interval_for`). The real logic is unbuilt. |

### 🥩 Features (one slice each)
| Feature file(s) | Screen / job |
|---|---|
| `js/screens/auth.js` + `routes/auth.py` | Login / signup |
| `js/screens/onboarding.js` + `routes/user.py` | First-run 3-step onboarding |
| `js/screens/add.js` + `routes/subjects.py`, `routes/topics.py` | Add subjects & topics |
| `js/screens/dashboard.js` + `js/schedule.js` | Homepage: priorities feed + coverage |
| `js/screens/subject-detail.js` + `js/screens/log-review.js` | One subject's detail + logging a review |
| `js/screens/settings.js` | Account settings |
| `back-end/scheduling.py` (+ its routes) | The spaced-repetition engine (Slice 7) |

---

## 4. The flow every button follows (learn this once)

Every single action in the app is the **same six hops**:

```
1. You click a <button data-action="X">
2. → the ONE listener in main.js finds the nearest data-action and hits `case 'X'`
3. → it calls a function in that feature's screens/*.js
4. → that function calls api('METHOD', '/api/…')            (js/api.js)
5. → api() runs EITHER the mock (api.mock.js, localStorage)
        OR fetches Flask :5050 → routes/*.py → db.py → SQLite
6. → back in the screen function: update `state`, then route() re-renders the screen
```

Turn on **`?debug=1`** and open DevTools → Console: the `trace()` lines print each hop as it happens, so
you can *watch* this list execute. That is the fastest way to understand any feature.

---

## 5. Three worked flows (click → JS → backend → database)

### 5.1 "Sign in" — the pattern in miniature
1. You click **Sign in** = `<button data-action="do-login">`.
2. `js/main.js` listener → `case 'do-login' → doLogin(btn)`.
3. `js/screens/auth.js` `doLogin()` reads `#login-email` + `#login-pw`, checks they're not empty, then
   `api('POST', '/api/auth/login', {email, password})`.
4. `js/api.js`:
   - **MOCK:** `api.mock.js` finds the user in `localStorage`, checks the password → returns
     `{token: 'mock.<id>', user}`.
   - **REAL:** `fetch('http://127.0.0.1:5050/api/auth/login')` → `routes/auth.py` `login()` → `db.py`
     `SELECT` the user → `auth.py` `verify_password` → `encode_token` (JWT) → returns `{token, user}`.
5. Back in `doLogin()`: `setToken(token)` saves the JWT to `localStorage` (`ncea_token`),
   `state.currentUser = user`, then `navigate('#dashboard')`.
6. The hash change fires `router.route()` → sees `#dashboard` → `renderDashboard()`.

### 5.2 "Add subject" — the same pattern, writing data
1. `<button data-action="add-subject">` → `openAddSubject()` (`js/screens/add.js`) shows a modal.
2. **Save** → `data-action="add-subject-submit"` → `submitAddSubject()` →
   `api('POST', '/api/subjects', {name})`.
3. **MOCK:** insert a subject row into `localStorage`. **REAL:** `routes/subjects.py` → parametrised
   `INSERT INTO subjects (…) VALUES (?, …)` → returns `{subject}`.
4. `onDone → route()` re-renders the dashboard with the new subject. *(This one is fully built on both
   paths — it's F1.)*

### 5.3 "Log review" — the heart of the app (mock-only today)
1. On the dashboard a priority card has `<button data-action="open-log" data-topic-id="7">`.
2. `main.js` `case 'open-log'`: fetches `GET /api/subjects`, finds topic 7, calls `openLogReview(topic,
   route)` in `js/screens/log-review.js`.
3. The modal shows confidence pills + **Evidence** + **Reflection** boxes. You pick a confidence and click
   **Save** → `data-action="lr-submit"` → `submitLogReview()`.
4. `api('POST', '/api/log-review', {topicId, confidence, evidence, reflection})`.
5. **MOCK path** (`api.mock.js`): `review_count += 1` → `interval = intervalFor(count)` (1→1, 2→3, 3→7,
   4+→14 days) → `next_due = today + interval` → push a row into `reviews[]` (with evidence + reflection) →
   save. **REAL path: does not exist yet** — there is no `POST /api/log-review` route and no
   `scheduling.log_review()`. Building it is Slice 7.
6. `route()` re-renders; `schedule.buildPriorities()` recomputes; topic 7 drops off "today's" list because
   its `next_due` is now in the future.

---

## 6. The router "bouncer" (runs on every load & hash change)

`router.route()` decides the screen in this order (see `js/router.js`):

1. **No token** → not logged in → hide topbar, show `#screen-auth`, `hydrateAuth()`.
2. **Token but no `state.currentUser`** → `GET /api/auth/me` to rehydrate (if it fails, the token was
   stale → clear it and start over).
3. **Logged in but `onboarding_done == 0`** → show `#screen-onboarding`.
4. **Otherwise** → show the topbar and pick by hash: `#settings` → `renderSettings()`; `#subject-<id>` →
   `renderSubjectDetail(id)`; anything else → `renderDashboard()`.

This is why the app "just knows" where to send you: the bouncer re-runs on every navigation.

---

## 7. The scheduling rules (what the engine does — spec)

These live in `CLAUDE.md` and are mirrored in `js/schedule.js` (client) today; the real Python engine
(`back-end/scheduling.py`) implements them in Slice 7.

- **Intervals by review count:** `{1:1, 2:3, 3:7}` days; **14** for 4+. Each review pushes the next one
  further out — that's spaced repetition.
- **Priority score** = `(today − next_due).days` (higher = more overdue). `next_due` empty = brand-new.
- **Daily list:** most-overdue first, capped at `daily_cap` (3–8, default 5); leftover slots filled with
  NEW topics (≤1 per subject).
- **Coverage** = topics reviewed at least once ÷ active topics, as a %.
- **Assessment ("internal") mode:** bump each topic to `review_count = max(current, 3)`, `next_due = today
  + 7`, log a review tagged `internal_assessment`.
- **Golden rule:** the **server** owns "today" (`date.today()`), ISO `YYYY-MM-DD` strings only — **never** a
  JavaScript `Date` in scheduling (timezone drift is the #1 bug in these apps). *(The mock uses the local
  date as a deliberate, documented dev-only exception.)*

---

## 8. Have vs. don't-have (so you know what's left to build)

| Area | ✅ Real backend | ⚠️ Mock-only (browser) | ❌ Not built anywhere |
|---|---|---|---|
| Accounts | signup, login, me, logout, JWT, hashing | — | password reset |
| Onboarding | mark done; add first subject/topic | — | — |
| Subjects/Topics | create subject, list subjects, create topic | — | edit / delete / archive endpoints |
| **Scheduling engine** | — | log-review, priorities, coverage (`schedule.js` + `api.mock.js`) | `scheduling.py` real logic; `GET /api/priorities`; `POST /api/log-review` |
| Subject detail | — | coverage, history, confidence, internal mode | server assessment-mode endpoints |
| Evidence / Reflection | — | stored in the mock only | DB columns + server persistence |
| Settings | — | UI only (daily cap not saved) | `PUT /api/settings` |
| Tests | 15 API tests (F1) pass | — | `test_scheduling.py` |

**Plain summary:** *F1 (accounts → onboarding → add subjects/topics) is real and tested. Everything about
reviewing — the actual point of the app — is currently faked in the browser. That is your build target.*
