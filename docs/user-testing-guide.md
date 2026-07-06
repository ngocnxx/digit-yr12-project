# User-Testing Guide — getting real people to try it (with the mock)

> **Goal:** put the app in front of real testers, collect usable feedback, and record it as NCEA evidence
> — *without* needing the real backend running. Companion docs:
> [`architecture-and-flow.md`](architecture-and-flow.md), [`rebuild-roadmap.md`](rebuild-roadmap.md).

---

## 1. Why the mock makes user-testing *easier*, not harder

The app defaults to the **mock backend**: each tester's data lives in *their own browser's* `localStorage`
(key `nrn_mock_db`). That means:

- **No shared database, no server to host, no accounts to manage.** Nothing to set up per tester.
- **Every tester gets a private sandbox** — one person's actions can't affect or break another's run.
- **You can reset instantly** between testers with `localStorage.clear()`.
- **It exercises the *real* screens and interactions** — the mock mirrors the Flask contract exactly, so
  what a tester experiences (the flow, the wording, the layout) is exactly what the finished app does.

You only need the *real* backend when you want data to persist centrally across devices — a later goal, not
a testing blocker. **For testing the design and flow, the mock is enough.**

---

## 2. Three ways to get it in front of testers

Pick whichever suits each tester. (Reminder: the live app is **ES modules**, so it must be *served* — you
can't just email someone the `front-end/` folder to double-click. Way B solves that with the generated
classic bundle.)

| Way | How | Best for | Notes |
|---|---|---|---|
| **A. Same wi-fi (live)** | Run `task dev`. Find your Mac's IP: `ipconfig getifaddr en0`. Testers on the same network open `http://<your-ip>:5500/` | Classmates in the room with you | Your laptop must stay on and awake; served, so ES modules load fine |
| **B. Classic prototype (offline)** | `task web:prototype` → zip `README/prototype/` → send it → they **double-click `index.html`** | Anyone, anywhere, no setup, non-technical testers | It's the *generated* classic copy — regenerate after each change so it's current |
| **C. Deploy free (a real link)** | Push `front-end/` to **GitHub Pages** or **Netlify** (drag-and-drop the folder) → share the URL | Remote testers; a shareable link for your write-up | Served over https, so ES modules work; still mock data (no backend needed) |

**Recommendation:** use **B** for most testers (zero friction, works on any device offline) and **A** when
you're sitting next to them and want to watch. Use **C** if you want a link to cite in your internal.

---

## 3. Running a test session (and recording it)

A simple, repeatable script you can run with 3–5 people:

1. **Give a task, don't explain the app.** e.g. *"Sign up, add Biology with one topic, then log a review."*
   Give 3–4 short tasks total.
2. **Watch silently.** Note where they hesitate, misclick, or ask a question — those are your findings.
   (Resist helping; confusion *is* the data.)
3. **Ask two questions after:** "What was confusing?" and "What would you change?"
4. **Reset for the next tester:** open DevTools → Console → `localStorage.clear()` → refresh. Fresh sandbox.

### Feedback table (put this in your write-up)

| Tester | Task | Worked? | Where they got stuck / said | Change I made in response |
|---|---|---|---|---|
| P1 | Add a subject | Yes | "Wasn't sure the + button added a *subject* vs a topic" | Relabelled button to "+ Add subject" |
| P2 | Log a review | Partly | Didn't notice the confidence pills | Moved pills above the Save button, added a hint |
| … | … | … | … | … |

That "change I made in response" column is the **refinement / iterative-improvement** evidence examiners
look for — it shows testing actually drove your design.

---

## 4. Tips & gotchas

- **Stale cache:** if a tester sees an old version, have them **hard-refresh** (⌘⇧R / Ctrl-F5), or use an
  **Incognito** window for a guaranteed clean load.
- **`file://` won't run the live app:** double-clicking `front-end/index.html` shows a "please serve me"
  card (that's the serve-guard working, not a bug). Use **Way B** (the prototype) for double-click testing.
- **Screenshots as evidence:** capture the tester's screen at the moment of confusion, and an after-shot
  once you've fixed it — a before/after pair per finding is strong evidence.
- **Keep data realistic:** seed a couple of subjects/topics before a session so the dashboard isn't empty
  (an empty app is hard to react to). `localStorage.clear()` afterwards to reset.
- **Privacy:** the mock stores everything locally in the tester's browser — no personal data leaves their
  machine, which is worth noting in your internal's ethics/consideration section.
