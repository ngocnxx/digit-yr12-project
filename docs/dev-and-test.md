# Development & testing guide

How to run and verify the NCEA Review Navigator at three levels of integration, in
two modes (bare-metal / Docker). The guiding idea is a **testing pyramid**: cheap,
fast, isolated checks at the bottom; fewer, slower, full-stack checks at the top.

```
        ▲  end-to-end  (browser → web → api → sqlite)      slow, few, highest confidence
       ╱ ╲   level 3
      ╱   ╲ front-end + back-end  (HTTP contract, CORS)    medium
     ╱     ╲  level 2
    ╱───────╲ front-end only · back-end unit/api           fast, many, isolated
       level 1
```

| Level | What runs | What it catches | Primary tools |
|---|---|---|---|
| **1 · front-end only** | static SPA + in-browser mock | markup/CSS/router, the whole UI journey, validation, graceful API-down handling | browser (MCP preview), `task web:dev` |
| **1 · back-end only** | Flask test client + temp SQLite | route logic, auth, validation, scoping, status codes | `pytest`, `ruff` |
| **2 · front-end + back-end** | SPA + Flask + sqlite, separate origins | the JSON contract + CORS, real fetch round-trips | `task api:smoke` (curl), browser |
| **3 · end-to-end** | browser drives SPA → API → DB | the whole user journey (signup → onboarding → dashboard), persistence, logout | browser MCP (preview / Chrome / computer-use) |

> **Ports (macOS):** the API's host port is **5050**, not 5000 — macOS *AirPlay Receiver*
> (ControlCenter) permanently binds `:5000`. The container still listens on 5000 internally;
> only the published host port differs. Override anything with `API_PORT` / `WEB_PORT`
> (e.g. `task api:dev API_PORT=5055`), and keep `front-end/js/config.js` `API_BASE` in sync.

---

## Quick reference (`task`)

Task runner: [Taskfile.yml](../Taskfile.yml) (install: `brew install go-task`). Run `task` to list all.

**Docker first.** The short tasks run the containers: the same on this Mac (Docker Desktop), in the
devcontainer and in Codespaces. Host mode (no Docker) stays under `web:*`, `api:*`, `db:*`.

```bash
task setup     # one-time: check Docker, create .env, build the images
task up        # ⭐ start web + api, wait until healthy, print the addresses
task dev       # same stack in the foreground, live sync of your edits (Ctrl+C stops)
task test      # ⭐ backend tests (pytest) inside the API image
task smoke     # HTTP smoke tests against the running stack (API flow, page, edge, CORS)
task smoke:s3  # database-in-S3 mode (two API copies + a local fake S3)
task image     # the API image is Lambda-ready
task verify    # ⭐ Definition of Done: setup + up + test + image + smoke + smoke:s3
task logs      # follow logs (task logs -- api)     task ps   # health
task down      # stop (data kept)                   task reset  # wipe the Docker database
task lint      # advisory ruff check (not in the gate: the submitted code stays as written)
```

```bash
# host mode (no Docker)
task api:setup       # venv + deps + back-end/navigator.db
task api:dev         # Flask dev server → :5050
task web:dev         # the page → :5500 (calls the API on :5050)
task api:test        # pytest in the venv
task api:smoke       # HTTP smoke test against a running API
task db:reset        # wipe + recreate back-end/navigator.db
```

---

## One entry point: `index.html` (+ a front-end-only mock)

There is **one** HTML file — `front-end/index.html`. Which backend it talks to is decided at
runtime, not by a second file. It **defaults to the mock** so the SPA runs standalone for
prototype/mockup review:

| URL | Backend | Needs Flask/DB? | Use for |
|---|---|---|---|
| `index.html`          | **in-browser mock** (default) | **no** | prototype/mockup review, front-end-only dev |
| `index.html?real=1`   | real Flask API (`config.js` `API_BASE`) | yes | testing against the live backend |
| `index.html?mock=1`   | force mock (explicit) | no | — |

The mock mirrors the real API **contract exactly** (same request bodies, response shapes, status
codes, and error messages) and persists to `localStorage`, so the entire UI — signup, onboarding,
dashboard, validation errors, reload-persistence — works with only HTML/CSS/JS. In production, the
deploy injects `window.NRN_API_BASE` (a real URL), which automatically selects the real backend.
The `api()` calls are the seam, so nothing else changes.

> **Serving note:** the SPA uses native ES modules, which browsers only load over `http(s)` — so it
> must be *served* (e.g. `task web:dev`, one command), not opened as a `file://` double-click.

### Standalone 3-file prototype (`README/prototype/`)

For mockup/prototype review with **only HTML/CSS/JS** — no server, no Python, no backend, and no
backend/DB code in sight — generate a portable 3-file package (HTML, CSS, JS kept isolated):

```bash
task web:prototype                   # → README/prototype/{index.html, styles.css, app.js}
open README/prototype/index.html  # or just double-click it in Finder
```

`scripts/build-prototype.py` concatenates the four `css/*.css` into one `styles.css`, and flattens the
ES modules into one **classic** `app.js` (no `import`/`export`, mock backend bundled in and on by
default). A classic `<script src="app.js">` is what lets the page open straight from the filesystem
(`file://`) — ES modules are blocked there. It's a **generated artifact**: edit the real source under
`front-end/js` + `front-end/css`, then re-run `task web:prototype`; never hand-edit `prototype/`.

| Entry | Opens via | Backend | Use |
|---|---|---|---|
| `front-end/index.html`          | served (`task web:dev`) — ES modules need http(s) | mock (default) / `?real=1` | dev loop |
| `README/prototype/index.html`| **double-click** (`file://`), 3 isolated files | mock (built in) | hand to reviewers — no backend/DB |

> *(An earlier `index.dev.html` was a throwaway verification harness — now deleted. Pointing the SPA
> at a different real API origin is done with `window.NRN_API_BASE`, not a second HTML file.)*

## Bare-metal (macOS / Python 3.13)

### Level 1 — front-end only (no backend)
Pure UI loop for HTML/CSS/JS work — **no Flask, no DB**. The mock backend serves the whole
journey (signup → onboarding → dashboard) so you can build and test the UI in isolation.

```bash
task web:dev                       # serve the SPA → :5500
# open http://127.0.0.1:5500/   → full app on the in-browser mock backend (default)
```

The page defaults to the mock, so everything runs client-side and persists to `localStorage` — no
Flask, no DB. This is the recommended first-stage loop; add `?real=1` (or set `window.NRN_API_BASE`)
to switch to the real backend later, with no code change.

### Level 1 — back-end only (unit/API)
No browser, no network. Flask's test client + a throwaway SQLite file (`tmp_path`).

```bash
task api:test                     # pytest: auth, onboarding, subjects/topics, 400/401 paths
task api:lint                     # ruff check
```

### Level 2 — front-end + back-end (contract + CORS)
Two terminals (separate origins, CORS bridges them):

```bash
task api:dev                      # terminal 1 → http://127.0.0.1:5050
task web:dev                      # terminal 2 → http://127.0.0.1:5500
task api:smoke                    # terminal 3 → drives the F1 flow over HTTP, asserts codes
```

### Level 3 — end-to-end
With both servers up (above), open `http://127.0.0.1:5500/?real=1` (the `?real=1` makes the SPA hit
the live Flask API instead of the mock) and walk the journey, or drive it with a browser MCP
(see *Visual verification*).

---

## Docker (the default)

One command brings up both services (web = nginx, api = Flask + gunicorn, SQLite on a volume) and
waits until both are healthy:

```bash
task up
# page → http://127.0.0.1:5500   edge (like AWS) → http://127.0.0.1:8080   api → http://127.0.0.1:5050
task verify                          # everything automated must pass
task down                            # stop (data kept)
```

- **Level 1 (back-end only) in Docker:** `task test` (pytest inside the API image).
- **Level 2 (contract + CORS + nginx):** `task smoke` runs `scripts/smoke.sh` and `scripts/smoke-web.sh`.
- **Edge :8080:** the same nginx, shaped like CloudFront: one origin, `/api/*` forwarded, 403 for a
  missing file, and the production CSP (script hash computed from `index.html` at build). Use it to
  prove the app runs under the production headers before deploying.
- **Devcontainer / Codespaces:** Python 3.13 + Docker-in-Docker + Task. `postCreateCommand` runs
  `task setup`; then `task up` / `task verify` exactly as on the Mac. In Codespaces the page calls
  `/api/*` on its own address (nginx forwards it), so the forwarded ports stay private.

---

## Visual verification (browser MCPs)

The app is intentionally **npm-free** (no framework, no bundler), so there is no in-repo
Playwright/Jest suite. Browser verification is done with whatever MCP browser driver is
available — they all drive the *real* rendered SPA:

- **Claude Preview MCP** (used in this repo): `preview_start` a server from `.claude/launch.json`,
  then `preview_click` / `preview_fill` / `preview_screenshot` / `preview_snapshot`, and
  `preview_resize` (mobile / tablet / desktop) for responsive + dark-mode checks. Fastest, DOM-aware.
- **Claude-in-Chrome MCP** — drive a real Chrome tab when you need genuine browser behaviour.
- **computer-use / Playwright MCP** — alternatives for full OS-level or scripted browser control.

**E2E visual checklist** (level 3):
1. Auth screen renders (logged-out, no token).
2. Sign up (Year 12) → onboarding step 1.
3. Get started → pick Biology → add subject → step 3.
4. Add topics (incl. one with a standard number) → Finish.
5. Placeholder dashboard shows the greeting + the subjects/topics just created.
6. Resize to mobile (375px) and desktop (1280px) — layout holds.
7. Reload — still logged in (JWT in `localStorage` `ncea_token`, `/api/auth/me` re-hydrates).
8. Log out → back to the auth screen.
9. Console shows **no errors** throughout (`preview_console_logs level=error`).

> If `API_BASE` must differ from `config.js` during a verification run (e.g. testing on
> free ports), set `window.NRN_API_BASE` before the modules load rather than editing
> committed code.
