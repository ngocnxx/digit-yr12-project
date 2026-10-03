# Spaced-repetition revision planner for NCEA students (Flask + SQLite API).

Docker first: the same commands run the app on a Mac, in the VS Code devcontainer and in
GitHub Codespaces. Needs [Docker](https://www.docker.com/products/docker-desktop/) and
[Task](https://taskfile.dev) (`brew install go-task`); the devcontainer and Codespaces already have both.

## 1. Run it (Mac with Docker Desktop)

```
task setup      # once: check Docker, create .env, build the images
task up         # start web + api, wait until healthy
```

- App: http://127.0.0.1:5500 (the page calls the API on :5050)
- Edge, like AWS: http://127.0.0.1:8080 (one address, `/api/*` forwarded, production CSP)
- API health: http://127.0.0.1:5050/api/health

`task dev` runs the same stack in the foreground and copies your edits in as you save.
`task down` stops it (your data is kept); `task reset` wipes the Docker database.

## 2. Check it (Definition of Done)

```
task verify     # tests in the image, image check, smoke tests, S3 mode
```

Then do the browser check: sign up → onboarding → add a subject and topic → log a review →
the topic is due tomorrow → reload (still signed in) → log out, with a clean console.

## 3. GitHub Codespaces

1. Code → Codespaces → Create codespace. The devcontainer is this repo's `docker-compose.yml` plus a
   `dev` service to work in; it starts the app and runs `task setup`.
2. In the terminal: `task verify` (or `task up` after a `task down`).
3. Open the forwarded port **5500** (Ports tab). The ports stay private: the page calls `/api/*` on
   its own address and nginx forwards it to the API, so no port has to be made public.

## 4. Host mode (no Docker, optional)

```
task api:dev    # Flask dev server on :5050 (creates back-end/.venv and navigator.db)
task web:dev    # the page on :5500, in a second terminal
task api:test   # pytest in the venv
```

In Codespaces host mode, open the forwarded **5050** address instead: Flask serves the page itself.

## 5. Devcontainer on a Mac (VS Code "Reopen in Container")

Same `docker-compose.yml`, same Docker engine, same database as bare metal: the `dev` container
drives Docker Desktop through its socket. Use bare metal **or** the devcontainer, one at a time —
close the devcontainer ("Reopen Folder Locally") before running `task up` on the Mac, because
VS Code's port forwarding takes over `127.0.0.1:5500` while it is open.

`task --list` shows every task. More detail: `docs/nrn-architecture.html` (Running locally) and
`docs/dev-and-test.md`.
