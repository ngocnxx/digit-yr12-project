# AWS Hosting Plan and Handoff: NCEA Review Navigator

Prepared 2026-09-26 for the working copy `/Users/ngocnx1501/digit-yr12-project`. Every factual claim below comes from today's three read-only audits (back-end, front-end, delivery), today's three research reports (compute, data, infrastructure), the implementation and test runs later the same day (sections 1.1 and 8.1), a read-only check of the repo files quoted, or the official page cited next to it. Anything marked **VERIFY** was not proven today and must be checked before anyone relies on it. Anything marked **unverified** could not be confirmed from an official source and is not relied on. Prices are USD for ap-southeast-2 (Sydney) from the AWS Price List API, before any tax. Lines marked **estimate** depend on assumed workloads.

The submitted folder `/Users/ngocnx1501/submitted-digit-yr12` is frozen. Nothing in this plan touches it, except one GitHub setting that only a human should change (section 1, finding C1).

Revision note 1 (same day): this version applies a second review. The main changes are: the Lambda concurrency quota increase is now a **required** step before the URL is shared, with a lower API throttle until it is granted; the ECR lifecycle rule can no longer expire the live image; the web bucket is versioned and every front-end deploy is saved locally for rollback; `deploy-web.sh` refuses to upload an `index.html` whose inline script no longer matches the live CSP; the first publish is a STOP point; and several version facts are now confirmed.

Revision note 2 (same day, after implementation): the database design changed from SQLite on Amazon EFS to **"the S3 object is the database"**. The SQLite file is one object in a private, versioned S3 bucket, and every save is a conditional write (section 2). It is implemented in `back-end/s3db.py` and verified locally: 60 back-end tests, 7 deliberate code mutations all caught, and a two-copy smoke test against a local S3 (section 8.1). All the code changes in section 5 are now **done** in the working copy. Only Terraform, `deploy-api.sh`, `deploy-web.sh`, `smoke-cloud.sh`, the concurrency quota gate and the CloudFront settings remain for the cloud session. The VPC, EFS, mount targets, security groups and AWS Backup are gone from the design; EFS is kept only as the fallback (section 2).

---

## 0. Decision in one screen

| Question | Decision | Why, in one line |
|---|---|---|
| Where | One AWS account owned by an adult (the student's father), Region **ap-southeast-2 (Sydney)** | Sydney needs no opt-in, is about 5% cheaper and adds only about 30 ms (measured today from this Mac). The NZ Region (ap-southeast-6, opt-in) no longer has a hard blocker now that EFS is out of the design, but Sydney stays the default unless the user chooses otherwise (decision 12.3). |
| The URL | One **CloudFront** distribution: `https://<id>.cloudfront.net` | Page and API share one origin, so `js/config.js` already returns `''` and no CORS is needed. |
| HTML, CSS, JS | Private, versioned **S3** bucket behind CloudFront **OAC** | Cheap, private, full control of headers and caching. |
| API front door | CloudFront `/api/*` -> **API Gateway HTTP API** -> Lambda | Passes the `Authorization: Bearer` token through and has built-in throttling. With a Lambda Function URL behind OAC, the Bearer token cannot reach Flask as `Authorization` without workarounds, and every POST/PUT needs a client-computed body hash. |
| Flask on Lambda | The existing `back-end/Dockerfile`, which now also holds the AWS Lambda Web Adapter 1.1.0 (pinned by digest) and `boto3`, shipped as a container image in **ECR** | It is the same image and gunicorn stack that passed 60/60 tests today. A build proved the adapter digest (`/opt/extensions/lambda-adapter` is present). |
| Database | **The S3 object is the database.** The SQLite file is one object, `db/navigator.db`, in a private, versioned data bucket. Each Lambda copy works on a copy in `/tmp` and saves it with a conditional PUT before it replies (`back-end/s3db.py`). **No VPC and no EFS.** | Implemented and verified locally today (section 2). A Lambda outside a VPC reaches S3 directly, so there is no network to build. |
| What S3 does | The static site, the database object, the photos (one object each) and the Terraform state | Three private buckets: web, data and state. |
| Secrets | `SECRET_KEY` from Terraform `random_password`, passed as an encrypted Lambda environment variable; the app **refuses to start** with the dev key (implemented) | Simple, and needs no code to read a secret store. |
| Infrastructure as code | Terraform 1.16.x (1.16.4 is current), `hashicorp/aws ~> 6.66` (6.66.0 released 2026-09-21), `hashicorp/random ~> 3.9`, flat root module in `infra/`, remote state from `infra/bootstrap/` (S3 native lock file, no DynamoDB) | Current, supported, simple to read end to end. |
| Capacity gate | The Lambda **concurrency quota increase is required** before the URL is shared. Until it is granted, the API throttle is 10 req/s with a burst of 20 | New accounts have reduced Lambda concurrency and memory quotas, and a throttled Lambda reaches the browser as a 500 (finding H10). |
| Monthly cost | Classroom (about 30 students): **well under USD 1** (estimate), covered by new-account credits | Almost everything sits inside always-free allowances or costs cents. There is no NAT, no VPC and no always-on server. |
| Code changes before go-live | **Done in the working copy:** photos out of `GET /api/subjects` (Lambda 6 MB response limit), a fail-closed `SECRET_KEY` and database location, no student emails in logs, and the S3 database. **Still required:** the concurrency quota increase, plus the CloudFront and upload settings in section 4 | Each code fix is covered by tests (section 1.3, Status column). |
| Honest ceiling | The S3 database is a **one-or-two-class** design: database under about 20 MB, about 1 to 2 writes per second sustained. A burst of 30 writes sees retries and 1 to 2 s latency. **Not suitable for 1,000 students.** | Move to a managed database (or EFS) when a section 10 trigger fires; the `[s3db]` log lines make each trigger measurable. |
| Do today, outside AWS | Make GitHub `ngocnxx/submitted-digit-yr12` **private**, after adding your teacher as a collaborator if they still need to see the submission | It is public and tracks `back-end/navigator.db`, which holds real accounts. A private repo is hidden from anyone not added. |

Decisions the user must make (defaults in section 12): who owns the account and which plan (Free plan or Paid plan), the Region (Sydney by default), open sign-up versus an invite code, and what the student's AWS login may do. Already decided and implemented in the working copy: a minimum password of 8, neutral hosted error text, keeping the token unless the answer is 401, and a 25 s browser request timeout.

---

## 1. Brutal assessment of the real deliverables

### 1.1 What is genuinely good

- The app works. After today's changes, **60/60 back-end tests pass** on the host and inside the built image: the 34 original tests, 11 in `tests/test_cloud.py` and 15 in `tests/test_s3db.py`. The normal Docker stack passed `scripts/smoke.sh` 9/9 and a 33-check extended smoke test. A browser test showed that the photo is fetched only when "View note" opens (`GET /api/reviews/<id>/attachment`) and that it renders, with no console errors. (Earlier the same day, before the changes: 34/34 tests, a 25-check smoke test passed 25/25, and a real browser signup through nginx worked with no console errors.)
- The S3 database is tested hard. `tests/test_s3db.py` runs two app copies against an in-memory fake S3 (`tests/fake_s3.py`), like two Lambda copies. Seven deliberate code mutations (blind overwrite, always upload, reply before save, fingerprint after migration, photo back in the list, no key guard, delete guard off) were each caught by the tests. moto 5.1.21 and 5.1.14 were checked to match real S3 on all six conditional-write rules, and the compose profile `s3` (moto plus two API copies sharing one database object) passed `scripts/smoke-s3.sh` (section 8.1).
- Data isolation is real. Every protected route scopes to `g.user_id` and the audit found no IDOR (Insecure Direct Object Reference: reading another user's data by changing an id). All SQL is parameterised. The new photo route checks ownership the same way.
- Confidence really cannot change the schedule. `routes/reviews.py` passes only the topic and `today()` into `scheduling.log_review`, which has no confidence parameter. A test locks this in (`test_log_review_stores_optional_fields_without_affecting_schedule`), and it still passes.
- The design is cloud-friendly. A new connection is opened and closed per request, SQLite runs in its default rollback-journal mode, the only outbound calls are to S3 (and only in S3 mode), the Docker image contains only code (`.dockerignore` excludes `.env`, `*.db`, `.venv`), and `/api/health` now touches the database.

### 1.2 Scorecard

| Area | Verdict |
|---|---|
| Local app (bare metal and Docker) | **Works.** 60 tests (host and image), `smoke.sh` 9/9, a 33-check extended smoke test, `smoke-s3.sh` across two copies, a browser test, isolation and the confidence rule are all verified. |
| GitHub, working copy (`ngocnxx/digit-yr12-project`, private) | `develop` is commit 0286f21 "adjusted code", pushed at 17:51 NZST today. Today's changes are **uncommitted** in the working tree (nothing is committed unless the user asks). `main` is a June stub (94c34e6). The last CI run on GitHub was **red**; the working copy's `ci.yml` now has no ruff steps and runs only on `v*` tags on `main` and by manual dispatch. There is no branch protection. |
| GitHub, submitted repo (`ngocnxx/submitted-digit-yr12`, public) | **Privacy problem**: it tracks a database with real accounts, plus the student's full-name assessment PDFs. The repo is frozen. |
| Cloud readiness | **Code ready, cloud not built.** The 3 code blockers are fixed and the S3 database is implemented and tested locally. Still missing: Terraform, `deploy-api.sh`, `deploy-web.sh`, `smoke-cloud.sh`, the concurrency quota gate on a new account, and the CloudFront settings. Terraform is not installed. |
| Docs and tooling | CLAUDE.md, Taskfile, `docs/` and `.env.example` are partly stale. CLAUDE.md actively tells an agent to run `ruff format`, which must not happen. CICD-HANDOFF.md is superseded by this document. |

### 1.3 Findings

"Blocks MVP" means the first cloud deploy must not go live until the item is fixed or configured as described. "Status" is the state of the working copy on 2026-09-26, after today's changes. Line numbers in the Evidence column are from the audit, before those changes.

| Sev | Finding | Evidence | Fix | Blocks MVP | Status |
|---|---|---|---|---|---|
| Critical | **C1.** The public submitted repo tracks `back-end/navigator.db` (real accounts, likely minors). With a 4-character minimum password, offline cracking of the hashes is feasible. | `git ls-files` lists it. `gh api` shows the repo is public with 0 forks. `.gitignore:220-222` cannot untrack a file that is already tracked. | A human makes the repo private today (Settings, General, Danger Zone, Change visibility). Ask the school before any history purge. Never copy this file anywhere. | No, but do it first | Open: a human action. |
| Critical | **C2.** `GET /api/subjects` returned every photo inline. Three maximum-size photos give an 8,389,715-byte response, over Lambda's 6,291,456-byte limit. The dashboard then fails on every load, and there is no delete route to recover. | `routes/subjects.py:40-49,107-111`; `routes/reviews.py:17` (2,800,000 characters per photo). Measured: 1 photo 2,796,643 B, 2 photos 5,593,179 B, 3 photos 8,389,715 B. Lambda quotas page: 6 MB synchronous response. | The list returns `hasAttachment` plus the review `id`; the photo is fetched one at a time (sections 5.3 to 5.7). | **Yes** | **Fixed.** Owner-only `GET /api/reviews/<id>/attachment` and lazy loading in `subject-detail.js`; covered by `tests/test_cloud.py` and a browser test. In S3 mode each photo is its own S3 object. |
| Critical | **C3.** `SECRET_KEY` silently falls back to `dev-insecure-change-me`. A token forged with that string got 200 on `/api/auth/me` as another user. | `app.py:36`, `docker-compose.yml:20`, `.env.example:5`. | Generate the key with Terraform `random_password`, and fail closed in `create_app` (section 5.2). | **Yes** | **Fixed** in code: on Lambda or with `APP_ENV=production` the app refuses the dev key or any key under 32 characters; on Lambda it also refuses to start unless `S3DB_BUCKET` is set or `DATABASE_PATH` starts with `/mnt/`. The `random_password` is for the cloud session. |
| Critical (config) | **C4.** By default CloudFront strips `Authorization` from GET requests, so every student is bounced back to login. The obvious half-fix (forward the header but keep a caching policy) serves one student's data to others for up to 24 h. | AWS CloudFront custom-origin header table; `api.js:18`. | On `/api/*`: CachingDisabled plus AllViewerExceptHostHeader, and Flask sends `Cache-Control: no-store` (sections 4.6 and 5.2). A ready-made fallback policy is in `web.tf` behind a variable. | **Yes** | Open: the CloudFront settings (cloud session). Flask side done: `no-store` on `/api/*` (tested). |
| High | **H1.** Nothing set up the database on Lambda. `/var/task` is read-only, and `/api/health` said ok while signup returned 500. | `app.py:34-37,64-66`; `db.py:62-78`; reproduced. | S3 mode: `S3DB_BUCKET` plus `DATABASE_PATH=/tmp/navigator.db`; the first request creates `db/navigator.db`. Health touches the database and returns JSON 503 on failure. | **Yes** | **Addressed.** Health touches the DB (tested); S3 mode is tested against the fake S3 and moto. The real bucket comes with Terraform. |
| High | **H2.** PBKDF2 runs 1,000,000 iterations: 0.534 s per verify on one core. At Terraform's defaults (128 MB, 3 s), login is estimated at about 7.4 s, so it times out. | `auth.py:28`; Werkzeug 3.1.8 default. | Use memory 1024 MB (about 0.9 s estimated) and a 20 s timeout. Keep the iterations. Check the account's memory quota first (section 7.2 step 7). | **Yes** | Open: Terraform settings. Signup now hashes the password before opening the database, so the slow hash no longer sits between the database download and the save. |
| High | **H3.** CICD-HANDOFF.md recommends a Lambda Function URL behind CloudFront OAC. With OAC, the viewer's Bearer token cannot reach Flask as `Authorization` without workarounds: the default `always` mode replaces the header with CloudFront's own SigV4 signature; the `no-override` mode passes it through, but Lambda then validates it as a SigV4 signature, so a Bearer JWT still fails; renaming the header (the adapter's `AWS_LWA_AUTHORIZATION_SOURCE`) needs front-end and adapter changes. Every PUT/POST also needs a client-computed `x-amz-content-sha256`. | AWS CloudFront OAC-for-Lambda page; adapter README. | Use an API Gateway HTTP API origin. | **Yes** (design) | Decided: HTTP API. |
| High | **H4.** Reserved concurrency 1 (a CICD-HANDOFF.md option) throttles a single student, because the page fires requests in parallel. It also may not be settable on a new account, because at least 100 must stay unreserved and new accounts have reduced quotas. | `dashboard.js:32-35` (Promise.all), `main.js:176-178`; Lambda quotas page. | No reservation in the MVP; the S3 design does not need one for safety, because conditional writes make many copies safe. Reserve 10 once the account quota is at least 110. | **Yes** (design) | Decided: no reservation. |
| High | **H5.** A typical SPA fallback (403/404 rewritten to `index.html` with 200) turns failed saves into a fake "Log saved!". | Reproduced in a harness. `custom_error_response` is per distribution, so it also hits API errors. | Use `default_root_object = "index.html"` and **no** custom error responses. Hash routing needs none. | **Yes** (config) | Open: CloudFront setting (cloud session). |
| High | **H6.** If S3 objects lack a JavaScript Content-Type, the ES modules refuse to run and students see developer instructions. | Reproduced: "Expected a JavaScript-or-Wasm module script ... binary/octet-stream". | Upload with `aws s3 sync` (sets types by extension) and check with curl. | **Yes** (config) | Open: `deploy-web.sh` and `smoke-cloud.sh` (cloud session). |
| High | **H7.** CI was red: `ruff: command not found` (run 36222056289). pytest has never run in CI on the current code. | `ci.yml:20-30`; ruff is no longer in `requirements.txt`. | Remove the two ruff steps. Never run `ruff format`. | No (blocks CI/CD) | **Fixed** in the working copy: no ruff steps; CI runs only on `v*` tags on `main` plus manual dispatch, and locally through `act`. Not pushed yet. |
| High | **H8.** CICD-HANDOFF.md points a new session at the frozen repo and gives a false test-recovery recipe: the "deleted" tests were 0-byte files. | CICD-HANDOFF.md:11-16, 113-125, 332; `git ls-tree -r -l 34c25d0^`. | Superseded by this document. Do not reuse it as a prompt. | No | Superseded. |
| High | **H9.** No cloud assets exist: no Terraform, no deploy scripts, and Terraform is not installed. | `which terraform`; no `*.tf` files. | Sections 5 to 7. | **Yes** | Partly: the Dockerfile adapter lines are done. Terraform, `deploy-api.sh`, `deploy-web.sh` and `smoke-cloud.sh` remain (cloud session). |
| High | **H10.** A new account's Lambda concurrency quota, not the API throttle, is the real ceiling. AWS states that new accounts have reduced concurrency and memory quotas but does not publish the figure (earlier notes said about 10; that figure is **unverified**). Lambda does not queue synchronous calls: a throttled Lambda behind an HTTP API reaches the browser as a **500**, and stage throttling returns **429**. With PBKDF2 logins of about 0.9 s and multi-second cold starts, a class opening the app together can exceed a small quota. Before today's fix, any such error on `/api/auth/me` silently logged the student out, and other screens show "Request failed (500)". | Lambda quotas page; AWS re:Post answer on API Gateway proxy turning a Lambda 429 into 500 (community source, not the Lambda docs); `router.js:53-63`; `auth.py:28`. | **Required:** request quota `L-B99A9384` (section 7.2 step 7) and do not share the URL until `get-account-settings` shows at least 100. Until then the stage throttle defaults to 10 req/s, burst 20. Clear the token only on 401. | **Yes** | Router part **fixed**: `router.js` clears the token only on 401. The quota gate is still required. |
| High | **H11.** The browser gave up after 10 s (`api.js:10`, `REQUEST_TIMEOUT_MS = 10000`). A cold start plus a login, or a 2.8 MB photo on a slow mobile uplink, can pass 10 s. The page says "The server took too long", but the POST may still finish on the server. A second tap on Save then runs `/api/log-review` twice and advances `reviewCount` twice, which moves the schedule without the student meaning to. | `api.js:10,27`; `routes/reviews.py:48-96` (no idempotency key); `routes/reviews.py:17`. | `smoke-cloud.sh` times the first call after a deploy and the signup, and fails above 8 s. Raise the timeout to about 25 s. Lasting fix: shrink photos in the browser and add an idempotency key (phase 2). | Measure: **Yes** | **Partly fixed:** `REQUEST_TIMEOUT_MS = 25000`. A double tap still counts twice. (A re-run after an S3 clash never counts twice: its first attempt is thrown away.) |
| Medium | **M1.** Races appear with 2 or more Lambda environments. Two concurrent log-reviews gave `reviewCount` 1 with 2 review rows. Two concurrent creates gave duplicate "Bio" subjects. | `reviews.py:55-74`, `subjects.py:79-90`; reproduced. Locally gunicorn has 1 worker, so this never showed. | `BEGIN IMMEDIATE` in the 3 write routes (within one copy); across Lambda copies the S3 conditional writes re-run the loser (section 2). | Recommended | **Fixed.** `smoke-s3.sh`: 20 parallel reviews across two copies gave `reviewCount` 20 and 20 rows; 10 identical parallel creates gave one 201 and nine 400. |
| Medium | **M2.** Student emails (likely minors) are printed to stdout, which on Lambda goes to CloudWatch with "never expire" retention by default. | `routes/auth.py:41,72`. | Drop emails from the prints. Terraform creates the log group with 14-day retention. | **Yes** (before real students) | **Fixed** and tested (`test_logs_do_not_contain_emails`). The retention is for Terraform. |
| Medium | **M3.** Auth is weak for a public URL: 4-character passwords, no rate limit, email enumeration at signup, 30-day tokens that cannot be revoked, and login timing (2 ms vs 505 ms) shows whether an email exists. | `routes/auth.py:15,56-58,77-80`; `auth.py:19`. | MVP: API stage throttling plus a budget alert, and a minimum of 8 characters. Later: WAF, 7-day tokens, a dummy hash on login miss. | Partly | **Partly fixed:** minimum password 8 (back-end, front-end, placeholder, tests, `scripts/smoke.sh`). Rate limit, enumeration, token lifetime and timing remain. |
| Medium | **M4.** Unvalidated input types cause 500s with HTML bodies, and there is no body-size limit. | Infinity, 1e30, list bodies, a 5,000,000-character colour string (stored). | MVP: `MAX_CONTENT_LENGTH` 3 MiB plus a JSON 413 response. Later: a small validation helper. | Partly | **Partly fixed:** the 3 MiB limit and JSON 413 (tested). Type validation remains. |
| Medium | **M5.** Developer-only text appears on the hosted page: a full-screen "The back-end is not running ... python app.py" overlay with no dismiss button, shown after any single failed health check. | `index.html:24-46`, `main.js:163-171`, `api.js:36`, `style.css:949-958`. | Neutral wording, one retry, and a dismissible banner. | No, strongly recommended | **Text fixed** in `index.html` and `api.js`. The retry and the dismissible banner are not done (optional, 5.12). |
| Medium | **M6.** Seventeen JS and CSS files have fixed names, and CloudFront's default 24 h cache can mix old and new modules after a deploy. | Performance entries; `_nocache_server.py` exists for this reason. Browser testing today also found cached modules running old code. | Upload with `Cache-Control: no-cache` and invalidate `/*` on every deploy. | **Yes** (config) | **Fixed locally:** `nginx.conf` sends `Cache-Control: no-cache`. CloudFront still needs the `no-cache` upload plus the invalidation (`deploy-web.sh`). |
| Medium | **M7.** In `config.js`, any host or port containing "5500" is sent to `http://127.0.0.1:5050`. | `config.js:20`; tested against the real file. The chance for a random CloudFront id is about 1 in 170,000. A custom domain containing 5500 fails every time. | A port-based check (section 5.8). | No | **Fixed.** |
| Medium | **M8.** The working copy has `back-end/navigator.db` on disk. A naive zip of `back-end/` would ship it. | `ls back-end`. | The container path excludes it (verified). Never zip the folder. | No (handled) | Handled. |
| Medium | **M9.** Docs and tasks are stale. CLAUDE.md (ignored by `~/.gitignore_global`) mentions `date.today()`, `css/` files, a separate-origin API and "no inline JS or CSS" (lines 31-32), and tells the agent to run `ruff check . && ruff format .` (lines 56-57 and 108), which would rewrite 6 synced files. `task test` runs lint first and fails. `web:prototype` needs deleted files. `.env.example` is out of date. | Delivery audit; `grep -n` on CLAUDE.md. | Ask before editing. The copy-paste prompt quotes and overrides the conflicting lines. | No | Open; ask before editing. |
| Medium | **M10.** `main` is stale (94c34e6, June) and no branch is protected. | `gh api`. | Decide the release branch in the CI/CD phase. | No | Open. `ci.yml` now expects release tags on `main`. |
| Medium | **M11.** Nothing is committed, so git cannot restore a previous deployed front-end, and an image tag built from the HEAD sha does not identify uncommitted code inside it. | `git status`; the user's rule of no commits unless asked. | Version the web bucket, save each front-end deploy to a gitignored `infra/.deploys/<timestamp>/`, and add `-dirty` to image tags when the tree has changes (sections 5.11 and 6.7). | **Yes** (rollback) | Open: the deploy scripts (cloud session). |
| Low | **L1.** An image function that stays idle for several weeks goes Inactive, and the next request fails. (VPC functions go Inactive after 14 idle days; this design has no VPC.) | Lambda VPC and container-image docs. | A weekly scheduled invoke (section 6.6). | No | Open: Terraform. |
| Low | **L2.** The `execute-api` URL is reachable directly, bypassing CloudFront. | HTTP API default. | Later: an origin-verify header, or a custom domain with the default endpoint disabled. | No | Open. |
| Low | **L3.** tzdata: the container path works (verified with the network off). A zip on the managed runtime would probably not. | Local test; AL2023 minimal package list. | Stay on the container path; `GET /api/priorities` in the smoke test proves it. | No | Handled. |
| Low | **L4.** Phone polish: the toast overflows at 375 px, some tap targets are under 24 px, and `100vh` misbehaves on iOS. | Measured. | UI polish later. | No | Open. |
| Low | **L5.** There is no account deletion or data export for likely under-18 users. | No delete routes. | Phase 3 (section 10). In S3 mode a delete must also remove the user's `photos/` objects. | No | Open. |
| Low | **L6.** Flask-Cors 5.0.1 has advisories fixed in 6.0. | `requirements.txt:7`. | Low impact on a same-origin setup. Upgrade later with tests. | No | Open. |
| Low | **L7.** The root `.env` is 499 bytes, the same as `.env.example`, so Docker is probably using the dev `SECRET_KEY` locally. | File size only; the file was not opened. | Never reuse any local secret in the cloud. | No | Unchanged. |
| Low | **L8.** `index.html` has no `<link rel="icon">`, so browsers request `/favicon.ico`. Locally nginx's `try_files` hides this with a 200; through CloudFront the S3 origin returns 403 by design, which can show as a "Failed to load resource" console line. | `index.html:7` is the only `<link>`; `nginx.conf:10`. | Treat a `/favicon.ico` 403 as expected in checks. Optional, ask first: add a small icon file. | No | Open (optional, 5.12). |

### 1.4 Corrections to this session's own premises

- **The GitHub state moved during the audits.** The brief said the working copy's GitHub was 14 commits behind with most code uncommitted. At 17:51:56 NZST today, 0286f21 "adjusted code" (58 files) was pushed to `develop`. At that point the tree was clean with 15 commits, and only `.env.example` is tracked (no `.db`, no `.env`). A fresh clone has the synced app, Docker and the 34 original tests, but not CLAUDE.md, which a global gitignore excludes. Today's later changes (section 5) and the 26 new tests are **not committed**.
- **The submitted repo cannot be hosted.** Its committed `config.js` has no same-origin branch (that line is only an uncommitted local edit), so it always calls `127.0.0.1:5050`. Deploy only from the working copy.
- **`config.js` already worked on CloudFront.** One research note said it would build a `:5050` URL there. The front-end audit ran the real file: on `*.cloudfront.net` it returns `''` (same origin). The port-based fix for "5500" is now done as well.
- **The stale "mock back-end" wording** is in `Taskfile.yml`, `taskfiles/web.yml` and `docs/`, not in CLAUDE.md. CLAUDE.md's problems are different (M9).
- **The earlier plan treated the API throttle as the ceiling.** It is not; the Lambda account quota is (H10). The earlier "about 10" figure is not in AWS documentation.
- **The first version of this plan said S3 cannot be the database, and chose SQLite on EFS.** Plain S3 still cannot be edited in place by SQLite, but a copy-and-sync design with conditional writes works at classroom scale and removes the VPC, EFS and backups. It is now implemented and tested (section 2). EFS is kept as the fallback.

### 1.5 What this plan supersedes in CICD-HANDOFF.md

| CICD-HANDOFF.md said | Reality |
|---|---|
| Work in `submitted-digit-yr12`; "Do not touch digit-yr12-project" | The reverse: the submitted repo is frozen and the working copy is the only writable repo. |
| Function URL behind CloudFront OAC, "no code change" | With OAC the Bearer token cannot reach Flask without workarounds, and every POST/PUT needs a client-computed body hash (H3). Use an HTTP API. Code changes were required, and they are now done (section 5). |
| EFS with reserved concurrency 1 | Reserved concurrency 1 throttles the dashboard and may not be settable on a new account. This plan uses no reservation, and the database now lives in S3, not EFS (section 2). |
| SSM Parameter Store is "free" | The first version of this plan put the Lambda in a VPC with no NAT, which cannot reach SSM without paid endpoints. The Lambda now has no VPC, but reading SSM would need new code; an encrypted environment variable is simpler. |
| Recover the tests from `34c25d0^` | Those files were empty. The real tests (now 60) are in the working copy. |
| "No CI", "No Dockerfile", keep PythonAnywhere | Stale or unsupported. |
| **Keep:** GitHub OIDC for CI, remote state, a budget alarm first, tagging | Carried forward into sections 6 and 10. The budget is now checked before any billed apply. |

### 1.6 Sources checked for this revision (2026-09-26)

- Lambda quotas ("New AWS accounts have reduced concurrency and memory quotas"; 6 MB synchronous payload; default 1,000 concurrent executions for standard accounts): https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- Lambda container images, function lifecycle (image missing from ECR puts the function in the Failed state): https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
- Lambda VPC Hyperplane ENIs (up to 20 minutes to delete; 14 idle days to Inactive; relevant only to the EFS fallback, since this design has no VPC): https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html
- API Gateway proxy turning a Lambda throttle into 500 (AWS re:Post, community answer, not official docs): https://repost.aws/questions/QUfI6bsdd0SOiPeyimzxSkfQ/api-gateway-proxy-integration-does-not-forward-lambda-throttling-http-429-to-client-needs-product-support
- EFS with AWS Backup (35-day default retention; default vault denies deleting recovery points; default plan and vault cannot be deleted; EFS fallback only): https://docs.aws.amazon.com/efs/latest/ug/awsbackup.html
- EFS metering (every NFS request counts as at least 4 KB; EFS fallback only): https://docs.aws.amazon.com/efs/latest/ug/performance.html
- CloudFront OAC for Lambda function URLs (x-amz-content-sha256 on PUT/POST; no-override signing validated as SigV4): https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html
- AWS Free Tier plans (credits carry over on upgrade; joining AWS Organizations upgrades a Free plan account): https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html
- IAM Identity Center account instances: https://docs.aws.amazon.com/singlesignon/latest/userguide/account-instances-identity-center.html
- AWS Lambda Web Adapter README and releases (v1.1.0, 2026-09-18; healthy status default 100-499; MIN_UNHEALTHY_STATUS removed; pass-through path /events): https://github.com/aws/aws-lambda-web-adapter and https://api.github.com/repos/aws/aws-lambda-web-adapter/releases
- Terraform releases (1.16.4, 2026-09-23; 1.17.0-beta2): https://github.com/hashicorp/terraform/releases
- AWS provider releases (6.66.0, 2026-09-21; `aws_s3files_*` since 6.40.0): https://github.com/hashicorp/terraform-provider-aws/releases
- Random provider releases (3.9.1, 2026-09-11): https://github.com/hashicorp/terraform-provider-random/releases
- Terraform install (HashiCorp tap): https://developer.hashicorp.com/terraform/install ; homebrew-core formula API returned 404: https://formulae.brew.sh/api/formula/terraform.json
- OpenTofu settings (required_version interpretation; versions.tofu precedence): https://opentofu.org/docs/language/settings/
- Lambda file systems (S3 Files and EFS as mount types): https://docs.aws.amazon.com/lambda/latest/dg/configuration-filesystem.html
- Local, read-only: `front-end/js/router.js:53-63`, `front-end/js/api.js:10,27`, `front-end/index.html:7,10`, `front-end/nginx.conf:10`, `back-end/routes/auth.py:15,41-43,72`, `back-end/app.py:1-40,64-66`, `scripts/smoke.sh:20`, `back-end/tests/conftest.py:34`, `CLAUDE.md:31-32,56-57,108,111`, `docker buildx imagetools inspect` on the adapter tag, and `docker push --help` (all before today's changes).
- Local, after implementation: `back-end/s3db.py`, `back-end/app.py`, `back-end/db.py`, `back-end/Dockerfile`, `back-end/tests/test_cloud.py`, `back-end/tests/test_s3db.py`, `back-end/tests/fake_s3.py`, `docker-compose.yml` (profile `s3`), `scripts/smoke-s3.sh`, and the verification runs listed in section 8.1.

---

## 2. How S3 holds the SQL database (SQLite cannot edit S3 in place)

SQLite is a single file that it edits **in place**. For each write it (1) overwrites individual 4 KB pages inside the file, (2) takes byte-range locks so two writers cannot collide, and (3) calls `fsync` so a crash cannot corrupt the file. Plain S3 offers none of these:

- S3 objects are **immutable**. Changing one byte means uploading the whole object again. AWS's own S3 Files docs say "S3 objects are immutable and do not support atomic renames".
- S3 has **no lock primitive**. AWS's FUSE client, Mountpoint for S3, "cannot modify existing files ... and it does not support symbolic links or file locking".
- SQLite's own authors warn that even real network filesystems have corrupted databases through faulty locking.

So SQLite cannot run **on** S3. It can run on a local copy of a file that **lives in** S3, as long as every save is checked against the latest version. That is the design now implemented in `back-end/s3db.py`: **the S3 object is the database**.

**How it works:**

1. The database is one object, `db/navigator.db`, in the private, versioned data bucket `nrn-data-<account>-ap-southeast-2`. Photos are separate objects, `photos/<user_id>/<sha256>`, written with `If-None-Match: *`; the `reviews.attachment` column holds an `s3:` pointer instead of the photo, so the database file stays small.
2. Each Lambda copy keeps its own local copy in `/tmp` (`DATABASE_PATH=/tmp/navigator.db`; the working file name adds the process id). gunicorn runs 1 worker and 1 thread, and the middleware handles one API request at a time per process.
3. Before a request uses the database, the copy asks S3 with `GET If-None-Match: <etag>`. A 304 means unchanged, so nothing is downloaded. Otherwise it downloads the new version.
4. After the request runs, and **before any reply is sent**, it checks whether the request changed the database, using SQLite's file change counter (header bytes 24 to 27) plus the file size. Reads never upload.
5. If the database changed, the copy checks the file (no leftover journal, `PRAGMA quick_check` is ok) and uploads it with `PUT If-Match: <etag>`, or `If-None-Match: *` for a brand-new database. The student sees a success only after S3 has accepted the save.
6. If S3 answers 412 or 409 (another copy saved first), the copy discards its file, downloads the new version and **re-runs the whole request** (the WSGI middleware `ReplayOnConflict` keeps the request body for this). It tries up to `S3DB_MAX_ATTEMPTS=5` times with a short jittered backoff. After that the reply is a JSON 503, "The server is busy. Please try again.", with `Cache-Control: no-store`. Nothing is half-saved.
7. The SDK's automatic retries are **off** for the database PUT, because a retried save could count twice. If a PUT ends without a clear answer, a HEAD request looks for this write's own token in the object metadata; if the token is there, the save landed.
8. If the key is missing but has version history (someone deleted it), the app refuses to create an empty database and answers 503 instead. Only a truly new bucket starts a new database.
9. It is **off** unless `S3DB_BUCKET` is set: local runs, Docker and the tests use a normal database file exactly as before. `boto3` is installed only in the Docker image (the Dockerfile `pip` line), never in `requirements.txt`.

The options:

| Option | How it works | Verdict |
|---|---|---|
| **Copy and sync with conditional writes (chosen, implemented)** | The steps above: a local copy in `/tmp`, a conditional GET before use, a conditional PUT before the reply, and a full re-run on a clash. | Correct with many Lambda copies, because every save must build on the latest version or it is re-run. No VPC and nothing always-on. It uploads the whole file on every write, so it has a ceiling (below). Verified locally (section 8.1). |
| sqlite-s3vfs | Stores database blocks as S3 objects. | Its README says "No locking is performed", which is disqualifying for a multi-writer app. (The original `uktrade/sqlite-s3vfs` repository returns 404 today; the status of any mirror is **unverified** and does not matter to this decision.) **Reject.** |
| Litestream | A WAL-mode replicator daemon. | Needs a long-lived process. Lambda freezes between requests, gives at most 2 s at shutdown, and each environment would be its own replicator. **Reject on Lambda.** |
| Amazon S3 Files | Mounts a bucket or prefix into Lambda as a file system (launched 2026-04-07; Lambda support 2026-04-21). The Lambda file-system docs list it as a mountable type. Terraform has `aws_s3files_*` resources since provider 6.40.0. | **Rejected for now.** It still needs a VPC, mount targets and security groups. AWS publishes no guidance for databases on it. Its "the bucket wins" conflict rule moves the live file to a hidden lost+found. Export to S3 happens only after 60 s without writes. A probe test on real AWS would be needed first. |
| Amazon EFS (fallback) | A mature NFSv4.1 file system with byte-range locks, mounted into Lambda at `/mnt/data`, inside a VPC with private subnets, mount targets and security groups. | The first version of this plan. Correct and mature, but it brings a VPC, mount targets, security groups and backups, and Lambda cannot mount EFS in the NZ Region. **Kept as the fallback** if the S3 design's ceiling is reached; the app already accepts a `DATABASE_PATH` under `/mnt/` with `S3DB_BUCKET` unset. |
| RDS, Aurora, DSQL, DynamoDB | Managed databases. | Correct at any scale, but need a data-layer port (section 10). |

**Honest ceiling.** This design is fine for one or two classes: a database under about 20 MB and about 1 to 2 writes per second sustained. A burst of 30 writes at once sees retries and 1 to 2 s latency, but every save lands or the student gets a clear "busy" message. It is **not suitable for 1,000 students**: the file is bigger, each upload takes longer, and more saves clash. Move to a managed database (RDS/Aurora or DynamoDB) or to EFS when any of the section 10 triggers fires: more than 5% of writes clash, any "busy" 503 in a week, p95 write latency over 1 s, or the database object passes 20 MB. The `[s3db]` log lines make each one measurable.

**What S3 does in this design:**

1. Hosts `index.html`, `style.css` and `js/**` privately in the web bucket; only CloudFront can read them, through OAC. The bucket is versioned as a rollback safety net.
2. Holds the database object `db/navigator.db` in the separate data bucket. Every save leaves the previous file as a version for 14 days, and each version is a complete SQLite file (section 4.10).
3. Holds photo attachments as their own objects under `photos/`, served one at a time through the owner-only attachment route.
4. Holds the Terraform state (versioned, encrypted, private, with a native lock file).

---

## 3. MVP architecture

### 3.1 Diagram

```
                 Students' phones, laptops, school PCs (any modern browser)
                                          |
                                          |  HTTPS, one address: https://dXXXXXXXXXXXXX.cloudfront.net
                                          v
  +--------------------------------------------------------------------------------------+
  |  Amazon CloudFront (global, edges in Auckland and Sydney; PriceClass_All)             |
  |                                                                                      |
  |  Default behaviour "*"                      |  Ordered behaviour "/api/*"            |
  |  CachingOptimized, security headers + CSP   |  CachingDisabled (never cached)        |
  |  GET/HEAD only                              |  AllViewerExceptHostHeader (forwards   |
  |                                             |  Authorization), all 7 HTTP methods    |
  +------------------------|---------------------+-------------------|--------------------+
                           | OAC (SigV4, read-only)                  | HTTPS
                           v                                         v
  +------------------------------------------+   +---------------------------------------+
  | S3 bucket nrn-web-<acct>-ap-southeast-2  |   | API Gateway HTTP API, $default stage   |
  | private, versioned; index.html,          |   | throttle 10 req/s, burst 20 until the  |
  | style.css, js/**                         |   | Lambda quota is >= 100; then 25 / 50   |
  +------------------------------------------+   +-------------------|-------------------+
                                                                     | AWS_PROXY, payload 2.0
   Region ap-southeast-2 (Sydney). No VPC, no EFS.                   v
  +--------------------------------------------------------------------------------------+
  |   +-----------------------------------------------------------+                      |
  |   | Lambda "nrn-api": container image from ECR, no VPC        |                      |
  |   |   Lambda Web Adapter -> gunicorn (1 worker, 1 thread)     |                      |
  |   |   -> Flask app wrapped by the s3db middleware             |                      |
  |   |   x86_64, 1024 MB, 20 s timeout, /tmp 512 MB              |                      |
  |   |   local copy of the database in /tmp                      |                      |
  |   +-----------------------------|-----------------------------+                      |
  |                                 | HTTPS to S3 with the function's IAM role:          |
  |                                 | GET If-None-Match; PUT If-Match or If-None-Match * |
  |   +-----------------------------v-----------------------------+                      |
  |   | S3 bucket nrn-data-<acct>-ap-southeast-2                  |                      |
  |   | private, versioned, SSE-S3, prevent_destroy               |                      |
  |   |   db/navigator.db           the whole SQLite file         |                      |
  |   |   photos/<user_id>/<sha256> one object per photo          |                      |
  |   | old db/ versions kept 14 days, old photos/ 30 days        |                      |
  |   +-----------------------------------------------------------+                      |
  +--------------------------------------------------------------------------------------+
  Also: ECR repo nrn-api (images), CloudWatch Logs /aws/lambda/nrn-api (14 days),
        S3 state bucket nrn-tfstate-<acct>-ap-southeast-2 (Terraform only).
```

### 3.2 Request flow: first page load

1. The browser requests `https://dXXXX.cloudfront.net/` from the nearest edge.
2. The default behaviour serves `/index.html` (`default_root_object`). On a cache miss, CloudFront fetches it from S3 with an OAC-signed request. The bucket policy allows only this distribution.
3. `style.css` and about 16 JS modules load the same way. Each object has the right `Content-Type` and `Cache-Control: no-cache`, so the browser revalidates with an ETag and usually gets a cheap 304. The browser also asks for `/favicon.ico`, which returns 403 (expected, finding L8).
4. `js/config.js`: the port is not 5500 or 5501 and the host does not end in `-5500.app.github.dev`, so `API_BASE = ''`. Every API call then goes to the same CloudFront host.
5. `main.js` fires `GET /api/health` and `GET /api/auth/me` at the same time.

### 3.3 Request flow: an authenticated call (`GET /api/subjects`)

1. The browser sends `GET /api/subjects` with `Authorization: Bearer <JWT>` to the same host.
2. CloudFront matches `/api/*`. CachingDisabled means the response is never stored, so it can never be served to anyone else. AllViewerExceptHostHeader forwards `Authorization`, and CloudFront sets `Host` to the `execute-api` domain.
3. The HTTP API `$default` stage (no path prefix) applies throttling and invokes Lambda with payload format 2.0.
4. **Cold start only:** the image CMD runs `init_db()` (in S3 mode this makes a small, unused `/tmp/navigator.db`, which is harmless) and starts gunicorn. The adapter waits until `/api/health` answers with a 2xx status. That first health check downloads `db/navigator.db` from S3, or, in a brand-new bucket, creates it with `If-None-Match: *`.
5. The adapter turns the event into `GET http://127.0.0.1:5000/api/subjects`. The s3db middleware asks S3 whether the database changed (`GET If-None-Match`, usually a 304 with no download). Flask verifies the HS256 token with `SECRET_KEY`, reads the local SQLite copy, and returns JSON with no photo data and `Cache-Control: no-store`. The request changed nothing, so nothing is uploaded.
6. The response travels back through API Gateway and CloudFront (`x-cache: Miss from cloudfront`) to the browser. The browser aborts any call that takes longer than 25 s (`api.js`).
7. A write, for example `POST /api/log-review`, follows the same path, then uploads the changed file with `PUT If-Match` before the reply leaves Lambda. On a clash it re-runs (section 2).

### 3.4 Components

| Service | Job | Why this | Why not the alternative | Monthly cost, classroom |
|---|---|---|---|---|
| CloudFront | One HTTPS URL, edge caching, security headers, routing `/api/*` | Same origin means no CORS or preflights; NZ and AU edges; 1 TB and 10M requests always free | GitHub Pages: public repo on Free, cross-origin, no headers, shared `github.io` origin (section 11) | USD 0 |
| S3 (web) | Static files | Private through OAC; exact Content-Type and Cache-Control; versioned | S3 website endpoint: public and incompatible with OAC | under USD 0.01 |
| API Gateway HTTP API | Lambda front door and throttling | Bearer header untouched, no code change, built-in rate limit | Function URL plus OAC cannot carry the Bearer token and needs body hashes on POST/PUT; Function URL without OAC has no throttling and needs a secret-header check in code | about USD 0.02 (USD 1.29 per million) |
| Lambda (container image + Web Adapter) | Runs the Flask app and the s3db middleware | Same image as the verified Docker stack; the adapter is AWS-maintained (`github.com/aws/aws-lambda-web-adapter`, v1.1.0 published 2026-09-18); no VPC | Zip plus adapter layer, or zip plus apig-wsgi: needs Linux wheels built on the Mac, gunicorn and tzdata vendored, and new files. A fine runner-up if AWS-managed patching matters more | USD 0 (inside 400,000 GB-s and 1M requests always free) |
| ECR | Stores the images | Required for image functions; basic scan on push | none | about USD 0.02 to 0.15 |
| S3 (data) | The database object and the photos | No VPC and nothing always-on; conditional writes keep many Lambda copies safe; versioning keeps every save for 14 days | EFS: needs a VPC, mount targets and security groups (the fallback); S3 Files: needs a VPC too and has no database guidance; RDS about USD 21 a month plus a code port | a few cents (estimate, section 9) |
| CloudWatch Logs | Function logs, 14 days, including the `[s3db]` lines | 5 GB always free | none | USD 0 |
| S3 (state) | Terraform state and lock | Native lock file (Terraform 1.11 and later) | DynamoDB locking is deprecated | under USD 0.01 |

---

## 4. Detailed design

### 4.1 Region and account

- **ap-southeast-2 (Sydney) is the default.** The NZ Region ap-southeast-6 is GA but opt-in. The first version of this plan was forced to Sydney because the Lambda docs state: "Amazon EFS for Lambda is available in all commercial Regions except Asia Pacific (New Zealand) ...". The S3 design uses no EFS, so that hard blocker is gone. Sydney stays the default for price (about 5% cheaper) and maturity unless the user chooses otherwise (decision 12.3). The latency cost is small (about 8 ms to NZ versus 34 to 46 ms to Sydney, measured today from this Mac), and CloudFront serves the static files from NZ edges anyway. If NZ is chosen, the adult opts in to the Region first, and every service in this plan must be checked as available there (**VERIFY**).
- **Privacy.** Under the Privacy Act 2020 s11, using AWS as an agent that stores data on your behalf is not a cross-border disclosure (IPP 12), so Sydney is legally workable. This is not legal advice. Keep `region` as a Terraform variable.
- **Account owner.** The AWS Customer Agreement requires that "you are not a minor", and NZ law defines a minor as under 18. **The adult (the father) creates and owns the account and enters the payment card. Claude never enters payment details or credentials.**

### 4.2 Networking: none

- There is **no VPC, no subnet, no security group, no internet gateway, no NAT gateway, no VPC endpoint and no mount target**.
- A Lambda outside a VPC reaches S3 and CloudWatch Logs directly, using its IAM role. The app's only outbound calls are to the data bucket, and only when `S3DB_BUCKET` is set.
- Trade-off, stated honestly: outside a VPC the function could reach the internet. The app makes no other outbound calls (verified), and its role can touch only the database object, `photos/*` and its own logs (section 6.6).

### 4.3 The database object and SQLite

- **Data bucket** `nrn-data-<account>-ap-southeast-2` (section 6.4): `prevent_destroy`, versioning on, SSE-S3, Block Public Access (all four), Object Ownership `BucketOwnerEnforced`. Lifecycle: noncurrent `db/` versions expire after 14 days, noncurrent `photos/` versions after 30 days, and incomplete multipart uploads are aborted after 1 day.
- **Bucket policy:** deny any request without TLS (`aws:SecureTransport` false); deny `s3:PutObject` on `db/*` when **both** `s3:if-match` and `s3:if-none-match` are absent, so nobody can overwrite the database blindly, not even an admin by mistake; deny `s3:DeleteObject*` on `db/*`. **VERIFY** that lifecycle expiry of noncurrent `db/` versions still works with that delete deny.
- **SQLite settings:** keep the **default rollback journal** (`journal_mode=DELETE`; a test locks this in) and never enable WAL: the uploaded file must be one self-contained file. The upload refuses a file that has a leftover `-journal` or fails `PRAGMA quick_check`.
- **Concurrency:** one API request at a time per process (a lock in the middleware, plus `--workers 1 --threads 1`). Across Lambda copies, the conditional PUT decides who saved first, and the loser re-runs its whole request on the new version. Section 5.5's `BEGIN IMMEDIATE` still serialises writers inside one copy.
- **Size:** every save uploads the whole file, which is why photos are kept out of it. The default 512 MB of `/tmp` holds the file plus a download in progress (2 copies) with plenty of room below 20 MB.
- **Requests:** one conditional GET per API request (usually a 304 with no body), one PUT per write (more if it clashes), one PUT per new photo, and a `ListObjectVersions` only when the key is missing.

### 4.4 Lambda

| Setting | Value | Reason |
|---|---|---|
| Package | `package_type = "Image"`, `image_uri = <ecr>:<immutable tag>` | Same Dockerfile as local. |
| Base image | `python:3.13-slim` (Debian 13) | The tests pass on it. Zone data is present (`Pacific/Auckland` verified offline). You rebuild it monthly for patches. |
| Adapter | `COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 /lambda-adapter /opt/extensions/lambda-adapter` | **Done and verified**: the line is in `back-end/Dockerfile`, and a build succeeded with `/opt/extensions/lambda-adapter` present. The tag is a multi-platform index; the digest above is the index digest from `docker buildx imagetools inspect`. The extension is inert under docker compose. |
| `boto3` | `"boto3>=1.36,<2"` on the Dockerfile `pip` line (image only) | The verified build has 1.43.103, which supports `PutObject` `IfMatch`/`IfNoneMatch`, `GetObject` `IfNoneMatch` and `retries={"total_max_attempts": 1}`. |
| Architecture | `x86_64` | The Intel Mac builds amd64 natively. |
| Memory | 1024 MB | About 0.9 s per PBKDF2 login (estimate). New accounts may have a reduced memory quota (AWS does not publish the value); check Service Quotas before the Phase 5 apply. If Lambda refuses 1024 MB, the apply fails with an error naming the limit; request an increase rather than lowering memory. |
| Timeout | 20 s | Room for a login plus a few re-runs after a clash, below the 30 s HTTP API cap. The browser now waits up to 25 s (`api.js`), so it sees the Lambda's answer; `smoke-cloud.sh` holds cold starts and signups under 8 s. |
| Ephemeral storage | 512 MB (the default; not set) | Holds 2 copies of the database (the file and a download in progress). |
| VPC, file system | none | The database is in S3 (section 2). |
| Reserved concurrency | none (`-1`) in the MVP | The account quota is the ceiling (H10). Conditional writes make many copies safe, so no reservation is needed for correctness. Reserve 10 once the quota is at least 110. |
| Start command | unchanged Dockerfile CMD: `init_db` then `gunicorn --bind 0.0.0.0:5000 app:app` | Runs on every cold start; idempotent. |
| Logging | Log group `/aws/lambda/nrn-api` created by Terraform first, retention 14 days | Otherwise AWS creates it with "never expire". |

Environment variables:

| Variable | Value | Set in | Why |
|---|---|---|---|
| `AWS_LWA_PORT` | `5000` | Dockerfile `ENV` (done) | gunicorn's port (the adapter defaults to 8080) |
| `AWS_LWA_READINESS_CHECK_PATH` | `/api/health` | Dockerfile `ENV` (done) | The adapter's default is `/`, which returns 404 on Lambda |
| `AWS_LWA_READINESS_CHECK_HEALTHY_STATUS` | `200-299` | Dockerfile `ENV` (done) | The adapter's default is `100-499`, so a 404 or 401 would count as ready. With `200-299`, only a real 200 from `/api/health` (which touches the DB) counts. Adapter 1.x removed `AWS_LWA_READINESS_CHECK_MIN_UNHEALTHY_STATUS`. The readiness wait is bounded only by Lambda's init and function timeouts. |
| `APP_ENV` | `production` | Terraform | Turns on the fail-closed guard |
| `SECRET_KEY` | `random_password` (64 chars) | Terraform, sensitive | Never the dev default |
| `S3DB_BUCKET` | the data bucket's name | Terraform | Turns on S3 mode. On Lambda the app refuses to start without it (or a `/mnt/` path). |
| `S3DB_KEY` | `db/navigator.db` | Terraform | The database object; must match the IAM policy resource |
| `S3DB_PHOTO_PREFIX` | `photos/` | Terraform | Where photos go; must match the IAM policy resource |
| `DATABASE_PATH` | `/tmp/navigator.db` | Terraform | The local copy (the working file name adds the process id) |
| `APP_TIMEZONE` | `Pacific/Auckland` | Terraform | Explicit; Lambda itself runs in UTC |
| `CORS_ORIGIN` | `https://none.invalid` (variable) | Terraform | The app is same-origin, so this allowlist deliberately matches no site. It also avoids a Terraform dependency cycle with the CloudFront domain. |
| `GUNICORN_CMD_ARGS` | `--timeout 0 --workers 1 --threads 1` | Terraform | One request at a time per copy, as the s3db middleware expects. `--timeout 0` is a precaution (**VERIFY** that it is needed): Lambda freezes the process between requests, and gunicorn's worker heartbeat could misread a long freeze as a hung worker. Lambda's own 20 s timeout bounds each request. |

`S3DB_MAX_ATTEMPTS` is not set; the code default is 5. `S3DB_ENDPOINT_URL` is only for the local test S3 and is never set in the cloud.

### 4.5 API Gateway HTTP API

- `protocol_type = "HTTP"` with **no** `cors_configuration`. Setting it would make API Gateway answer preflights and ignore Flask's CORS headers, and same-origin needs no CORS at all.
- Integration `AWS_PROXY`, `payload_format_version = "2.0"` (the provider defaults to 1.0), and `timeout_milliseconds = 30000`.
- Route `$default` and stage `$default` with `auto_deploy = true`. There is no path prefix, so `/api/health` reaches Flask as `/api/health`.
- Throttling: `throttling_rate_limit` and `throttling_burst_limit` are variables with defaults **10 and 20**. Those defaults match a small new-account Lambda quota (about 11 PBKDF2 logins per second at 10 environments). Once `aws lambda get-account-settings` shows a quota of at least 100, raise them to **25 and 50** with a plan, STOP and apply. A class of 30 opening the app together (about 4 requests each, about 120 requests in about 5 s) fits the 25/50 setting only when Lambda has the concurrency to serve it.
- Known behaviour: stage throttling returns **429**. A throttled Lambda reaches the client as a **500** through the proxy integration (reported on AWS re:Post, not stated in the Lambda docs). Nothing is queued. Since `router.js` now clears the token only on 401, these no longer log the student out, but the student still sees an error, so the quota gate stays required.

### 4.6 CloudFront

| Setting | Value |
|---|---|
| Default behaviour | origin S3 (OAC), `redirect-to-https`, GET/HEAD, `compress = true`, cache policy **Managed-CachingOptimized `658327ea-f89d-4fab-a63d-7e88639e58f6`**, custom response headers policy |
| `/api/*` behaviour | origin HTTP API, `https-only`, all 7 methods, cache policy **Managed-CachingDisabled `4135ea2d-6df8-44a3-9df3-4b5a84be39ad`** (or the per-token fallback policy when `auth_in_cache_key = true`), origin request policy **Managed-AllViewerExceptHostHeader `b689b0a8-53d0-40ab-baf2-68738e2966ac`** |
| Must not use | Managed-AllViewer `216adef6-5c7f-47e4-b989-5492eafa07d3` (it forwards `Host`, which breaks API Gateway), any shared caching policy on `/api/*`, and OAC on a Lambda Function URL |
| `default_root_object` | `index.html` |
| `custom_error_response` | **none** (finding H5) |
| `price_class` | `PriceClass_All` (100 and 200 exclude the AU and NZ edges) |
| Certificate | the default `*.cloudfront.net` certificate (a custom domain is phase 3) |
| Security headers | HSTS 1 year, `nosniff`, frame-options `DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, plus the CSP below |

**CSP.** The front-end audit ran the app under `default-src 'none'; script-src 'self' 'sha256-<hash of the one inline script>'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`. `'unsafe-inline'` for styles is needed because the templates set `style="width:..."` on progress bars. Photos still reach the page as data URLs from the API, so `img-src 'self' data:` is enough. Terraform computes the inline-script hash from `front-end/index.html` itself (section 6.7). The only inline script is `index.html:10-19`, the file has LF line endings, and its hash is `sha256-Bs3dMPZpJl4yu6i4aoEHNoqe6dkmNQOo007ow/o95jI=`, computed locally with the same regex (re-checked after today's text edits to `index.html`, which are outside the script: unchanged), so the Terraform approach matches what the browser hashes.

**The CSP only changes on `terraform apply`.** `deploy-web.sh` uploads files without Terraform, so any edit to the inline `<script>` (even whitespace) would make the live CSP block it. `deploy-web.sh` therefore recomputes the hash locally and compares it with the `csp` Terraform output; if they differ it stops with "run terraform plan/apply first" (section 5.11). **VERIFY** in the browser console after deploy: there should be no CSP violations.

**Authorization check and fallback.** CloudFront's custom-origin header rules remove `Authorization` from GET and HEAD requests unless a policy forwards it; AllViewerExceptHostHeader forwards it. The smoke test signs up, then calls `GET /api/auth/me` with the token through CloudFront and expects 200 with the right email. If it gets 401, the header is not reaching Flask. The fallback is already written in `web.tf`: a custom cache policy `nrn-api-per-token` that **puts `Authorization` in the cache key** (TTLs min 0, default 0, max 1), so each token gets its own entry and nothing is shared between users. Switching to it is `-var auth_in_cache_key=true`, then plan, STOP, apply. Keep `Cache-Control: no-store` from Flask and re-run the test.

**Caching of the unhashed ES modules.** Upload every file with `Cache-Control: no-cache`, and run `aws cloudfront create-invalidation --paths "/*"` after each upload. That counts as 1 path, and the first 1,000 paths a month are free. Browsers then revalidate on each load. Browser testing today showed why this matters: without `no-cache`, cached modules ran old code after an update (now fixed locally in `nginx.conf`). The think-big upgrade is to deploy assets under `v/<git-sha>/` with `immutable` caching, and keep only `index.html` as `no-cache`.

### 4.7 S3

- Web bucket `nrn-web-<account>-ap-southeast-2`: Block Public Access (all four settings), SSE-S3, Object Ownership "bucket owner enforced" (the default), **versioning on with noncurrent versions expiring after 30 days**, and a bucket policy that allows `s3:GetObject` only to `cloudfront.amazonaws.com` with `AWS:SourceArn` set to the distribution. Because the policy grants no `ListBucket`, a missing file returns 403. That is intended.
- Upload **only** `index.html`, `style.css` and `js/**`, never `Dockerfile`, `nginx.conf`, `_nocache_server.py` or `.DS_Store`. Use `aws s3 sync --delete` with filters, which sets the Content-Type from the file extension.
- Each deploy also saves exactly what it uploaded as a tarball under the gitignored `infra/.deploys/<timestamp>/`, because nothing is committed and git cannot restore a previous front-end (M11).
- Data bucket `nrn-data-<account>-ap-southeast-2`: the database object and the photos (sections 4.3 and 6.4). Only the Lambda role reads and writes it. Humans never write `db/` by hand, except a rehearsed restore (section 4.10).
- State bucket (bootstrap): versioning on, SSE-S3, Block Public Access, `prevent_destroy`.

### 4.8 Secrets and configuration

- `SECRET_KEY` = Terraform `random_password` (64 characters, no special characters), passed as a Lambda environment variable (encrypted at rest with the AWS-managed key). It also ends up in Terraform state, which is why the state bucket is private, encrypted and versioned.
- The Lambda has no VPC, so it could read SSM Parameter Store or Secrets Manager, but that needs new code. The encrypted environment variable is simpler and enough here.
- To rotate it: `terraform apply -replace=random_password.secret_key`. This logs everyone out. Rotate whenever the database is recreated, because ids restart.
- Never print it. Do not run `terraform state show random_password.secret_key`. Always call `aws lambda get-function-configuration` with a `--query` that leaves out `Environment`.
- Never reuse any local `.env` value in the cloud.

### 4.9 Logging and monitoring

- Terraform creates the log group before the function, with 14-day retention. The `[trace]` prints no longer contain email addresses (tested); the user id, method and path remain.
- The `[s3db]` lines carry only technical details (etag, size in bytes, time in ms, attempt number, status code), never student data:
  - `saved etag=... bytes=... ms=...` for every upload,
  - `conflict attempt=N` when another copy saved first and the request re-runs,
  - `busy attempts=5` when all attempts clashed (the student got a 503),
  - `unavailable`, `save-failed` and `saved-unclear-ok` for S3 errors and unclear uploads.
- What to watch for:
  - `InsecureKeyLengthWarning` (a canary for a short key; the guard should prevent it),
  - any `[s3db] busy` line, and the share of `conflict` lines against `saved` lines (the section 10 triggers),
  - `WORKER TIMEOUT` (gunicorn after a freeze),
  - `Task timed out`,
  - Lambda `Throttles` and API 429/5xx counts in the first class session (H10).
- Budgets (created in the console on day one, and checked by the implementing session before any billed apply) are the MVP cost alarm. CloudWatch alarms on Lambda `Errors` and `Throttles`, API 5xx and the `[s3db] busy` lines come in phase 3 (10 alarms are always free).

### 4.10 Backups

- **Every save is a backup.** The data bucket is versioned, so each save of `db/navigator.db` keeps the previous file as a noncurrent version for 14 days (photos: 30 days). Each version is a complete SQLite file: the app uploads only a file with no leftover journal that passes `PRAGMA quick_check`. This is better than the EFS fallback's file-level backups, which AWS warns can be inconsistent if taken during a write.
- The bucket policy denies deleting `db/` objects and versions and denies any unconditional write to `db/`, so neither a script nor a tired human can overwrite or delete the database by mistake. Lifecycle expiry is what removes old versions (**VERIFY** that it still works with the delete deny).
- Storage: each save keeps a whole old copy for 14 days, so old versions take roughly the file size times the number of saves in 14 days. At classroom scale that is still well under USD 0.10 a month (estimate, section 9). If 14 days is too short (for example over school holidays), lengthen the `db/` rule.
- **Restore outline (a human runs it; rehearse it before the class relies on the app).** Claude never runs these steps and never downloads the database.
  1. List the versions: `aws s3api list-object-versions --bucket <data_bucket> --prefix db/navigator.db --query 'Versions[].{Id:VersionId,Time:LastModified,Size:Size,Latest:IsLatest}'`.
  2. Download the chosen version to a private folder outside every git repo: `aws s3api get-object --bucket <data_bucket> --key db/navigator.db --version-id <id> <private folder>/restore.db`.
  3. Read the current ETag: `aws s3api head-object --bucket <data_bucket> --key db/navigator.db --query ETag --output text`.
  4. Upload it as the new current version with a conditional write (the bucket policy rejects a plain PUT): `aws s3api put-object --bucket <data_bucket> --key db/navigator.db --body <private folder>/restore.db --if-match <etag>`. **VERIFY** the `--if-match` flag and the ETag format with `aws s3api put-object help`. A 412 means someone saved in between: read the ETag again and repeat, or first pause the API with the emergency brake (section 8.2). If the key is missing (the app answers 503 because it has history), use `--if-none-match '*'` instead.
  5. Every Lambda copy picks up the restored file on its next request, because its conditional GET sees a new ETag. Remove the local `restore.db` afterwards; it holds student data.
- A safe rehearsal restores the newest version onto itself (same content), which proves every step without losing any save.

### 4.11 Data initialisation

- Production starts **empty**. No local `navigator.db` is ever uploaded. The image cannot contain one (`.dockerignore` has `*.db`), and `scripts/deploy-api.sh` checks this before pushing.
- The first API request in a brand-new bucket (normally the adapter's first health check) creates `db/navigator.db` with `If-None-Match: *`. Two cold starts racing create exactly one (tested: `test_two_cold_starts_make_one_database`).
- Each copy runs `db.init_db()` (`CREATE TABLE IF NOT EXISTS` plus column migration) on every file it downloads. A migrated file is saved once through the normal conditional PUT (tested), so two copies can no longer collide on one file while adding a column.
- If the key ever disappears while it has version history, the app refuses to start an empty database and answers 503 until a human restores it (section 4.10).
- The smoke test's test accounts (`smoke+<time>@example.test`) remain in production, because there is no delete route. Name them clearly.

### 4.12 Security hardening

MVP:
- HTTPS only, and a private web bucket reachable only through OAC.
- `/api/*` is never cached, and Flask sends `no-store` (done).
- Security headers and CSP, with a deploy-time check that the CSP still matches `index.html`.
- A fail-closed `SECRET_KEY` and database location (done).
- API stage throttling sized to the Lambda quota, and budget alerts.
- A least-privilege role: `AWSLambdaBasicExecutionRole` plus an inline policy for `s3:GetObject` and `s3:PutObject` on `db/navigator.db` and `photos/*`, and `s3:ListBucket` and `s3:ListBucketVersions` on the data bucket. Nothing else.
- A data bucket that is private, versioned, TLS-only, and protected by a bucket policy that denies unconditional writes and deletes on `db/`, with `prevent_destroy`.
- All three S3 buckets, the Terraform state and the environment variables encrypted.
- 14-day logs with no emails (done), and a 3 MiB body limit (done).
- A minimum password of 8 (done).
- Root MFA, no access keys anywhere, and IAM users with MFA.
- Image scanning on push, and an image that contains only code.

Later (section 10):
- A WAF rate-based rule on `/api/auth/*` (HTTP APIs cannot have WAF, so it goes on CloudFront).
- An origin-verify header, or a custom domain with the default `execute-api` endpoint disabled.
- A dummy hash on login misses, 7-day tokens plus a `token_version` column, and `require_auth` returning 401 for deleted users.
- Input validation, Flask-Cors 6, and account deletion and export.

---

## 5. Code and config changes (working copy only): done, and what remains

All of the code changes below are **done** in the working copy and verified on 2026-09-26 (60/60 tests on the host and inside the image; section 8.1). They are **uncommitted**, by the user's rule. Nothing touches `scheduling.py`, the scheduling maths, `schema.sql`, `requirements.txt`, `README.md` or `CLAUDE.md`. The 34 original tests still pass; their only edit is the signup password (`secret` became `secret-pass`, because the minimum is now 8). **The implementing session re-verifies these changes with `git status` and pytest; it does not re-implement them.** Only the scripts in 5.11 and the infrastructure in section 6 remain.

| # | File | Change | Status |
|---|---|---|---|
| 5.1 | `back-end/Dockerfile` | The Lambda Web Adapter COPY (pinned by digest), 3 `ENV` lines, and `boto3` on the `pip` line (image only) | Done; a build proved the digest |
| 5.2 | `back-end/app.py` | Fail-closed secret and database location, 3 MiB limit plus JSON 413, `no-store` on `/api/*`, health touches the DB (JSON 503), `s3db.install(app)` | Done, tested |
| 5.3 | `back-end/routes/subjects.py` | The list returns `id` and `hasAttachment`, never photo data; `BEGIN IMMEDIATE` in `create_subject` | Done, tested |
| 5.4 | `back-end/routes/reviews.py` | Owner-only `GET /api/reviews/<id>/attachment`; log-review returns `hasAttachment`, stores the photo through `s3db.save_photo`, and uses `BEGIN IMMEDIATE` | Done, tested |
| 5.5 | `back-end/routes/assessment.py` | `BEGIN IMMEDIATE` in `end` | Done |
| 5.6 | `back-end/routes/auth.py` | No emails in logs; the password is hashed before the database is opened; `MIN_PASSWORD_LEN = 8` | Done, tested |
| 5.7 | `front-end/js/screens/subject-detail.js` | Fetch the photo only when "View note" opens | Done, browser-tested |
| 5.8 | `front-end/js/config.js` | Port-based check instead of the substring check | Done |
| 5.9 | `back-end/tests/test_cloud.py` (11 tests), `back-end/tests/test_s3db.py` (15), `back-end/tests/fake_s3.py`; `conftest.py` and `test_api.py` use `secret-pass` | New tests | Done: 60 pass |
| 5.10 | `.gitignore` | Terraform entries and `infra/.deploys/` | Done |
| 5.11 | `scripts/deploy-api.sh`, `scripts/deploy-web.sh`, `scripts/smoke-cloud.sh` (new) | Build, push, upload, verify, with the guards below | **Not written yet: the cloud session** |
| 5.12 | `router.js`, `api.js`, `index.html`, `js/screens/auth.js`, `nginx.conf`, `scripts/smoke.sh`, `.github/workflows/ci.yml` | Token cleared only on 401, 25 s timeout, neutral error text, 8-character minimum in the UI, `no-cache` in nginx, CI on release tags | Done; four small optional items remain |
| 5.13 | `back-end/s3db.py` (new), `back-end/db.py`, `docker-compose.yml` (profile `s3`), `scripts/smoke-s3.sh` (new) | The S3 database and its local two-copy test stack | Done, tested |

### 5.1 `back-end/Dockerfile` (done)

```dockerfile
FROM python:3.13-slim

# AWS Lambda Web Adapter: lets this same image run on AWS Lambda.
# It does nothing under docker compose. Tag 1.1.0, pinned by digest.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AWS_LWA_PORT=5000 \
    AWS_LWA_READINESS_CHECK_PATH=/api/health \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200-299
```

and, further down:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt "gunicorn>=23,<24" "boto3>=1.36,<2"
```

The rest of the file is unchanged, including `USER appuser` (harmless on Lambda, because the files are world-readable) and the CMD that runs `init_db` and then gunicorn. `boto3` is installed only here, never in `requirements.txt` (which matches the submitted code). A build proved the digest (`/opt/extensions/lambda-adapter` is present), and `boto3` 1.43.103 in the image supports every call s3db makes.

### 5.2 `back-end/app.py` (done)

`create_app` sets `MAX_CONTENT_LENGTH = 3 * 1024 * 1024`, then, after `config.update`, calls this guard:

```python
def _check_cloud_settings(app: Flask) -> None:
    """In the cloud, refuse to start with settings that are unsafe or lose data."""
    on_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if not on_lambda and os.environ.get("APP_ENV") != "production":
        return
    # The dev key is public, so anyone could make a login token with it
    key = app.config.get("SECRET_KEY") or ""
    if key == "dev-insecure-change-me" or len(key) < 32:
        raise RuntimeError("SECRET_KEY must be a random value of at least 32 characters.")
    # On Lambda, local files are wiped, so the database must live in S3 or on a mount
    s3_bucket = app.config.get("S3DB_BUCKET") or os.environ.get("S3DB_BUCKET")
    if on_lambda and not s3_bucket and not app.config["DATABASE_PATH"].startswith("/mnt/"):
        raise RuntimeError("Set S3DB_BUCKET (or a /mnt/ DATABASE_PATH) so data is not lost.")
```

It also adds a JSON 413 handler ("That upload is too big."), an `after_request` hook that sets `Cache-Control: no-store` on `/api/*`, a health route that runs `SELECT 1 FROM users LIMIT 1` and returns JSON 503 "Database unavailable." on `sqlite3.Error`, and, as the last step of `create_app`, `s3db.install(app)`, which does nothing unless `S3DB_BUCKET` is set.

The tests are unaffected: `conftest.py` passes its own `SECRET_KEY` and never sets `APP_ENV`. Side effect on the bare-metal path: if someone starts Flask without first running `init_db`, health returns a JSON 503 and the page shows the server overlay. `README.md:14` and `scripts/run-api.sh` both run `init_db` first, so the risk is small.

### 5.3 `back-end/routes/subjects.py` (done)

`review_public` returns `id` and `hasAttachment` instead of `attachment`. `list_subjects` names its columns (`attachment IS NOT NULL AS has_attachment`), so the photo text is never read for the list. `create_subject` starts with `BEGIN IMMEDIATE`.

### 5.4 `back-end/routes/reviews.py` (done)

- `GET /api/reviews/<int:review_id>/attachment` joins reviews to topics to subjects on `subjects.user_id = g.user_id`, and returns `{attachment, attachmentName}` or 404. `s3db.load_photo` turns an `s3:` pointer back into the data URL, so the front-end sees the same shape in both modes. A single photo response is at most about 2.8 MB, well under 6 MB.
- `_review_public` returns `hasAttachment` instead of `attachment`.
- `log_review` checks the photo and stores it with `s3db.save_photo` **before** opening the database (in S3 mode it becomes its own object; the same photo always gets the same name, so a re-run is harmless), then runs `BEGIN IMMEDIATE`.

### 5.5 `BEGIN IMMEDIATE` (done; no scheduling change)

The line sits directly after `db = get_db()` in `log_review` (`routes/reviews.py`), `create_subject` (`routes/subjects.py`) and `end` (`routes/assessment.py`). Python's default (legacy) transaction mode accepts an explicit `BEGIN`. The existing `db.commit()` ends the transaction. If the route raises, the connection closes in teardown and the transaction rolls back. The scheduling inputs and outputs are identical; the change only serialises writers inside one copy. Across Lambda copies the S3 conditional write does the same job (section 2). It makes a double tap count **twice** correctly; it does not stop the double tap itself (H11).

### 5.6 `back-end/routes/auth.py` (done)

The two `[trace]` prints no longer include the email (`test_logs_do_not_contain_emails` checks it). Signup hashes the password before it opens the database. `MIN_PASSWORD_LEN = 8`, matched by `front-end/js/screens/auth.js`, the signup placeholder in `index.html`, the tests and `scripts/smoke.sh`.

### 5.7 `front-end/js/screens/subject-detail.js` (done)

`hasNote` uses `review.hasAttachment`. `openReviewNote` calls `GET /api/reviews/<id>/attachment` only when `hasAttachment` is true, and renders that photo. A browser test confirmed that the photo request happens only when "View note" opens, that the photo renders, and that the console has no errors. No other front-end file reads `review.attachment` (`log-review.js` only sends it).

### 5.8 `front-end/js/config.js` (done)

```js
  const fromSeparateServer =
    location.port === '5500' ||
    location.port === '5501' ||
    location.hostname.endsWith('-5500.app.github.dev');
```

The front-end audit verified this: both CloudFront host shapes, `study5500.example.nz`, `github.io` and `127.0.0.1:55000` return `''`. `127.0.0.1:5500`, `localhost:5500` and `:5501` still return `http://127.0.0.1:5050`, and Codespaces still maps `-5500.` to `-5050.`.

### 5.9 Tests (done: 60 pass)

- `back-end/tests/test_cloud.py` (11, normal database file): the list has no photo data; the photo is only for its owner (200, 404 for another user, 401 without a token); a review without a photo has no attachment; production refuses the dev secret key; Lambda refuses a database that would be wiped; local development still works with the dev key; API answers are not cached; health fails without a database; a too-big upload is a JSON 413; the password needs 8 characters; the logs contain no emails.
- `back-end/tests/test_s3db.py` (15, two app copies sharing `tests/fake_s3.py`): plain mode is unchanged; a fresh bucket is created; two cold starts make one database; reads never upload; a copy refreshes after another copy saves; a clash re-runs the request and saves once; too many clashes give busy and save nothing; an unclear save that landed counts as saved; a failed save gives busy and is not repeated; S3 being down gives busy; an old database is upgraded and saved once; a deleted database is never replaced with an empty one; the journal mode stays DELETE; photos are their own S3 objects; the reply waits for the save.

Run them inside the image:

```
docker compose build api && docker compose run --rm --no-deps api python -m pytest -p no:cacheprovider
```

### 5.10 `.gitignore` (done)

It now ignores `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfplan`, `tfplan`, `crash.log`, `*.tfvars`, `infra/backend.hcl` and `infra/.deploys/`. Keep `.terraform.lock.hcl` tracked, so provider versions are pinned.

### 5.11 Scripts (still to write, in the cloud session)

`scripts/deploy-api.sh` builds, checks and pushes the image, and records the tag:

```bash
#!/usr/bin/env bash
# Build the API image for Lambda (x86_64), check it, push it to ECR, record the tag.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(terraform -chdir=infra output -raw ecr_repository_url)
TAG="$(git rev-parse --short HEAD)"
# Nothing is committed by default, so mark images built from a changed tree.
if [ -n "$(git status --porcelain)" ]; then TAG="$TAG-dirty"; fi
TAG="$TAG-$(date +%Y%m%d%H%M%S)"

docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t nrn-api:local back-end
# Refuse to ship any database or .env file.
if docker run --rm --entrypoint sh nrn-api:local -c 'find /app \( -name "*.db" -o -name ".env" \) | grep -q .'; then
  echo "Image contains a .db or .env file. Aborting." >&2; exit 1
fi
docker tag nrn-api:local "$REPO:$TAG"
# The containerd image store can publish an OCI index on a plain push; Lambda needs a
# single-platform manifest, so push only the amd64 manifest.
docker push --platform linux/amd64 "$REPO:$TAG"

# Guard: confirm the pushed tag is a single manifest, not an index.
docker buildx imagetools inspect --raw "$REPO:$TAG" | python3 -c '
import json, sys
m = json.load(sys.stdin).get("mediaType", "")
print("manifest type:", m)
sys.exit("This is an index, which Lambda rejects." if "index" in m or "list" in m else 0)'

printf 'image_tag = "%s"\n' "$TAG" > infra/image.auto.tfvars
echo "Pushed $REPO:$TAG. Apply it soon: unapplied pushes count toward the ECR keep-15 rule."
```

`scripts/deploy-web.sh [SRC_DIR]` checks the CSP, uploads the static files, saves a rollback copy and clears the CDN cache. `SRC_DIR` defaults to `front-end` (a rollback passes an extracted older copy):

```bash
#!/usr/bin/env bash
# Upload the static front-end to S3, keep a local copy for rollback, clear the CloudFront cache.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:-front-end}"
BUCKET=$(terraform -chdir=infra output -raw web_bucket)
DIST=$(terraform -chdir=infra output -raw distribution_id)
LIVE_CSP=$(terraform -chdir=infra output -raw csp)

# The CSP header only changes on terraform apply. Stop if index.html's inline script changed.
HASH=$(python3 - "$SRC/index.html" <<'PY'
import base64, hashlib, re, sys
html = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"(?s)<script>(.*?)</script>", html)
print(base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode())
PY
)
case "$LIVE_CSP" in
  *"'sha256-$HASH'"*) echo "CSP hash matches: sha256-$HASH" ;;
  *) echo "index.html inline script changed: run terraform plan, STOP, apply first." >&2; exit 1 ;;
esac

# Keep an exact copy of what is being published (nothing is committed, so git cannot restore it).
STAMP=$(date +%Y%m%d%H%M%S)
mkdir -p "infra/.deploys/$STAMP"
tar -czf "infra/.deploys/$STAMP/front-end.tgz" -C "$SRC" index.html style.css js

aws s3 sync "$SRC/" "s3://$BUCKET/" --delete \
  --exclude "*" --include "index.html" --include "style.css" --include "js/*" \
  --exclude "*.DS_Store" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" --query 'Invalidation.Id' --output text
echo "Uploaded $SRC to s3://$BUCKET, saved infra/.deploys/$STAMP, invalidated $DIST"
```

`scripts/smoke-cloud.sh SITE_URL [API_URL] [--burst]` is written in the style of the existing `scripts/smoke.sh` and `scripts/smoke-s3.sh`. It prints `ok` or `FAIL` per check and exits non-zero on the first failure. It uses the password `smoke-pass-2026` (15 characters) for every signup. It records `curl -w '%{time_total}'` for the first call after a deploy (a cold start) and for signup, and fails above 8 s. It includes the parallel log-review check (A16). `--burst` runs the go-live gate check A15. The checks are listed in section 8.1.

### 5.12 Other small changes (done), and what is still optional

Done in the working copy:
- `front-end/js/router.js`: the token is cleared only when `e.status === 401`; for 0, 429, 5xx and a "busy" 503 it is kept, and the auth screen is shown without signing out (H10).
- `front-end/js/api.js`: `REQUEST_TIMEOUT_MS = 25000` (H11), and the network error now says "Can't reach the server. Check your connection and try again."
- `front-end/index.html`: neutral text in the `#serve-hint` and `#server-hint` cards, and the signup placeholder "At least 8 characters". These edits are outside the inline `<script>`, so the CSP hash is unchanged.
- `front-end/js/screens/auth.js` and `scripts/smoke.sh`: the 8-character minimum (`smoke.sh` signs up with `secret-pass`).
- `front-end/nginx.conf`: `add_header Cache-Control "no-cache" always;`, so browsers never keep running old JavaScript after an update (M6, found in browser testing).
- `.github/workflows/ci.yml`: no ruff steps; runs only on `v*` tags that are on `main`, plus `workflow_dispatch`; locally through `act workflow_dispatch -W .github/workflows/ci.yml` (H7).

Still optional, ask first (item by item, not done):
- Make `#server-hint` a dismissible banner that appears only after one retry (`main.js` `checkServer`). Today one failed health check shows it, including a 503 when S3 cannot be reached. An edit inside the inline `<script>` changes the CSP hash, so it needs plan, STOP, apply before `deploy-web.sh`.
- In `nginx.conf`, change `try_files $uri $uri/ /index.html;` to `=404` for Docker parity with CloudFront.
- A small favicon file (an icon, never an emoji) linked from `index.html` and added to the `deploy-web.sh` include filter, so browsers stop requesting a missing `/favicon.ico` (L8).
- Toast `max-width: calc(100vw - 32px); white-space: normal;`.

### 5.13 The S3 database: `back-end/s3db.py` and its local test stack (done)

- `back-end/s3db.py` (new): the design in section 2. `install(app)` wraps the Flask app in `ReplayOnConflict` and returns at once if `S3DB_BUCKET` is not set.
- `back-end/db.py`: `get_db()` opens the latest local copy (`DB_SYNC.pull()`) when S3 mode is on, and the normal file otherwise.
- Settings: `S3DB_BUCKET` (turns it on), `S3DB_KEY` (default `db/navigator.db`), `S3DB_PHOTO_PREFIX` (default `photos/`), `S3DB_MAX_ATTEMPTS` (default 5), and `S3DB_ENDPOINT_URL` (only for the local test S3; never set in the cloud).
- `docker-compose.yml`, profile `s3` (off unless asked for): `s3` is `motoserver/moto:5.1.21`, `s3-init` makes a versioned bucket `nrn-data-local`, and `api-s3a` (port 5061) and `api-s3b` (port 5062) are two API copies sharing one database object, like two Lambda copies.
- `scripts/smoke-s3.sh` (new): health on both copies, sign up on A and see the student from B, 20 parallel reviews across both copies (all 201, `reviewCount` 20, 20 rows), and 10 identical parallel subject creates (one 201, nine 400).

```
docker compose --profile s3 up --build -d
scripts/smoke-s3.sh
docker compose --profile s3 logs api-s3a api-s3b | grep '\[s3db\]'
```

---

## 6. Terraform

Written from the provider docs. It has **not** been run through `terraform validate` (Terraform is not installed on this Mac), so the implementing session must run `terraform fmt -check` and `terraform validate` before any plan. Current versions on 2026-09-26: Terraform 1.16.4 (1.17 is in beta), `hashicorp/aws` 6.66.0 (2026-09-21), `hashicorp/random` 3.9.1 (2026-09-11).

### 6.1 Layout

```
infra/
  bootstrap/
    main.tf            # state bucket (local state, run once)
  versions.tf          # terraform, providers, backend "s3" (partial)
  backend.hcl          # bucket = "<state bucket>"  (gitignored, from bootstrap output)
  variables.tf
  data.tf              # data bucket: the database object and photos (versioned, locked down)
  ecr.tf               # repository + lifecycle policy
  lambda.tf            # secret, role + S3 policy, log group, function, weekly ping
  api.tf               # HTTP API, integration, route, stage, permission
  web.tf               # web bucket (versioned), OAC, headers policy, fallback cache policy, distribution, bucket policy
  outputs.tf
  image.auto.tfvars    # image_tag = "..." (gitignored, written by deploy-api.sh)
  .deploys/            # gitignored copies of each front-end deploy
```

There is no `network.tf` and no `efs.tf`: the design has no VPC and no EFS.

### 6.2 `infra/bootstrap/main.tf`

```hcl
terraform {
  required_version = ">= 1.15"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}

provider "aws" {
  region = "ap-southeast-2"
  default_tags {
    tags = {
      Project   = "nrn"
      Stack     = "bootstrap"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "me" {}

resource "aws_s3_bucket" "tfstate" {
  bucket = "nrn-tfstate-${data.aws_caller_identity.me.account_id}-ap-southeast-2"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}
```

Its local `terraform.tfstate` stays on the Mac and is gitignored. Losing it is not fatal: the bucket is protected, and `terraform import` can recover it.

### 6.3 `infra/versions.tf` and `infra/variables.tf`

```hcl
terraform {
  required_version = ">= 1.15" # 1.11+ for use_lockfile; 1.15+ for 'aws login' credentials in the backend
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
  backend "s3" {
    key          = "nrn/prod/terraform.tfstate"
    region       = "ap-southeast-2"
    use_lockfile = true
    encrypt      = true
    # bucket comes from: terraform init -backend-config=backend.hcl
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "nrn"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "me" {}
```

```hcl
variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "env" {
  type    = string
  default = "prod"
}

variable "image_tag" {
  type        = string
  description = "ECR tag to run; written to image.auto.tfvars by scripts/deploy-api.sh"
}

variable "cors_origin" {
  type        = string
  default     = "https://none.invalid"
  description = "Same-origin app: this allowlist deliberately matches no real site"
}

variable "api_rate_limit" {
  type        = number
  default     = 10
  description = "Requests per second. Raise to 25 once the Lambda concurrency quota is at least 100."
}

variable "api_burst_limit" {
  type        = number
  default     = 20
  description = "Burst. Raise to 50 once the Lambda concurrency quota is at least 100."
}

variable "reserved_concurrency" {
  type        = number
  default     = -1
  description = "-1 means no reservation. Set to 10 once the account quota is at least 110."
}

variable "auth_in_cache_key" {
  type        = bool
  default     = false
  description = "Fallback only: true switches /api/* to a per-token cache policy if Authorization does not reach Flask."
}
```

### 6.4 `infra/data.tf` (replaces `network.tf` and `efs.tf`)

```hcl
locals {
  db_key       = "db/navigator.db" # S3DB_KEY; the IAM policy in lambda.tf uses the same value
  photo_prefix = "photos/"         # S3DB_PHOTO_PREFIX
}

# The database lives here as one object (db/navigator.db), plus one object per photo.
resource "aws_s3_bucket" "data" {
  bucket = "nrn-data-${data.aws_caller_identity.me.account_id}-${var.region}"
  lifecycle {
    prevent_destroy = true # holds student data; remove deliberately before any teardown
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Every save leaves the previous file as a noncurrent version: keep those 14 days (db/)
# or 30 days (photos/), and clean up any upload that never finished.
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "db-old-versions"
    status = "Enabled"
    filter {
      prefix = "db/"
    }
    noncurrent_version_expiration {
      noncurrent_days = 14
    }
  }
  rule {
    id     = "photos-old-versions"
    status = "Enabled"
    filter {
      prefix = local.photo_prefix
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
  depends_on = [aws_s3_bucket_versioning.data]
}

data "aws_iam_policy_document" "data" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # The database may only be written with If-Match or If-None-Match, so nobody can
  # overwrite it blindly. Both conditions must hold (both headers absent) to deny.
  statement {
    sid       = "DenyUnconditionalDbWrites"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/db/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Null"
      variable = "s3:if-match"
      values   = ["true"]
    }
    condition {
      test     = "Null"
      variable = "s3:if-none-match"
      values   = ["true"]
    }
  }

  # Nobody deletes the database or its versions. Old versions leave through lifecycle
  # expiry only (VERIFY that expiry still works with this deny).
  statement {
    sid       = "DenyDbDeletes"
    effect    = "Deny"
    actions   = ["s3:DeleteObject*"]
    resources = ["${aws_s3_bucket.data.arn}/db/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket     = aws_s3_bucket.data.id
  policy     = data.aws_iam_policy_document.data.json
  depends_on = [aws_s3_bucket_public_access_block.data]
}
```

Notes:
- The app's own writes always carry `If-Match` or `If-None-Match` (section 2), so the bucket policy never blocks them; the `photos/` prefix is not covered by the write rule, but s3db writes photos with `If-None-Match: *` anyway.
- There is no `force_destroy`, and the bucket has `prevent_destroy`: a `terraform destroy` cannot remove it by accident (section 8.3 is the human-only teardown).
- Once the bucket policy exists, it is never edited or removed by a Claude session. A plan that destroys or replaces `aws_s3_bucket.data` is an automatic STOP.

### 6.5 `infra/ecr.tf` (`efs.tf` is gone)

```hcl
resource "aws_ecr_repository" "api" {
  name                 = "nrn-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

# If the image a function points to disappears from ECR, the function enters the Failed
# state and every invocation fails. So: expire untagged leftovers quickly, keep a wide
# window of tagged images, and apply soon after each push.
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 1 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the newest 15 images (rollback window; the live one must be among them)"
        selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 15 }
        action       = { type = "expire" }
      },
    ]
  })
}
```

Before every apply that changes `image_tag`, and before any rollback, confirm the tag still exists:
`aws ecr describe-images --repository-name nrn-api --image-ids imageTag="$(sed -n 's/.*"\(.*\)".*/\1/p' infra/image.auto.tfvars)" --query 'imageDetails[0].imageTags'`.

### 6.6 `infra/lambda.tf`

```hcl
resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "aws_iam_role" "api" {
  name = "nrn-api-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Logs only. There is no VPC and no EFS, so no VPC or EFS policies.
resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "api_data" {
  # Read and write the database object and the photos. HEAD uses s3:GetObject too.
  statement {
    sid     = "DatabaseAndPhotos"
    actions = ["s3:GetObject", "s3:PutObject"]
    resources = [
      "${aws_s3_bucket.data.arn}/${local.db_key}",
      "${aws_s3_bucket.data.arn}/${local.photo_prefix}*",
    ]
  }
  # ListBucket makes a missing key return 404 instead of 403. ListBucketVersions lets
  # the app see version history, so it never starts an empty database over a deleted one.
  statement {
    sid       = "ListForMissingKeys"
    actions   = ["s3:ListBucket", "s3:ListBucketVersions"]
    resources = [aws_s3_bucket.data.arn]
  }
}

resource "aws_iam_role_policy" "api_data" {
  name   = "nrn-api-data"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_data.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/nrn-api"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name                  = "nrn-api"
  role                           = aws_iam_role.api.arn
  package_type                   = "Image"
  image_uri                      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  architectures                  = ["x86_64"]
  memory_size                    = 1024
  timeout                        = 20
  reserved_concurrent_executions = var.reserved_concurrency
  # ephemeral_storage stays at the default 512 MB: room for 2 copies of the database.
  # No vpc_config and no file_system_config: the database is an S3 object.

  environment {
    variables = {
      APP_ENV           = "production"
      SECRET_KEY        = random_password.secret_key.result
      S3DB_BUCKET       = aws_s3_bucket.data.bucket
      S3DB_KEY          = local.db_key
      S3DB_PHOTO_PREFIX = local.photo_prefix
      DATABASE_PATH     = "/tmp/navigator.db"
      APP_TIMEZONE      = "Pacific/Auckland"
      CORS_ORIGIN       = var.cors_origin
      GUNICORN_CMD_ARGS = "--timeout 0 --workers 1 --threads 1"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api,
    aws_iam_role_policy_attachment.logs,
    aws_iam_role_policy.api_data,
  ]
}

# Weekly invoke so the function never sits idle long enough to go Inactive.
# The adapter forwards non-HTTP events to /events (AWS_LWA_PASS_THROUGH_PATH default);
# that path is not under /api/, so the s3db middleware does not touch S3 for it.
# Flask answers 405, and that is fine (VERIFY in logs).
resource "aws_cloudwatch_event_rule" "keep_active" {
  name                = "nrn-api-weekly-ping"
  schedule_expression = "rate(7 days)"
}

resource "aws_cloudwatch_event_target" "keep_active" {
  rule = aws_cloudwatch_event_rule.keep_active.name
  arn  = aws_lambda_function.api.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowWeeklyPing"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.keep_active.arn
}
```

Compared with the first (EFS) version of this file: the `vpc_config`, the `file_system_config`, the mount-target `depends_on`, and the `AWSLambdaVPCAccessExecutionRole` and `AmazonElasticFileSystemClientReadWriteAccess` attachments are gone; `AWSLambdaBasicExecutionRole`, the inline S3 policy and the `S3DB_*` variables are new.

### 6.7 `infra/api.tf` and `infra/web.tf`

```hcl
resource "aws_apigatewayv2_api" "api" {
  name          = "nrn-http"
  protocol_type = "HTTP"
  # No cors_configuration: the app is same-origin through CloudFront.
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = var.api_rate_limit
    throttling_burst_limit = var.api_burst_limit
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
```

```hcl
resource "aws_s3_bucket" "web" {
  bucket        = "nrn-web-${data.aws_caller_identity.me.account_id}-${var.region}"
  force_destroy = true # copies of the front-end; each deploy is also saved in infra/.deploys/
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning is the safety net for front-end rollback; old versions expire after 30 days.
resource "aws_s3_bucket_versioning" "web" {
  bucket = aws_s3_bucket.web.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
  depends_on = [aws_s3_bucket_versioning.web]
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "nrn-web-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

locals {
  # Hash of the single inline <script> in index.html, so the CSP allows exactly that script.
  # deploy-web.sh recomputes this and refuses to upload if it no longer matches.
  serve_guard_hash = base64sha256(
    regex("(?s)<script>(.*?)</script>", file("${path.module}/../front-end/index.html"))[0]
  )
  csp = join("; ", [
    "default-src 'none'",
    "script-src 'self' 'sha256-${local.serve_guard_hash}'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ])
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "nrn-security-headers"
  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    content_security_policy {
      content_security_policy = local.csp
      override                = true
    }
  }
}

# Fallback only (var.auth_in_cache_key = true): if Authorization does not reach Flask on GET,
# put it in the cache key so every token has its own entry and nothing is shared between users.
resource "aws_cloudfront_cache_policy" "api_per_token" {
  name        = "nrn-api-per-token"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 1
  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "whitelist"
      headers {
        items = ["Authorization"]
      }
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  default_root_object = "index.html"
  price_class         = "PriceClass_All"
  comment             = "NCEA Review Navigator"

  origin {
    origin_id                = "web"
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  origin {
    origin_id   = "api"
    domain_name = replace(aws_apigatewayv2_api.api.api_endpoint, "https://", "")
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "api"
    viewer_protocol_policy = "https-only"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id = (var.auth_in_cache_key
      ? aws_cloudfront_cache_policy.api_per_token.id
      : "4135ea2d-6df8-44a3-9df3-4b5a84be39ad") # Managed-CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # Managed-AllViewerExceptHostHeader
  }

  # Deliberately NO custom_error_response: the app uses hash routing, and an error
  # rewrite to index.html would turn failed API saves into fake successes.

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "web" {
  statement {
    sid       = "AllowCloudFrontReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket     = aws_s3_bucket.web.id
  policy     = data.aws_iam_policy_document.web.json
  depends_on = [aws_s3_bucket_public_access_block.web]
}
```

### 6.8 `infra/outputs.tf`

```hcl
output "site_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "web_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket # holds db/navigator.db and photos/; never write db/ by hand
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.api.api_endpoint # debugging only; students use site_url
}

output "function_name" {
  value = aws_lambda_function.api.function_name
}

output "csp" {
  value = local.csp # read by deploy-web.sh to detect a stale inline-script hash
}
```

v6 notes: use the standalone `aws_s3_bucket_*` resources (never inline bucket arguments) and cache policy IDs (never the deprecated `forwarded_values`). The resource-level `region` argument exists but is not needed here.

---

## 7. Step by step from a brand-new AWS account on the Intel Mac

Who does what: **[Adult]** is the account holder (the father). **[Student]** is the student at the Mac. **[Claude]** is the new Claude Code session, and every [Claude] step that creates, changes, bills or publishes anything waits for a "yes" in chat.

### 7.1 Before AWS (today)

1. **[Adult or Student]** Make GitHub `ngocnxx/submitted-digit-yr12` private: open the repo on GitHub, then Settings, General, Danger Zone, Change visibility, Private. If the teacher still needs access, add them as a collaborator. Decide with the school before any history purge. No Claude session touches that repo.

### 7.2 Create and secure the account (Adult; about 30 minutes, then up to 24 h for activation)

2. **[Adult]** Go to aws.amazon.com and choose "Create an AWS Account".
   - Root email: an address the adult controls (a dedicated alias is ideal).
   - Account name: `nrn-prod`, account type Personal.
   - The adult's address, phone and payment card.
   - Plan: **Paid plan** (recommended; the account never auto-closes, and both plans receive the USD 100 sign-up credit plus up to USD 100 more for activities) or Free plan (closes after 6 months or when the credits run out; remaining credits carry over if you later upgrade).
   - Support: Basic (free).
3. **[Adult]** Sign in as root. Open the account menu (top right), then Security credentials, then Assign MFA: a passkey or security key is preferred; add a second device if possible. **Never create root access keys.**
4. **[Adult]** In Billing and Cost Management, open Budgets, then Create budget:
   - the "Zero spend budget" template,
   - a "Monthly cost budget" of USD 10 with emails to the adult and the student.
   Then Billing preferences: turn on Free Tier usage alerts. Setting a budget also counts as one of the credit activities. The implementing session checks that a budget exists before any billed apply.
5. **[Adult]** Switch the console Region to **Asia Pacific (Sydney) ap-southeast-2**. No opt-in is needed. Do not enable ap-southeast-6 for this project unless decision 12.3 chose the NZ Region.
6. **[Adult]** In IAM, open Users and create two users, `parent-admin` and `nrn-student`:
   - Tick "Provide user access to the AWS Management Console" and "I want to create an IAM user".
   - Set a custom password that must be changed at first sign-in.
   - Attach policies directly: `AdministratorAccess` and `SignInLocalDevelopmentAccess` (see decision 12.6).
   - Create **no access keys**.
   - Each person signs in at `https://<account-id>.signin.aws.amazon.com/console` and assigns MFA to their own user.
   - From now on the adult uses `parent-admin`, not root.
   - Plain IAM users are simplest here. An organization instance of IAM Identity Center requires AWS Organizations, and joining Organizations upgrades a Free plan account to the Paid plan (remaining credits carry over). An account instance of Identity Center does not need Organizations, but it cannot grant console or CLI access to AWS accounts, so it does not help.
7. **[Adult] REQUIRED before the URL is shared.** Open CloudShell in Sydney from the console.
   - Record the current Lambda quota:
     `aws lambda get-account-settings --query 'AccountLimit.{Total:ConcurrentExecutions,Unreserved:UnreservedConcurrentExecutions}'`
   - Request the increase (free; approval can take from minutes to days):
     `aws service-quotas request-service-quota-increase --service-code lambda --quota-code L-B99A9384 --desired-value 1000`
   - In the Service Quotas console, open AWS Lambda and read the other quotas, including any memory-related quota, before the Phase 5 apply uses 1024 MB. New accounts have reduced memory quotas too; AWS does not publish the exact figures.
   - Gate: do not share the URL until `get-account-settings` shows `Total` of at least 100 (comfortably above a class burst). Until then the API throttle stays at 10/20. Check progress with
     `aws service-quotas list-requested-service-quota-change-history --service-code lambda --query 'RequestedQuotas[].{Quota:QuotaCode,Status:Status,Value:DesiredValue}'`.

### 7.3 Prepare the Mac (Student; Claude asks before installing anything)

8. **[Student]** Check the tools:
   - `aws --version` (2.32.0 or later needed; 2.36.49 is installed),
   - `docker version` (Docker running),
   - `git -C /Users/ngocnx1501/digit-yr12-project status` (on `develop`; it lists today's uncommitted changes from section 5, which is expected).
9. **[Claude asks, Student approves]** Install Terraform:
   `brew tap hashicorp/tap && brew install hashicorp/tap/terraform && terraform version` (expect 1.16.x; 1.16.4 is current).
   homebrew-core no longer has a `terraform` formula (its formula API returns 404), so a plain `brew install terraform` does not work; always use the HashiCorp tap. OpenTofu is out of scope: this configuration pins `required_version = ">= 1.15"`, which OpenTofu may evaluate against its own version number, and it has not been tested with `tofu`.
10. **[Student]** Sign the CLI in without any stored keys:
    `aws login --profile nrn` (a browser opens; sign in as `nrn-student` with MFA; choose `ap-southeast-2` if asked; **VERIFY** the flags with `aws login help`).
    `aws sts get-caller-identity --profile nrn` must show `.../nrn-student`.
    Sessions last up to 12 h. Every shell Claude uses needs `export AWS_PROFILE=nrn AWS_REGION=ap-southeast-2`.
    Fallback if Terraform cannot use these credentials: add this profile to `~/.aws/config` and use `AWS_PROFILE=nrn-tf`:
    ```
    [profile nrn-tf]
    credential_process = aws configure export-credentials --profile nrn --format process
    region = ap-southeast-2
    ```

### 7.4 Code readiness (Claude, in a new session started with the section 13 prompt)

11. **[Claude]** Phase 0: read-only orientation and a report back.
12. **[Claude]** Phase 1: **verify** the implemented changes from section 5. Nothing is re-implemented, nothing is committed, and no branch is created unless the student asks.
13. **[Claude]** Verify locally:
    ```
    cd /Users/ngocnx1501/digit-yr12-project
    git status --short && git diff --stat                                            # the files in section 5
    (cd back-end && .venv/bin/python -m pytest -p no:cacheprovider -q)                # 60 pass on the host
    docker compose build api
    docker compose run --rm --no-deps api python -m pytest -p no:cacheprovider      # 60 pass in the image
    docker compose up -d --build
    API_BASE=http://127.0.0.1:5050 scripts/smoke.sh                                  # 9/9
    docker compose --profile s3 up --build -d
    scripts/smoke-s3.sh                                                              # every check passes
    docker compose --profile s3 logs api-s3a api-s3b | grep '\[s3db\]'               # saved lines, no busy
    ```
    Then a browser check at http://127.0.0.1:5500: sign up (a password of at least 8 characters), log a review with a photo, "View note" shows the photo, and the console has no errors.

### 7.5 Terraform bootstrap

14. **[Claude]** Confirm a budget exists (read-only):
    `aws budgets describe-budgets --account-id "$(aws sts get-caller-identity --query Account --output text)" --query 'Budgets[].BudgetName'`
    Stop if the list is empty. Then write `infra/bootstrap/main.tf`, and run:
    `terraform -chdir=infra/bootstrap init && terraform -chdir=infra/bootstrap plan -out=tfplan`
    **STOP**: show the plan (4 S3 resources).
15. **[Student approves] [Claude]** `terraform -chdir=infra/bootstrap apply tfplan`, then write `infra/backend.hcl` containing `bucket = "<state_bucket output>"`.

### 7.6 Registry and first image

16. **[Claude]** Write `infra/*.tf`, then:
    `terraform -chdir=infra init -backend-config=backend.hcl && terraform -chdir=infra fmt -check && terraform -chdir=infra validate`
17. **[Claude, STOP]**
    `terraform -chdir=infra plan -target=aws_ecr_repository.api -target=aws_ecr_lifecycle_policy.api -var image_tag=none -out=tfplan`
    After approval: `terraform -chdir=infra apply tfplan`
18. **[Student]** Log Docker in to ECR (the token is piped, never shown; it is valid for 12 h):
    ```
    aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-southeast-2.amazonaws.com"
    ```
19. **[Claude]** `scripts/deploy-api.sh`. It builds, checks that there is no `.db` or `.env`, pushes only the amd64 manifest, checks the manifest type, and writes `infra/image.auto.tfvars`.

### 7.7 Full stack

20. **[Claude, STOP]** Re-check the budget and report the quota request status. Then `terraform -chdir=infra plan -out=tfplan`. Summarise the resources. Confirm there is no VPC, subnet, security group, NAT gateway, endpoint, EFS or AWS Backup resource; confirm `aws_s3_bucket.data` is created (never replaced) with `prevent_destroy`, versioning, encryption, the public access block, the lifecycle rules and the bucket policy; and list what bills (the three S3 buckets and their requests, API Gateway, Lambda, CloudFront, ECR, logs). After approval: `terraform -chdir=infra apply tfplan`. Expect several minutes, mostly for CloudFront to deploy globally.
21. **[Claude, STOP]** The first `scripts/deploy-web.sh` makes the site reachable on the public internet. Confirm decision 12.5 (who may sign up) first. After approval, run it.
22. **[Claude]** `scripts/smoke-cloud.sh "$(terraform -chdir=infra output -raw site_url)"`. Every check passes, including the 8 s cold-start and signup timings and the parallel log-review check. The first API call creates `db/navigator.db`; confirm it exists without downloading it: `aws s3api head-object --bucket "$(terraform -chdir=infra output -raw data_bucket)" --key db/navigator.db --query '{ETag:ETag,Size:ContentLength}'`.
23. **[Adult or Student] The bucket-policy check** (a human runs it; Claude never writes to `db/`):
    ```
    aws s3api put-object --bucket "$(terraform -chdir=infra output -raw data_bucket)" --key db/deny-probe
    ```
    It must fail with `AccessDenied` (403), because the PUT has neither `If-Match` nor `If-None-Match`. It uses a probe key, never `db/navigator.db`. If it succeeds, STOP: the bucket policy is not working. Report it, leave the probe object alone, and do not share the URL.
24. **[Student]** Manual checks from section 8.1 on a phone using mobile data.
25. **[Adult and Student] Go-live gate.** When `get-account-settings` shows a quota of at least 100: raise the throttle (`-var api_rate_limit=25 -var api_burst_limit=50`, or set them in a gitignored `.tfvars`), plan, STOP, apply, then run `scripts/smoke-cloud.sh "$SITE" --burst`. Check CloudWatch for `[s3db] saved` lines and no `[s3db] busy` lines. Only then share the URL, with the audience from decision 12.5.

### 7.8 Every later deploy

- **API change:** tests in Docker, `scripts/deploy-api.sh`, confirm the tag exists in ECR (section 6.5), then plan, STOP and apply, then `scripts/smoke-cloud.sh`. Apply soon after each push: unapplied pushes count toward the keep-15 rule.
- **Front-end change:** if `index.html`'s inline `<script>` changed (even whitespace), first plan, STOP, apply so the CSP hash updates. Then `scripts/deploy-web.sh` (it refuses to upload on a mismatch), then `scripts/smoke-cloud.sh`.
- **Weekly in term time:** run the section 10 Logs Insights query and act on any scale trigger.
- **Monthly:** rebuild the image for base-image patches (`deploy-api.sh`, then apply).
- **Once the quota is at least 110:** `terraform apply -var reserved_concurrency=10` (plan, STOP, apply).

---

## 8. Verify, roll back, tear down

### 8.1 Verification

**Already verified locally on 2026-09-26 (before any AWS work):**
- 60 back-end tests pass on the host and inside the Docker image: 34 original, 11 in `tests/test_cloud.py`, and 15 in `tests/test_s3db.py`, which uses an in-memory fake S3 (`tests/fake_s3.py`).
- 7 deliberate code mutations were each caught by the tests: blind overwrite, always upload, reply before save, fingerprint after migration, photo back in the list, no key guard, and delete guard off.
- moto 5.1.21 and 5.1.14 were checked to match real S3 on all six conditional-write rules.
- The compose profile `s3` (moto plus two API copies on ports 5061 and 5062 sharing one database object) passed `scripts/smoke-s3.sh`: 20 parallel reviews across both copies were all saved (`reviewCount` 20, 20 rows), and 10 identical parallel subject creates gave exactly one 201 and nine 400. The logs showed 25 saves, 6 real clashes that re-ran correctly, 0 busy and 0 emails.
- The normal Docker stack passed `scripts/smoke.sh` 9/9 and a 33-check extended smoke test.
- A browser test showed that the photo is fetched only when "View note" opens (`GET /api/reviews/<id>/attachment`) and that it renders, with no console errors.
- The adapter image digest was proven by a successful build (`/opt/extensions/lambda-adapter` present). `boto3` 1.43.103 in the image supports `PutObject` `IfMatch`/`IfNoneMatch` and `GetObject` `IfNoneMatch`, and accepts `retries={"total_max_attempts": 1}`.

Not yet verified, because it needs real AWS: the bucket policy on real S3, real S3 latency per save, and the clash rate under a real class (checks A16, M4 and M6 below).

**Automated: `scripts/smoke-cloud.sh SITE [API] [--burst]`.** API defaults to SITE. Every signup uses the password `smoke-pass-2026`.

| # | Check | Expected |
|---|---|---|
| S1 | `GET /` | 200, `content-type: text/html` |
| S2 | `GET /style.css` | 200, `text/css` |
| S3 | `GET /js/main.js`, `GET /js/config.js` | 200, content-type contains `javascript` |
| S4 | `GET /js/does-not-exist.js` | 403 or 404, **never 200** (proves there is no SPA rewrite) |
| S5 | `GET /` headers | `strict-transport-security`, `x-content-type-options: nosniff`, `content-security-policy` present, and the CSP contains the `sha256-` hash of the live `index.html` inline script |
| S6 | `GET /Dockerfile`, `/nginx.conf`, `/_nocache_server.py` | not 200 (never uploaded) |
| A1 | `GET /api/health` (the first call after a deploy, so usually a cold start; in a new bucket it also creates `db/navigator.db`) | 200 `{"status":"ok"}`, `cache-control: no-store`, `x-cache` never `Hit`, `time_total` under 8 s |
| A2 | signup user A (`smoke+<epoch>a@example.test`) | 201 with a token, `time_total` under 8 s |
| A3 | `GET /api/auth/me` with A's token | 200 with A's email (**proves `Authorization` reaches Flask on GET**) |
| A4 | `GET /api/auth/me` with no token | 401 |
| A5 | signup user B, then `GET /api/auth/me` as B | B's email (no cross-user caching) |
| A6 | A: create subject, create topic, `PUT /api/user/onboarding` | 201, 201, 200 (PUT passes CloudFront) |
| A7 | A: `POST /api/log-review` with a tiny PNG data URL | 201 |
| A8 | A: `GET /api/subjects` | 200; body has no `data:image`; the review has `id` and `hasAttachment: true` |
| A9 | `GET /api/reviews/<id>/attachment` as A, as B, and with no token | 200 with the data URL (read back from its own S3 object), 404, 401 |
| A10 | B: `GET /api/subjects`; B: log-review on A's topic | no subjects; 404 |
| A11 | A: two new topics logged with `shaky` and `solid` | identical `nextDue` (confidence never changes scheduling) |
| A12 | duplicate subject; wrong password | 400; 401 with the generic message |
| A13 | `PUT /api/settings {"dailyCap": 4}`; `GET /api/priorities` | 200; 200 (proves the NZ clock works in the function) |
| A14 | 5 rounds of parallel `GET /api/subjects` and `GET /api/priorities` | all 200 (no throttling at normal load) |
| A15 | `--burst` only, the go-live gate: right after a deploy (cold), 30 parallel authenticated `GET /api/auth/me` plus 30 parallel `GET /api/subjects` | all 200; any 429 or 5xx means the quota or throttle is not ready and the URL must not be shared |
| A16 | A: two rapid parallel `POST /api/log-review` on one new topic | both 201, and that topic's `reviewCount` goes up by exactly 2 (a clash between Lambda copies re-runs, it never loses or doubles a save) |

The key manual curl, if A3 fails:

```
SITE=$(terraform -chdir=infra output -raw site_url)
TOKEN=$(curl -s -X POST "$SITE/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Probe\",\"email\":\"probe+$(date +%s)@example.test\",\"password\":\"smoke-pass-2026\",\"yearLevel\":12}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -i "$SITE/api/auth/me" -H "Authorization: Bearer $TOKEN" | grep -i -E '^HTTP|x-cache|cache-control|email'
```

If this returns 401, switch to the fallback in section 4.6 (`-var auth_in_cache_key=true`, then plan, STOP, apply), then re-run.

**Manual:**
- M1: on a phone using mobile data, open the site, sign up, finish onboarding, add a subject and topic, log a review with a real camera photo **well under 1 MB** (the browser gives up after 25 s, H11), and open "View note": the photo shows.
- M2: log in on a second device and see the same data.
- M3: in desktop Chrome DevTools, the console has no CSP or MIME errors. A `/favicon.ico` 403 is expected and is not a failure (L8).
- M4: CloudWatch Logs `/aws/lambda/nrn-api` show no email addresses, `InsecureKeyLengthWarning` or `WORKER TIMEOUT`; they show `[s3db] saved` lines for the smoke writes and **no** `[s3db] busy` lines.
- M5: `aws lambda get-function --function-name nrn-api --query 'Configuration.[State,LastUpdateStatus]'` returns `Active` and `Successful`.
- M6: a human (never Claude) runs the unconditional PUT to `db/deny-probe` from section 7.7 step 23 and gets `AccessDenied` (403).

### 8.2 Roll back

| What broke | Roll back |
|---|---|
| API code | Put the previous tag in `infra/image.auto.tfvars` (ECR keeps the newest 15; list them with `aws ecr describe-images --repository-name nrn-api --query 'sort_by(imageDetails,&imagePushedAt)[].imageTags'`), confirm it exists (section 6.5), then plan, STOP and apply. |
| Front-end | Pick the previous copy in `infra/.deploys/<timestamp>/front-end.tgz`, extract it to a scratch folder (`mkdir -p /tmp/nrn-rollback && tar -xzf <file> -C /tmp/nrn-rollback`), then run `scripts/deploy-web.sh /tmp/nrn-rollback`. If the older copy has a different inline-script hash, the script stops: apply with that `index.html` first, or restore single objects from S3 versions (kept 30 days). |
| Infrastructure change | Revert the `.tf` edit, then plan, STOP and apply. A plan that destroys or replaces `aws_s3_bucket.data` is never applied. |
| Data | A human restores an earlier version of `db/navigator.db` from S3 versioning (kept 14 days), with a conditional PUT (section 4.10). Rehearse it before the class depends on the app. |
| The S3 design's ceiling | Not a quick rollback: plan the move to a managed database or to the EFS fallback (section 10). Until then, lower the API throttle to reduce clashes. |
| Emergency brake (abuse, runaway cost) | `terraform apply -var api_rate_limit=0 -var api_burst_limit=0`: every API call gets 429 at once and the static site stays up. Undo by applying the normal values. |

### 8.3 Tear down (a human runs these; Claude only prepares them)

1. Keep the data or not? To keep it, download the current `db/navigator.db` and the `photos/` prefix to a private place the adult controls (it is student data; never into a git repo and never to Claude), for example `aws s3 cp "s3://<data_bucket>/" <private folder>/ --recursive`.
2. Remove `prevent_destroy` from `aws_s3_bucket.data` (a deliberate edit).
3. Remove the data bucket's delete protection: delete its bucket policy (console: the data bucket, Permissions, Bucket policy, Delete). Without this, emptying the bucket fails on `db/` with "Access Denied".
4. Empty the data bucket, including all versions (console: the bucket, Empty).
5. Run `terraform -chdir=infra destroy` and type `yes`. The web bucket (`force_destroy`) and the ECR repository (`force_delete`) are removed with their contents.
6. Bootstrap: remove `prevent_destroy`, empty the state bucket including all versions (console: bucket, Empty), then `terraform -chdir=infra/bootstrap destroy`.
7. Confirm nothing is left. Each of these should print an empty list:
   ```
   aws resourcegroupstaggingapi get-resources --region ap-southeast-2 --tag-filters Key=Project,Values=nrn --query 'ResourceTagMappingList[].ResourceARN'
   aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=Project,Values=nrn --query 'ResourceTagMappingList[].ResourceARN'
   aws s3api list-buckets --query "Buckets[?starts_with(Name, 'nrn-')].Name"
   aws cloudfront list-distributions --query 'DistributionList.Items[].Id'
   aws ecr describe-repositories --region ap-southeast-2 --query 'repositories[].repositoryName'
   aws logs describe-log-groups --region ap-southeast-2 --log-group-name-prefix /aws/lambda/nrn --query 'logGroups[].logGroupName'
   ```
8. The next day: Billing, Bills shows only cents, and Cost Explorer's daily view is flat. The adult may then close the account from the Account page.

---

## 9. Cost

All figures are estimates at Sydney prices (USD, before tax). The workload assumptions are stated.

| Item | Classroom: 30 students, about 15,000 API calls a month | 1,000 students, about 600,000 API calls a month |
|---|---|---|
| CloudFront | USD 0 (always free: 1 TB and 10M requests) | USD 0 (still inside the allowance, unless photos get heavy) |
| S3 web (versioned, 30-day old versions) and state | under USD 0.01 | under USD 0.05 |
| API Gateway HTTP API (USD 1.29 per million) | USD 0.02 | USD 0.77 |
| Lambda (1 GB; always free 400,000 GB-s and 1M requests) | USD 0 (about 3,000 GB-s; a little more with the S3 round trips, still inside the allowance) | USD 0 (about 120,000 GB-s) |
| S3 data bucket storage (the database object, 14 days of old versions, photos with 30 days of old versions) | under USD 0.10 (**estimate**) | not a supported size for this database design (section 10) |
| S3 data bucket requests (one conditional GET per API request, one PUT per write, one PUT per new photo) | a few cents (**estimate**: about 15,000 GETs and a few thousand PUTs) | not a supported size for this database design (section 10) |
| ECR (USD 0.10/GB-month, up to 15 images) | USD 0.02 to 0.15 | same |
| CloudWatch Logs (5 GB always free) | USD 0 | USD 0 |
| VPC, NAT gateway, endpoints, EFS, AWS Backup | none in this design | none, unless the chosen managed database needs a VPC |
| WAF (phase 3: web ACL USD 5 + USD 1 per rule + USD 0.60 per million requests) | not used | about USD 7 |
| Managed database (phase 4, needed at this size) | not used | roughly USD 8 (demo usage) to 40 a month for Aurora Serverless v2 |
| **Total** | **about USD 0.05 to 0.35 (estimate)** | **roughly USD 16 to 50 (estimate; depends on the database chosen)** |

The S3 lines depend on the workload. Every API request makes one conditional GET (usually a 304 with no download), and every write uploads the whole database file once, or more if it clashes and re-runs. Each save also keeps the previous file as an old version for 14 days, so version storage is roughly the file size times the saves in 14 days. With photos kept out of the file, that stays small at classroom scale. In week one, count the `[s3db] saved` and `conflict` lines, watch the Cost Explorer daily view, and revise this table from real numbers.

Free-tier notes:
- Accounts created on or after 15 Jul 2025 get USD 100 in credits on either plan, plus up to USD 100 more for activities (setting a budget is one). Credits expire 12 months after the account is created.
- Always free: Lambda (1M requests and 400,000 GB-s a month), CloudFront pay-as-you-go (1 TB, 10M requests), CloudWatch (5 GB of logs, 10 alarms).
- **Not** always free for new accounts: S3, ECR and API Gateway. Credits cover them.
- The Free plan closes the account after 6 months or when the credits run out, and AWS deletes the data 90 days later. Upgrading keeps any remaining credits. For a URL that must keep working, pick the Paid plan and set budgets.
- CloudFront flat-rate plans are not available to Free Tier accounts, and the plan does not need them.

At 1,000 students the real limit is the **S3 database's write ceiling (section 10), not money**. An Aurora Serverless v2 migration would add roughly USD 8 (demo usage) to 40 a month, depending on active hours at USD 0.20 per ACU-hour.

---

## 10. Think big: phased scale path

**Honest ceiling of the S3 database.** It is fine for one or two classes: a database under about 20 MB and about 1 to 2 writes per second sustained. A burst of 30 writes at once sees retries and 1 to 2 s latency, but every save lands or the student gets a clear "busy" message with nothing half-saved. It is **not suitable for 1,000 students**: the file is bigger, each upload takes longer, and more saves clash.

**Scale triggers.** Move to a managed database (RDS/Aurora or DynamoDB) or to EFS when **any** of these is true:
- more than 5% of writes clash (`conflict` lines compared with `saved` lines),
- any "busy" 503 in a week (any `[s3db] busy` line),
- p95 write latency over 1 s (the `ms=` value on `saved` lines is the upload time, the main extra cost of a write),
- the database object passes 20 MB (the `bytes=` value on `saved` lines).

The `[s3db]` lines carry only the event, etag, size and time, never personal data, so they are safe to keep and query. A CloudWatch Logs Insights query on `/aws/lambda/nrn-api` (**VERIFY** it in the console):

```
fields @timestamp, @message
| filter @message like /\[s3db\]/
| parse @message "[s3db] * *" as event, details
| stats count() by event
```

| Phase | What | Trigger | Notes |
|---|---|---|---|
| 1 (this plan) | MVP above, including the quota gate | now | |
| 2 | **A rehearsed restore**: a human restores the newest version of `db/navigator.db` onto itself with a conditional PUT (section 4.10), which proves every step without losing a save; lengthen the `db/` version expiry if 14 days is too short | before the whole class relies on it | Every save is already a complete, checked version, so no snapshot job is needed. |
| 2 | **CI/CD with GitHub Actions OIDC**: CI is already fixed in the working copy (no ruff steps; runs on `v*` tags on `main` plus manual dispatch; locally through `act`); pin `ubuntu-24.04`; an IAM OIDC provider `token.actions.githubusercontent.com` (no thumbprint); a role trusted only for the release tags (`repo:ngocnxx/digit-yr12-project:ref:refs/tags/v*`; `ci.yml` checks the tag is on `main`); `aws-actions/configure-aws-credentials@v6`, `hashicorp/setup-terraform@v4`; `permissions: id-token: write, contents: read`; plan on a manual run, apply on a release tag with a manual approval environment | more than one deployer, or weekly deploys | Needs the user to choose the release branch and to commit, push and tag (only when asked). No stored AWS keys. Committed code also makes image tags and front-end rollback come from git. |
| 2 | **Smaller, faster photos**: photos are already their own S3 objects. Next: shrink them in the browser (canvas, longest side 1600 px, JPEG 0.8, typically under 400 KB), serve presigned GET URLs straight from S3 instead of through Lambda (add the S3 host to CSP `img-src`), and add a delete-photo route | slow uploads, slow "View note", or any photo complaint | The lasting fix for H11. |
| 2 | **Idempotent saves**: a client-generated request id on `/api/log-review`, ignored if seen before | any double-count report | Stops a retried tap from moving the schedule twice. (A re-run after an S3 clash already never counts twice.) |
| 3 | **Abuse protection**: WAF on CloudFront with a rate-based rule on `/api/auth/*`; an origin-verify secret header checked by Flask, or a custom domain with `disable_execute_api_endpoint`; a dummy hash on login misses; 7-day tokens plus `token_version` (real logout) | the URL is shared beyond the class, a budget alert fires, or odd sign-ups appear | WAF costs about USD 7 a month. The minimum password of 8 is already done. |
| 3 | **Custom domain**: an ACM certificate in **us-east-1** (with provider v6, `region = "us-east-1"` on the `aws_acm_certificate` resource), a Route 53 hosted zone (USD 0.50 a month) or external DNS, and CloudFront `aliases` | a memorable URL is wanted | `config.js` already uses a port-based check (section 5.8), so any domain name works. |
| 3 | **Observability**: CloudWatch alarms on Lambda Errors and Throttles and API 5xx, plus metric filters and alarms on `[s3db] busy` and `[s3db] conflict`, to email via SNS; structured JSON logs; a small dashboard | before the first real class | Inside the 10 free alarms. |
| 3 | **Privacy features**: delete-my-account (uses the existing `ON DELETE CASCADE`, and must also delete the user's `photos/<user_id>/` objects, so the role would need `s3:DeleteObject` on `photos/*` only), data export, a short privacy notice | before real students (they are likely under 18) | |
| 4 | **Managed database or EFS**: Aurora Serverless v2 PostgreSQL at 0 ACU (auto-pause, about 15 s resume), Aurora DSQL (serverless, no VPC, free up to 100k DPU and 1 GB a month; needs retries and no photos in rows), DynamoDB (full rewrite, 400 KB items), or **EFS** (the first version of this plan; no code change, because the app already accepts a `/mnt/` `DATABASE_PATH` with `S3DB_BUCKET` unset, but it brings back a VPC, mount targets, security groups and backups) | any scale trigger above; more than one school; or the school needs the RDS claim to be true | Aurora needs a data-layer port: `?` becomes `%s`, AUTOINCREMENT becomes IDENTITY, SQLite date functions are rewritten. Aurora and EFS put the Lambda back into a VPC; DSQL and DynamoDB do not. A human copies the current `db/navigator.db` into the new store once. |
| 4 | **Environments**: separate `dev` and `prod` state keys and variables; deploy PR previews to dev | a second developer, or risky changes | |
| 5 | **NZ Region**: ap-southeast-6 is possible now, because the S3 design needs no EFS (decision 12.3) | a data-residency preference | Opt-in Region; check every service first. The EFS fallback still cannot run there (Lambda cannot mount EFS in the NZ Region). |

Target state after phase 4: CloudFront (custom domain, WAF) serves the S3 site; `/api/*` goes to API Gateway, then Lambda (outside any VPC unless the chosen database needs one), then a managed database; photos live in S3 behind presigned URLs; GitHub Actions deploys through OIDC; alarms email the adult and the student.

Out of scope, noted only: the finished scholarship report says the deployed database is Amazon RDS, which will not match this S3 build.

---

## 11. GitHub Pages alternative (honest comparison)

| Aspect | CloudFront + S3 (chosen) | GitHub Pages |
|---|---|---|
| Repo visibility | Stays private | GitHub Free requires a **public** repo (or GitHub Pro, possibly through the Student Pack). The working copy is private today. |
| Policy | Fine for logins | GitHub says Pages "shouldn't be used for sensitive transactions like sending passwords". This app has signup and login forms. |
| Origin | One origin; no CORS; no preflights | Cross-origin: every authenticated call adds an OPTIONS preflight (an extra round trip and an extra Lambda call, which also counts against the concurrency quota) |
| Token exposure | Own origin | The token sits in `localStorage` on `ngocnxx.github.io`, which every Pages site of that account shares |
| Headers | CSP, HSTS and friends via a response headers policy | No custom headers. CSP only through a `<meta>` tag (no `frame-ancestors`). |
| Caching | `no-cache` plus invalidation on deploy | Fixed `max-age=600`, no invalidation, up to 10 minutes of mixed module versions |
| API | Same distribution | Still needs its own HTTPS endpoint (CloudFront or `execute-api`) |

What would change for Pages:
1. Add a classic `<script src="js/env.js"></script>` before the module script in `index.html`, generated at deploy time with `window.NRN_API_BASE = 'https://<api-host>'` (no trailing slash; `api.js` concatenates).
2. Set `CORS_ORIGIN=https://ngocnxx.github.io` exactly, and configure CORS in **one** layer only (Flask, or API Gateway `cors_configuration`, never both).
3. Publish with an Actions workflow that uploads only `index.html`, `style.css` and `js/`.
4. Make the repo public or pay for Pro.

**Verdict: not recommended.** It trades a few cents a month for a public repo, weaker security and more moving parts.

---

## 12. Decisions the user must make

| # | Decision | Options | Recommended default |
|---|---|---|---|
| 12.1 | Submitted repo privacy | Private now; or `git rm --cached` plus a history purge | **Make it private today** (first add the teacher as a collaborator if they still need access), then decide the purge with the school |
| 12.2 | Account owner and plan | Adult on the Paid plan; adult on the Free plan | **Adult, Paid plan** with USD 10 and zero-spend budgets. The Free plan closes the account at 6 months. |
| 12.3 | Region | Sydney; NZ (ap-southeast-6, opt-in) | **Sydney** (cheaper, no opt-in). NZ is possible now, because the S3 design needs no EFS; choose it only for a data-residency preference. |
| 12.4 | Database | The S3 object (implemented); EFS (the fallback); S3 Files; Aurora Serverless v2 | **The S3 object now**; the section 10 triggers decide when to move |
| 12.5 | Who may sign up | Open sign-up; invite code; only the class | **Share the URL only with the class for now**, and only after the quota gate (7.7 step 25); add an invite code (a small change) before sharing more widely |
| 12.6 | Student's AWS rights | Admin with MFA under supervision; the adult runs every apply | **Admin with MFA**; every apply still needs a human "yes" |
| 12.7 | Code changes in section 5 | Keep as implemented; revert item by item | **Keep** (done and tested); only the scripts in 5.11 and the infrastructure remain. The optional items in 5.12 are asked item by item. |
| 12.8 | Photos in the cloud MVP | Lazy-load plus one S3 object per photo (done); disable photo upload | **Keep the done version**; shrink photos and use presigned URLs in phase 2 |
| 12.9 | Minimum password | Keep 4; raise to 8 | **8 (done)**, including the tests and `smoke.sh` |
| 12.10 | Hosted error wording | Keep developer text; neutral text plus retry | **Neutral text (done)**; the retry and dismissible banner are optional (5.12) |
| 12.11 | CSP in the MVP | Yes; later | **Yes** (Terraform computes the hash; `deploy-web.sh` checks it) |
| 12.12 | Release branch for CI/CD | `develop`; fast-forward `main` | **Fast-forward `main`**, tag releases `v*` on `main` (`ci.yml` now runs on those tags), protect `main`, deploy from `main` |
| 12.13 | Custom domain | No; yes | **No** for the MVP |
| 12.14 | Lambda quota increase | Request 1,000 now; wait | **Request now (required, free)**; share the URL only at 100 or more; reserve 10 at 110 or more |
| 12.15 | Keep the token on 429/5xx (`router.js`) | Keep the old behaviour; clear only on 401 | **Clear only on 401 (done)** |
| 12.16 | Browser request timeout (`api.js`) | Keep 10 s; raise to about 25 s | **25 s (done)**; shrink photos in phase 2 |

---

## 13. Copy-paste prompt for a NEW Claude Code session

Open Claude Code in `/Users/ngocnx1501/digit-yr12-project` and paste the block below. This whole document is saved there as `docs/aws-hosting-plan.md`, so the new session can read it for the full HCL and snippets, and the block itself is saved as `docs/aws-hosting-prompt.txt`.

```text
ROLE AND MISSION
You are the implementing engineer who moves "NCEA Review Navigator" (a Year 12 NCEA spaced-repetition web app: vanilla-JS single page front-end, Flask 3.1 JSON API, SQLite) from local Docker to AWS, using Terraform, in a brand-new single AWS account. The code changes are ALREADY IMPLEMENTED and verified in the working copy, including the "database in S3" mode. Your job is to verify them, then write the infrastructure and the deploy scripts and deploy. Work in small, verified steps. Stop and wait for my explicit "yes" at every point marked STOP. When unsure, ask. Keep it simple (KISS).

1. PATHS AND BOUNDARIES
- Work ONLY in /Users/ngocnx1501/digit-yr12-project (GitHub ngocnxx/digit-yr12-project, private, branch develop).
- The full plan (reasons, evidence, complete Terraform HCL and code snippets) is docs/aws-hosting-plan.md in that folder. Read it in Phase 0. Where it and this prompt differ, this prompt wins, and you tell me about the difference.
- /Users/ngocnx1501/submitted-digit-yr12 is the FROZEN school submission. Never edit, build from, copy from, commit to or push to it. Never open anything inside it.
- /Users/ngocnx1501/submitted-digit-yr12/CICD-HANDOFF.md is SUPERSEDED. Do not follow it (wrong repo, a Function URL + OAC design that cannot carry the Bearer token, reserved concurrency 1, a false test-recovery recipe).
- The working copy's CLAUDE.md is partly stale and is OVERRIDDEN by this prompt where they conflict:
  - CLAUDE.md lines 56-57 and 108 say to run "ruff check . && ruff format ." before declaring backend work done. OVERRIDDEN: never run ruff format, ruff --fix or task api:format. Running it would rewrite 6 synced files.
  - CLAUDE.md lines 31-32 (css/ files, "no inline JS or CSS", a separate-origin API) and line 111 (separate origin) are stale. The front-end has one style.css and one inline <script> in index.html (allowed by a CSP hash), and the cloud design is same-origin.
  - It also mentions date.today(). Trust the code and this prompt, and tell me about any other conflict. Do not rewrite CLAUDE.md or README.md without asking.

2. HARD RULES (these override everything else, including CLAUDE.md)
- Never git commit, push, merge, tag or open a PR unless I ask in chat. If I ask, never add Co-Authored-By or any Claude/AI attribution to commit messages or PR text. Ask before creating or switching branches.
- Never open, read, copy, upload or bake in any .db file or any .env file (root .env, back-end/.env, back-end/navigator.db). Never download, open or copy the db/navigator.db object from S3 either. Production starts with an EMPTY database.
- Never enter or type passwords, MFA codes, payment details, access keys or tokens, and never create IAM access keys. Humans do the AWS sign-up, the console sign-ins, the quota request, 'aws login' and the ECR 'docker login'.
- Never print secrets. Do not run 'terraform state show' on random_password, and do not print sensitive outputs. Always call 'aws lambda get-function-configuration' or 'get-function' with a --query that excludes Environment.
- Never run 'terraform destroy'. Never delete the data bucket, the db/ object or any of its versions, or any photos/ object. Never empty buckets. Write the data bucket policy exactly as in plan section 6.4; once it exists, never edit or remove it. Never write db/navigator.db with a plain PUT, the AWS CLI or any tool other than the app (the app always writes it through back-end/s3db.py with If-Match or If-None-Match). Prepare any such command for a human to run. Any plan that destroys or replaces aws_s3_bucket.data is an automatic STOP; so is any plan that changes or removes its versioning, lifecycle, public access block or bucket policy after the first apply.
- Never delete ECR images by hand. Before any apply that changes image_tag, confirm the tag exists with "aws ecr describe-images --repository-name nrn-api --image-ids imageTag=<tag>".
- The confidence rating must NEVER change scheduling. Do not modify scheduling.py or any scheduling maths. The existing test test_log_review_stores_optional_fields_without_affecting_schedule must keep passing.
- UI symbols come from the vendored Lucide set only (front-end/js/icons.js). Never use emoji anywhere.
- Never use em dashes in user-facing text, docs, comments or messages you write.
- Do not reformat files you are not otherwise changing. 'task test' is broken (it runs ruff first); run pytest directly.
- The code changes are already implemented. Do not redo, rewrite or "improve" them, and do not change app code (back-end or front-end) without asking. No new frameworks, no refactors. Only the deploy scripts and the infrastructure remain.
- Publishing is a STOP: the first scripts/deploy-web.sh makes the site public. Sharing the URL with students is gated on the Lambda quota (section 6, Phase 6).

3. VERIFIED STATE (as of 2026-09-26; re-check with git status, git log --oneline -3, docker version, aws --version, which terraform)
- develop = 0286f21 "adjusted code", pushed. main = 94c34e6 (a June stub). There is no branch protection. Today's code changes are UNCOMMITTED in the working tree (my rule: nothing is committed unless I ask); section 5 below lists the files. The working copy's .github/workflows/ci.yml now runs only on v* tags that are on main, plus manual dispatch (workflow_dispatch), and locally through act; the ruff steps were removed. The last CI run on GitHub (before that change) was red. Leave CI alone unless I ask.
- 60 back-end tests pass on the host (back-end/.venv, Python 3.13) and inside the Docker image: 34 original, 11 in back-end/tests/test_cloud.py, and 15 in back-end/tests/test_s3db.py, which uses an in-memory fake S3 (back-end/tests/fake_s3.py; no AWS and no boto3 needed). Seven deliberate code mutations (blind overwrite, always upload, reply before save, fingerprint after migration, photo back in the list, no key guard, delete guard off) were each caught by the tests.
- docker compose (web nginx on 5500, api gunicorn on 5050, named volume db_data) passes scripts/smoke.sh 9/9 and a 33-check extended smoke test. The compose profile "s3" (moto 5.1.21 as a local S3, plus two API copies on ports 5061 and 5062 sharing one database object) passes scripts/smoke-s3.sh: 20 parallel reviews across both copies were all saved (reviewCount 20, 20 rows), and 10 identical parallel subject creates gave exactly one 201 and nine 400; the logs showed 25 saves, 6 real clashes re-run correctly, 0 busy and 0 emails. moto 5.1.21 and 5.1.14 were checked to match real S3 on all six conditional-write rules. A browser test showed the photo is fetched only when "View note" opens (GET /api/reviews/<id>/attachment) and renders, with no console errors.
- back-end/Dockerfile: python:3.13-slim. The Lambda Web Adapter line "COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 /lambda-adapter /opt/extensions/lambda-adapter" and ENV AWS_LWA_PORT=5000, AWS_LWA_READINESS_CHECK_PATH=/api/health and AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200-299 are ALREADY in it. pip installs requirements plus "gunicorn>=23,<24" and "boto3>=1.36,<2" (boto3 only in the image, never in requirements.txt). It runs as appuser; CMD runs "python -c 'import db; db.init_db()'" and then "gunicorn --bind 0.0.0.0:5000 app:app". A build proved the adapter digest (/opt/extensions/lambda-adapter present). boto3 1.43.103 in the image supports PutObject IfMatch/IfNoneMatch, GetObject IfNoneMatch and retries total_max_attempts=1. back-end/.dockerignore excludes .venv, .env, *.db.
- The S3 database (back-end/s3db.py; on only when S3DB_BUCKET is set): the SQLite file is one S3 object (S3DB_KEY, default db/navigator.db). Each process keeps a copy in /tmp and handles one API request at a time. Before a request uses the DB it sends GET If-None-Match <etag> (304 = unchanged, no download). If the request changed the DB (SQLite's file change counter, header bytes 24-27, plus the size), it uploads BEFORE replying with PUT If-Match <etag> (If-None-Match * for a brand-new DB). On 412/409 it discards the copy, downloads the new version and re-runs the whole request (WSGI middleware ReplayOnConflict, up to S3DB_MAX_ATTEMPTS=5, jittered backoff); after that, a JSON 503 "busy" with Cache-Control no-store. SDK retries are off for the database PUT (a retried save could count twice); an unclear PUT is checked with HEAD for a per-write token. It refuses to create an empty DB if the key has version history. Photos are separate objects photos/<user_id>/<sha256> (If-None-Match *) with an "s3:" pointer in reviews.attachment. Log lines "[s3db] saved|conflict|busy|unavailable|save-failed|saved-unclear-ok" carry only etag, size, time, attempt or status, never personal data.
- app.py: locally SECRET_KEY still defaults to 'dev-insecure-change-me', but on Lambda or with APP_ENV=production the app refuses to start unless SECRET_KEY is at least 32 characters and not the dev key; on Lambda it also refuses to start unless S3DB_BUCKET is set or DATABASE_PATH starts with /mnt/. MAX_CONTENT_LENGTH is 3 MiB with a JSON 413. Cache-Control: no-store on /api/*. /api/health touches the DB and returns JSON 503 on failure. CORS still defaults to '*'. clock.py uses zoneinfo with APP_TIMEZONE (default Pacific/Auckland; the zone data exists in the Debian image).
- Other fixes already done: GET /api/subjects returns id and hasAttachment and never photo data; GET /api/reviews/<id>/attachment is owner-only; subject-detail.js loads the photo only when a note opens; BEGIN IMMEDIATE in log_review, create_subject and assessment end; no emails in logs; signup hashes the password before opening the DB; minimum password 8 (back-end, front-end, signup placeholder, tests, scripts/smoke.sh; the tests and smoke.sh use "secret-pass"); router.js clears the token only on 401; api.js REQUEST_TIMEOUT_MS = 25000; neutral error text in index.html and api.js; config.js uses a port-based check (port 5500 or 5501, or a host ending in -5500.app.github.dev), so it returns '' (same origin) on *.cloudfront.net; nginx.conf sends Cache-Control: no-cache; .gitignore has the Terraform entries and infra/.deploys/.
- index.html has exactly one inline <script> (lines 10-19, LF line endings; hash sha256-Bs3dMPZpJl4yu6i4aoEHNoqe6dkmNQOo007ow/o95jI=, unchanged by the text edits) and no favicon link. The app uses a hash router, and the dashboard fires /api/subjects and /api/priorities in parallel.
- Still true: PBKDF2 at 1,000,000 iterations takes about 0.53 s per core, so Lambda needs 1024 MB. New AWS accounts have reduced Lambda concurrency and memory quotas (AWS does not publish the numbers).
- Local tools: Intel Mac (x86_64), Docker 29.5.3 (containerd image store; "docker push --platform" is supported), AWS CLI 2.36.49, Python 3.13 in back-end/.venv. Terraform is NOT installed. Current releases: Terraform 1.16.4, hashicorp/aws 6.66.0, hashicorp/random 3.9.1, Lambda Web Adapter 1.1.0.

4. TARGET ARCHITECTURE (decided; do not redesign without asking)
- Region ap-southeast-2 (Sydney) by default: cheaper and no opt-in. The NZ Region (ap-southeast-6, opt-in) no longer has a hard blocker, because the design uses no EFS; use it only if I choose it. One account owned by an adult.
- One CloudFront distribution (default *.cloudfront.net certificate, PriceClass_All, http2and3, default_root_object index.html, NO custom_error_response blocks).
  - Default behaviour: a private, versioned S3 web bucket (noncurrent versions expire after 30 days) through OAC (origin type s3, sigv4, always), redirect-to-https, GET/HEAD, compress, cache policy Managed-CachingOptimized 658327ea-f89d-4fab-a63d-7e88639e58f6, plus a custom response headers policy: HSTS 1 year, nosniff, frame DENY, Referrer-Policy strict-origin-when-cross-origin, and CSP "default-src 'none'; script-src 'self' 'sha256-<computed by Terraform from the single inline <script> in front-end/index.html>'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'". Output the CSP string as a Terraform output named csp.
  - Ordered behaviour /api/*: origin = the HTTP API execute-api domain, https-only, all 7 methods, origin request policy Managed-AllViewerExceptHostHeader b689b0a8-53d0-40ab-baf2-68738e2966ac, and cache policy chosen by a bool variable auth_in_cache_key (default false): false = Managed-CachingDisabled 4135ea2d-6df8-44a3-9df3-4b5a84be39ad; true = a custom aws_cloudfront_cache_policy "nrn-api-per-token" with the Authorization header in the cache key, all query strings, no cookies, TTLs 0/0/1. Write that policy now so the fallback is a variable flip. Never AllViewer (it forwards Host). Never a shared caching policy on /api/*. Never OAC in front of a Lambda Function URL.
  - Web bucket policy: s3:GetObject for cloudfront.amazonaws.com only, with AWS:SourceArn equal to the distribution.
- API Gateway HTTP API: no cors_configuration; AWS_PROXY integration with payload_format_version "2.0" and timeout 30000 ms; route $default; stage $default with auto_deploy and default_route_settings throttling from variables api_rate_limit (default 10) and api_burst_limit (default 20); raise them to 25 and 50 only after the Lambda quota is at least 100. A lambda_permission for apigateway.amazonaws.com.
- Lambda "nrn-api": package_type Image from ECR, x86_64, 1024 MB, timeout 20 s, ephemeral storage left at the default 512 MB (it holds 2 copies of the DB), NO vpc_config, NO file_system_config, reserved_concurrent_executions = var (default -1, meaning none).
  - ECR repo: IMMUTABLE, scan on push, lifecycle rule 1 expires untagged images after 1 day, rule 2 (tagStatus any) keeps the newest 15. Never a rule that could expire the live image.
  - Environment: APP_ENV=production, SECRET_KEY=random_password (64 characters, no specials), S3DB_BUCKET=<the data bucket name>, S3DB_KEY=db/navigator.db, S3DB_PHOTO_PREFIX=photos/, DATABASE_PATH=/tmp/navigator.db, APP_TIMEZONE=Pacific/Auckland, CORS_ORIGIN=https://none.invalid (a variable; the app is same-origin), GUNICORN_CMD_ARGS="--timeout 0 --workers 1 --threads 1". Never set S3DB_ENDPOINT_URL in the cloud (it is for the local test S3 only).
  - Role: AWSLambdaBasicExecutionRole plus one inline policy: s3:GetObject and s3:PutObject on <data bucket ARN>/db/navigator.db and <data bucket ARN>/photos/*; s3:ListBucket and s3:ListBucketVersions on the data bucket ARN (ListBucket makes a missing key return 404 instead of 403). Nothing else. depends_on: the log group, the attachment and the inline policy.
  - Log group /aws/lambda/nrn-api with 14-day retention, created before the function.
  - A weekly EventBridge rule invokes the function so it never goes Inactive.
- Data bucket (infra/data.tf): aws_s3_bucket.data named "nrn-data-<account>-ap-southeast-2" with lifecycle prevent_destroy (no force_destroy); versioning Enabled; SSE-S3 (AES256); public access block (all four true); ownership controls BucketOwnerEnforced; lifecycle rules: db/ noncurrent versions expire after 14 days, photos/ noncurrent versions after 30 days, abort incomplete multipart uploads after 1 day; bucket policy with three Deny statements for all principals: (1) s3:* on the bucket and its objects when aws:SecureTransport is false; (2) s3:PutObject on db/* when BOTH s3:if-match and s3:if-none-match are absent (two Null conditions set to "true" in one statement); (3) s3:DeleteObject* on db/*. VERIFY that lifecycle expiry of noncurrent db/ versions still works with that delete deny.
- NO VPC, NO subnets, NO security groups, NO internet or NAT gateway, NO VPC endpoints, NO EFS, NO mount targets, NO AWS Backup. A Lambda outside a VPC reaches S3 directly.
- Image: the existing back-end/Dockerfile exactly as it is now. Build with "docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load" and push with "docker push --platform linux/amd64".
- S3 holds three things: the static site (web bucket), the database object and photos (data bucket), and the Terraform state (state bucket).
- Terraform: required_version ">= 1.15"; hashicorp/aws "~> 6.66"; hashicorp/random "~> 3.9"; default_tags Project=nrn, Environment=prod, ManagedBy=terraform. A flat root module in infra/ (versions, variables, data, ecr, lambda, api, web, outputs), with backend "s3" (key nrn/prod/terraform.tfstate, region ap-southeast-2, use_lockfile true, encrypt true; bucket supplied through a gitignored infra/backend.hcl). infra/bootstrap/ uses local state and creates the state bucket nrn-tfstate-<account>-ap-southeast-2 (versioning, SSE-S3, public access block, prevent_destroy). Use standalone aws_s3_bucket_* resources and no forwarded_values. Outputs: site_url, distribution_id, web_bucket, data_bucket, ecr_repository_url, api_endpoint, function_name, csp. Use Terraform from the HashiCorp tap, not OpenTofu.
- Honest ceiling: this is a one-or-two-class design (database under about 20 MB, about 1 to 2 writes per second sustained; a burst of 30 writes sees retries and 1 to 2 s latency). Not for 1,000 students. The fallback is EFS or a managed database when a scale trigger in plan section 10 fires (more than 5% of writes clash, any busy 503 in a week, p95 write latency over 1 s, or the database object over 20 MB).

5. CODE CHANGES: ALREADY IMPLEMENTED (do not redo; only the deploy scripts and the infrastructure remain)
Phase 1 only VERIFIES these. "git status --short" should show exactly:
- Modified: .github/workflows/ci.yml, .gitignore, back-end/Dockerfile, back-end/app.py, back-end/db.py, back-end/routes/assessment.py, back-end/routes/auth.py, back-end/routes/reviews.py, back-end/routes/subjects.py, back-end/tests/conftest.py, back-end/tests/test_api.py, docker-compose.yml, front-end/index.html, front-end/js/api.js, front-end/js/config.js, front-end/js/router.js, front-end/js/screens/auth.js, front-end/js/screens/subject-detail.js, front-end/nginx.conf, scripts/smoke.sh.
- New: back-end/s3db.py, back-end/tests/fake_s3.py, back-end/tests/test_cloud.py, back-end/tests/test_s3db.py, docs/aws-hosting-plan.md, docs/aws-hosting-prompt.txt, scripts/smoke-s3.sh.
If the list differs, report it and STOP; do not "fix" code without my yes.
Still to write (show me the file list first; STOP for approval):
a) infra/bootstrap/main.tf and infra/*.tf as in plan section 6 (versions, variables, data, ecr, lambda, api, web, outputs).
b) scripts/deploy-api.sh: tag = <git short sha>, plus "-dirty" when "git status --porcelain" is not empty, plus -<timestamp>; buildx build --load; abort if the image contains any .db or .env under /app; "docker push --platform linux/amd64"; check with "docker buildx imagetools inspect --raw" that the mediaType is a single manifest and not an index; only then write infra/image.auto.tfvars.
c) scripts/deploy-web.sh [SRC_DIR, default front-end]: compute the sha256 of the inline <script> in SRC_DIR/index.html with python3 (regex (?s)<script>(.*?)</script>, base64 of the SHA-256 digest) and compare it with "terraform -chdir=infra output -raw csp"; if the hash is missing, stop with "run terraform plan/apply first". Save a tarball of exactly index.html, style.css and js/ to infra/.deploys/<timestamp>/front-end.tgz. Then aws s3 sync SRC_DIR/ with --delete --exclude "*" --include index.html --include style.css --include "js/*" --exclude "*.DS_Store" --cache-control no-cache, then a CloudFront invalidation of "/*".
d) scripts/smoke-cloud.sh SITE [API] [--burst], in the style of scripts/smoke.sh and scripts/smoke-s3.sh, with the checks in section 7 below. Use the password "smoke-pass-2026" for every signup.
OPTIONAL, not done, ask me item by item:
   - A dismissible #server-hint banner that appears only after one retry (main.js checkServer). An edit inside the inline <script> changes the CSP hash, so it needs plan, STOP, apply before deploy-web.sh.
   - nginx try_files =404.
   - A small favicon file (an icon, never emoji) linked from index.html and added to the deploy-web.sh filter.
   - Toast max-width.

6. PHASES, STOP POINTS AND ACCEPTANCE CRITERIA
Phase 0, orientation (read-only). Verify section 3, list any differences, and confirm you will not touch the frozen repo.
  Accept: a short report. No files changed.
Phase 1, verify the implemented changes (local only; no code edits). Run "git status --short" and "git diff --stat" and compare with section 5. Run the host tests ("cd back-end && .venv/bin/python -m pytest -p no:cacheprovider") and the image tests ("docker compose build api && docker compose run --rm --no-deps api python -m pytest -p no:cacheprovider"). Run "docker compose up -d --build" and "API_BASE=http://127.0.0.1:5050 scripts/smoke.sh". Run "docker compose --profile s3 up --build -d" and "scripts/smoke-s3.sh", then check "docker compose --profile s3 logs api-s3a api-s3b" for "[s3db] saved" lines, no "[s3db] busy" lines and no email addresses. Do a browser check at http://127.0.0.1:5500: sign up (a password of at least 8 characters), log a review with a photo, and View note shows the photo, with no console errors.
  Accept: 60 tests pass on the host and in the image, smoke.sh passes 9/9, smoke-s3.sh passes, the browser check passes, and the changed files match section 5. If anything fails, STOP and report the evidence; do not re-implement or change code without my yes.
Phase 2, tools and access. STOP before installing anything: "brew tap hashicorp/tap && brew install hashicorp/tap/terraform". The human runs "aws login --profile nrn". You then use AWS_PROFILE=nrn and AWS_REGION=ap-southeast-2 and run, read-only:
  - "aws sts get-caller-identity";
  - "aws budgets describe-budgets --account-id $(aws sts get-caller-identity --query Account --output text) --query 'Budgets[].BudgetName'" (STOP if no budget exists);
  - "aws lambda get-account-settings --query 'AccountLimit'";
  - "aws service-quotas list-requested-service-quota-change-history --service-code lambda --query 'RequestedQuotas[].{Quota:QuotaCode,Status:Status,Value:DesiredValue}'" (the human submits the L-B99A9384 request; remind them if it is missing).
  Report the concurrency quota, the request status and any memory-related Lambda quota visible in Service Quotas.
  Accept: terraform version 1.16.x, the caller identity is the IAM user (not root), at least one budget exists, and the quota request is submitted.
Phase 3, bootstrap. Write infra/bootstrap/main.tf, then run init, fmt -check, validate and "plan -out=tfplan". STOP: show the plan. Apply only after my yes, then write infra/backend.hcl.
  Accept: the state bucket exists, versioned and encrypted, with public access blocked.
Phase 4, registry and image. Write infra/*.tf (versions, variables, data, ecr, lambda, api, web, outputs; no network.tf, no efs.tf), then run "terraform -chdir=infra init -backend-config=backend.hcl", fmt -check and validate. STOP before "plan -target=aws_ecr_repository.api -target=aws_ecr_lifecycle_policy.api -var image_tag=none" and before its apply. Ask the human to run the ECR docker login. Then run scripts/deploy-api.sh.
  Accept: the image is in ECR as a single-platform manifest with no .db or .env inside, and infra/image.auto.tfvars is written.
Phase 5, full stack. Re-check the budget. Confirm the image tag exists in ECR. Run "terraform -chdir=infra plan -out=tfplan". STOP: summarise the resources; confirm there is NO VPC, subnet, security group, NAT gateway, endpoint, EFS, mount target or AWS Backup resource and no public IPv4; confirm aws_s3_bucket.data is being created (not replaced) with prevent_destroy, versioning, SSE-S3, the public access block, BucketOwnerEnforced, the three lifecycle rules and the three-statement bucket policy; confirm the Lambda has the S3DB_* variables and no vpc_config; show the throttle values (10/20 unless the quota is already at least 100); and list everything that bills (the web, data and state buckets and their requests, API Gateway, Lambda, CloudFront, ECR, logs). Apply only after my yes. Wait for the Lambda to be Active. If the apply fails on memory, report the error and do not lower memory without asking.
  Accept: the apply succeeds, the outputs are printed (never secrets), and the Lambda is Active and Successful.
Phase 6, publish, verify, go-live gate.
  - STOP before the first scripts/deploy-web.sh: it makes the site reachable on the public internet. Ask me to confirm who may sign up.
  - After my yes: scripts/deploy-web.sh, then scripts/smoke-cloud.sh "$(terraform -chdir=infra output -raw site_url)". Confirm db/navigator.db now exists with "aws s3api head-object --bucket <data_bucket> --key db/navigator.db --query '{ETag:ETag,Size:ContentLength}'" (metadata only; never download it).
  - Ask the human to run the bucket-policy check in section 7 below and tell you the result.
  - Go-live gate: only when "aws lambda get-account-settings" shows ConcurrentExecutions of at least 100, propose raising api_rate_limit to 25 and api_burst_limit to 50 (plan, STOP, apply), then run scripts/smoke-cloud.sh with --burst. Tell me the URL may be shared with students only after this passes.
  Accept: every check passes (including the 8 s timing checks, the parallel log-review check and, at go-live, --burst), the human's unconditional PUT to db/ was refused with 403, CloudWatch shows "[s3db] saved" lines and no "[s3db] busy" lines, and I complete the manual phone test with a photo well under 1 MB. A 403 on /favicon.ico is expected and is not a console failure.
Phase 7, handover. Write a short runbook (infra/README.md) covering: API deploy (push, confirm tag, plan, STOP, apply, smoke); front-end deploy (if the inline script changed: plan, STOP, apply first; then deploy-web.sh and smoke); front-end rollback from infra/.deploys/<timestamp>/front-end.tgz via "scripts/deploy-web.sh <extracted dir>", with S3 versions (30 days) as the safety net; API rollback to an earlier tag that still exists in ECR; the Authorization fallback (auth_in_cache_key=true); the emergency brake (api_rate_limit=0 and api_burst_limit=0); the quota gate; the human-only database restore from an S3 version with a conditional PUT (plan section 4.10); the weekly [s3db] check against the scale triggers (plan section 10); human-only teardown (remove prevent_destroy, delete the data bucket policy, empty every version, then destroy; plan section 8.3); costs; and the open items. STOP before any git commit or push; only do it if I ask, and never with attribution.

7. REQUIRED SMOKE CHECKS (scripts/smoke-cloud.sh, plus two human or log checks)
Static:
- / returns 200 text/html.
- /style.css returns text/css.
- /js/main.js and /js/config.js have a content-type containing "javascript".
- /js/does-not-exist.js returns 403 or 404, never 200.
- / carries HSTS, nosniff and CSP headers, and the CSP contains the sha256 of the live index.html inline script.
- /Dockerfile, /nginx.conf and /_nocache_server.py are not 200.
API (password "smoke-pass-2026" for every signup):
- /api/health (the first call after a deploy, a cold start) returns 200 with cache-control no-store, x-cache is never "Hit", and time_total is under 8 s.
- Sign up user A (smoke+<epoch>a@example.test) in under 8 s, then GET /api/auth/me with A's token returns 200 and A's email. This proves Authorization reaches Flask on GET. If it returns 401, STOP and propose the fallback: -var auth_in_cache_key=true, then plan, STOP, apply.
- GET /api/auth/me with no token returns 401.
- User B's /api/auth/me returns B's email.
- A creates a subject (201), a topic (201), and PUTs onboarding (200).
- A logs a review with a tiny PNG data URL (201). Then GET /api/subjects contains no "data:image", and the review has id and hasAttachment true.
- The attachment endpoint returns 200 to A (the data URL), 404 to B, and 401 with no token.
- B sees no subjects and gets 404 logging a review on A's topic.
- "shaky" versus "solid" on two new topics give an identical nextDue.
- A duplicate subject returns 400, and a wrong password returns 401 with the generic message.
- PUT /api/settings returns 200, and GET /api/priorities returns 200.
- 5 rounds of parallel subjects plus priorities all return 200.
- Two rapid parallel POST /api/log-review on one new topic both return 201, and that topic's reviewCount increases by exactly 2.
- With --burst only (the go-live gate): right after a deploy, 30 parallel authenticated GET /api/auth/me plus 30 parallel GET /api/subjects all return 200. Any 429 or 5xx means do not share the URL.
Human check (a human runs it, never Claude): "aws s3api put-object --bucket <data_bucket> --key db/deny-probe" (an unconditional PUT to a probe key under db/, never db/navigator.db) must fail with AccessDenied (403). If it succeeds, STOP: the bucket policy is not working.
Logs (CloudWatch): no email addresses and none of InsecureKeyLengthWarning or WORKER TIMEOUT; "[s3db] saved" lines appear for the smoke writes; there are no "[s3db] busy" lines.

8. VERIFY BEFORE RELYING (still open on 2026-09-26)
1) The actual new-account Lambda concurrency and memory quotas (aws lambda get-account-settings and Service Quotas). AWS says they are reduced for new accounts but does not publish the numbers.
2) With "docker push --platform linux/amd64", the pushed tag is a single manifest that Lambda accepts. If it is an index, report it and propose a fix; do not change Docker Desktop settings yourself.
3) The Terraform aws provider and S3 backend accept 'aws login' credentials. Fallback: a credential_process profile using "aws configure export-credentials --profile nrn --format process".
4) Authorization reaches Flask through CloudFront on GET (smoke check).
5) aws s3 sync sets a JavaScript content type for .js files (smoke check).
6) The CSP hash that Terraform computes matches what the browser expects (no console violations).
7) The weekly EventBridge invoke succeeds and keeps the function Active (check the logs and function state).
8) The gunicorn --timeout 0 precaution: look for WORKER TIMEOUT after long idle periods.
9) The 'aws login' flags (aws login help).
10) Whether AWS Cost Anomaly Detection has any charge, before adding it.
11) The data bucket policy on real S3: the human's unconditional PUT to db/ is refused (403) while the app's conditional saves succeed (the smoke writes).
12) Lifecycle expiry of noncurrent db/ versions still works with the bucket policy's delete deny (after 14 days, older versions disappear).
13) Real S3 save latency and clash rate (the "[s3db] saved ... ms=" and "conflict" lines) against the scale triggers in plan section 10.
Already confirmed, no action needed: the adapter tag and digest (a build proved it); Terraform 1.16.4, aws 6.66.0 and random 3.9.1 are current; boto3 1.43.103 in the image supports the conditional parameters; moto 5.1.21 and 5.1.14 match real S3 on the six conditional-write rules.
If any check fails, stop, report the evidence, and propose the smallest fix.

9. REPORTING STYLE
Plain, specific, short. For each phase, say what changed (file paths), what you ran, the results, and the next STOP. Never paste secrets, tokens or .env contents. No emoji. No em dashes.
```
