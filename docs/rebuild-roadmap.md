# Rebuild Roadmap — build it yourself, slice by slice, and document it

> **Goal:** rebuild this project *yourself*, in small stages you understand, and produce the evidence an
> NCEA internal wants (planning, iterative development, trialling/testing, refinement, justified
> decisions). The existing code is your **reference / worked example** — you assemble each file line by
> line, in your own words, so you can explain any part of it. Read
> [`architecture-and-flow.md`](architecture-and-flow.md) first.

---

## 0. The two questions this doc answers

**"There are so many files — if I build one screen, it needs `main.js`, `router.js`, `api.js`, the
backend… but those hold code for *every* feature. Which lines do I take? How do I know? Won't copying whole
files look suspicious?"**

Answer, in one sentence: **`main.js`, `router.js` and `api.mock.js` are *registries that grow one entry per
feature* — you never copy them whole; you build a tiny skeleton once, then append only the current
feature's few lines.**

**"Do I have to build all the shared stuff before any screen?"** — Yes, but only a *minimal skeleton*
(Slice 0). Then you thicken it a little inside each feature slice.

---

## 1. Spine vs. Features (recap)

- **🦴 Spine** = shared plumbing (`index.html`, `config/dom/state/debug/icons.js`, `api.js`, `api.mock.js`,
  `router.js`, `main.js`, `app.py`, `db.py`, `schema.sql`, `auth.py`, `errors.py`). Built **once**
  (Slice 0), then extended a few lines per feature.
- **🥩 Features** = one screen's own file(s): `screens/*.js` + a `routes/*.py`.

### Proof that a feature owns only a few lines
The real `main.js` `switch` has ~20 `case`s. When you build **only auth**, yours is just:

```js
switch (act.dataset.action) {
  case 'auth-tab':  setAuthMode(act.dataset.mode); break;
  case 'do-login':  await doLogin(act);  break;
  case 'do-signup': await doSignup(act); break;
}
```

Three cases — not twenty. You add onboarding's cases when you build onboarding, the dashboard's when you
build the dashboard, and so on. Same with `router.js`: the auth slice only adds

```js
if (!getToken()) { showScreen('screen-auth'); hydrateAuth(); return; }   // ← auth's whole branch
```

### How to KNOW which code belongs to a feature — *follow the thread*
> **button `data-action`** → its **`case` in `main.js`** → the **function it names** (in that feature's
> `screens/*.js`) → the **`api('METHOD','/path')` call** inside it → the **handler for that path** (in
> `api.mock.js`, and later a Flask route).

Take everything on that thread and nothing off it. To *see* the thread, open `?debug=1` and click — the
`trace()` lines print exactly these hops.

### Why this is genuinely your work (not copying)
Because you (a) build the skeleton minimally, (b) add only the current feature's lines, and (c) write every
comment in **your own words**, you can explain every line — which is what "understanding" means for the
assessment. In your write-up, state plainly that you used the reference implementation and rebuilt it slice
by slice. That's honest and it's the best way to actually learn it.

---

## 2. Slice 0 — build the spine skeleton first

**Goal:** an app that **boots to an (empty) auth screen with zero console errors**, and a backend that
answers `/api/health`. No features yet.

**Front-end skeleton**
- `index.html` — `<head>`, the classic serve-guard script, a hidden `#topbar`, five empty
  `<section class="screen hidden">` shells, and `<script type="module" src="js/main.js">`.
- `js/config.js`, `js/dom.js`, `js/state.js`, `js/debug.js` — the small generic helpers.
- `js/api.js` — the `fetch` wrapper + `getToken/setToken/clearToken` + mock dispatch.
- `js/api.mock.js` — `load()/save()/blank()` DB in `localStorage` + an **empty** `routes` table.
- `js/router.js` — `SCREENS`, `showScreen()`, `navigate()`, `route()` with the no-token branch.
- `js/main.js` — the one click listener with an **empty `switch`**, the keyboard block, and startup
  (`route(); hydrateIcons();`). Set `window.__NRN_BOOTED = true` at the top.

**Back-end skeleton**
- `app.py` — app factory, CORS, `ApiError` handler, `/api/health` (no blueprints yet).
- `db.py` + `schema.sql` (start with the `users` table only).
- `auth.py`, `errors.py` — the helpers (needed from Slice 1).

**Trial/test (your first evidence):** `task web:dev` → `:5500` boots, console clean. `task api:dev` →
`curl :5050/api/health` → `{"status":"ok"}`. Screenshot both.

---

## 3. The per-slice FILE MAP (which files pair with which screen)

Build in order. Each row = the **new feature file(s)**, the **spine lines you append**, and **how you prove
it**. Use the Section-4 micro-loop inside every slice.

| Slice | New feature file(s) | Spine files you EXTEND | Prove it |
|---|---|---|---|
| **1 · Auth** | `js/screens/auth.js`; auth markup in `index.html`; input/`.auth-card` CSS; `routes/auth.py` | `main.js`: import auth + cases `auth-tab/do-login/do-signup` + Enter-submit · `router.js`: import `hydrateAuth` + no-token branch · `api.mock.js`: `+POST /auth/signup`, `/auth/login`, `GET /auth/me`, `POST /auth/logout` · `app.py`: register `auth_bp` | sign up on mock → "logged in"; `?real=1` → `pytest` auth (7 tests) |
| **2 · Onboarding** | `js/screens/onboarding.js`; onboarding markup; `routes/user.py` | `main.js`: import + `ob-next/ob-add-subject/ob-add-topic/ob-finish/ob-skip` + Enter-adds-topic · `router.js`: import `hydrateOnboarding` + `onboarding_done==0` gate · `api.mock.js`: `+PUT /user/onboarding` · `app.py`: register `user_bp` · `schema.sql`: `subjects`, `topics` | new account is walked through; flag flips to 1 |
| **3 · Add subjects/topics** | `js/screens/add.js`; `routes/subjects.py`, `routes/topics.py` | `main.js`: import + `add-subject/add-subject-submit/add-topic/add-topic-submit` · `api.mock.js`: `+POST /subjects`, `GET /subjects`, `POST /topics` · `app.py`: register `subjects_bp`, `topics_bp` | add a subject + topic, see it listed; `?real=1` → pytest |
| **4 · Dashboard + priorities** | `js/screens/dashboard.js`; `js/schedule.js`; `js/icons.js`; dashboard CSS | `main.js`: import `setDashTab` + `dash-tab/view-subject/nav-dashboard/nav-settings/do-logout` · `router.js`: import `renderDashboard` + default `#dashboard` branch + show topbar · `api.mock.js`: `GET /subjects` returns topics with `reviews[]` | "today's" list + coverage % render from your data |
| **5 · Subject detail + Log review** | `js/screens/subject-detail.js`; `js/screens/log-review.js`; CSS | `main.js`: imports + `open-log/lr-submit/lr-attach/toggle-internal` · `router.js`: import `renderSubjectDetail` + `#subject-` branch · `api.mock.js`: `+POST /log-review` (mock engine) | logging a review moves the topic's next-due date |
| **6 · Settings** | `js/screens/settings.js` | `router.js`: import `renderSettings` + `#settings` branch · (`nav-settings` case already added in Slice 4) | daily-cap select + logout work |
| **7 · Real engine** | `back-end/scheduling.py` (`log_review`, `build_priorities`, `coverage`, assessment mode); scheduling routes; `tests/test_scheduling.py` | `app.py`: register new blueprints · `schema.sql`: add `evidence`/`reflection` columns · **front-end unchanged** — just add `?real=1` | same screens work against Flask + SQLite; `test_scheduling.py` green |
| **8 · Polish** | — | error states, tone, wellbeing footer, accessibility across the above | wrong inputs + empty states look intentional |

**Why Auth is Slice 1** (not the flashy dashboard): it's the *smallest* feature that crosses all three
tiers (browser → Flask → SQLite), so building it teaches the whole pattern once. Every later slice is that
same pattern with different nouns. *What-if you started at the dashboard:* it depends on subjects, topics,
reviews **and** the engine — four unbuilt things at once, and nothing you could screenshot early.

---

## 4. The micro-loop (do this inside every slice)

Vertical slices (finish one feature end-to-end before the next) mean you always have something to demo and
screenshot — which is exactly the "iterative development" evidence NCEA rewards. Inside a slice, build the
**front-end on the mock first, the backend last** (the mock lets you build and even user-test the whole UI
before writing any Flask):

```
1. HTML skeleton  → trial: open in browser, screenshot the raw structure
2. CSS styling    → trial: refresh, screenshot v1; tweak; refresh; screenshot v2   (shows iteration!)
3. JS on the MOCK → trial: click it — it works on fake data; screenshot + ?debug=1 console
4. Backend        → test: pytest, then add ?real=1 and screenshot the REAL data
5. Refine + log   → note one bug you fixed (before → after) + write the dev-log row
```

*Why this order:* structure before style before behaviour before persistence — each step is visible and
testable on its own. *What-if you wrote JS before the HTML exists:* nothing to attach clicks to. *What-if
you did the backend before the mock:* slower feedback and no UI to see it working.

---

## 5. How to trial & test each sub-step (concrete)

- **HTML/CSS:** edit → **hard-refresh** (⌘⇧R, beats the cache) → screenshot. Change a colour/spacing →
  refresh → screenshot again. Use DevTools → Elements to try a value live before committing it.
- **JS (on the mock):** open `http://127.0.0.1:5500/?debug=1`, open DevTools → Console. Every `trace()`
  narrates a hop as you click — screenshot the console beside the UI as proof the flow runs. Reset your
  test data anytime with `localStorage.clear()` (wipes `nrn_mock_db` + `ncea_token`).
- **Backend:** `task test` after each change (paste the passing output into your log). Then add `?real=1`
  so the same UI hits Flask (`:5050`); repeat the action and screenshot the **real** data (optionally the
  row via a SQLite viewer). Mock and real producing the same result proves the contract is right.

---

## 6. Documenting it for your NCEA internal

- **Dev log** — keep `docs/dev-log.md`, one row per slice/sub-step:
  `Date | Slice | What I built | Trial result | Test result | Screenshot file | Decision & why (what-if)`.
- **Screenshots** — name them in sequence so the *iteration* is visible: `slice1-html.png`,
  `slice1-css-v1.png`, `slice1-css-v2.png`, `slice1-working.png`, `slice1-console.png`, `slice1-pytest.png`.
- **Testing evidence** — paste `pytest` output; keep your **user-test table** (see
  [`user-testing-guide.md`](user-testing-guide.md)); for at least one bug, show *before → fix → after*
  (refinement scores well).
- **Decisions** — the per-slice **why / value / what-if** is your "justify your choices" section. Do a
  quick **5W1H** per slice too (Who = the student user · What = the feature · Why = the value · When = which
  review state · Where = which screen/route/table · How = the micro-loop steps).
- **Version history** — your human operator commits at the end of each slice. *(Per the repo rule, you and
  the AI assistant never run git — a human owns version control.)* The commit list becomes your development
  timeline.
- **Originality** — comments in your own words; state that you used the reference and rebuilt it slice by
  slice. True, and provable by your ability to explain any line.

---

## 7. Quick command reference

```bash
# one-time, only if you'll use the REAL backend
task setup            # create the Python venv + install deps + create the database
task db:init          # (re)create the SQLite database from schema.sql (safe to re-run)

# everyday
task dev              # ⭐ serve the front-end on :5500 (mock — no Flask/DB needed)
task api:dev          # run the Flask API on :5050 (needed only for ?real=1)
task test             # ⭐ lint + backend pytest suite (the everyday quality gate)
task web:prototype    # regenerate README/prototype/ (classic bundle for double-click sharing)
task db:shell         # open the SQLite database to inspect real rows
```
Open the app with `?debug=1` to watch the flow in the console, `?real=1` to hit the real backend.
(`task dev` and `task web:dev` are the same server; `task dev` is the starred shortcut.)
