# Loom Recording Day — Hands-On Guide

> Use this DURING recording. Keep it open in a window you can glance at. Every command + every "what to say" is below.

---

## ONE-TIME PREP (do this BEFORE you hit record)

### Tools you need installed

- **Loom desktop app** (https://www.loom.com/desktop) — free tier is fine
- **Windows Terminal** (Microsoft Store, free) — looks WAY better than cmd.exe for the dashboard
- Your editor — VS Code, Cursor, or whatever you usually use

### Verify everything works (5 min)

Open a PowerShell terminal in the project folder. Run these three commands in order:

```powershell
# 1. Dashboard demo (no API cost, ~15 sec) — proves Scene 1 will look good
.venv\Scripts\python scripts\_see_dashboard.py
```

You should see a cyan-bordered panel, 5 tool rows appear one by one, then summary. If colors look broken → use Windows Terminal instead of cmd.exe.

```powershell
# 2. Recovery demo (no API cost, ~12 sec) — proves Scene 2 will look good
.venv\Scripts\python scripts\loom_scene2_recovery.py
```

You should see: fetch_api keep failing in the table, then the agent halts with "graceful degrade: 3+ consecutive failures". 

```powershell
# 3. Full eval (cassette replay, no API cost, ~6 sec) — proves Scene 4
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

You should see `-- <scenario> ... PASS` for all 12 scenarios, ending with `Result: 12/12 PASS`.

If all three work cleanly, you're ready to record.

### Set up your screen ONCE before recording

1. **Increase terminal font size** to 18pt or larger (in Windows Terminal: Settings → Profile → Appearance → Font size). Reviewers will appreciate readable output.
2. **Maximize the terminal window** to roughly half your screen width. Leave the other half for the editor in Scene 3.
3. **Close** Slack, mail, browser notifications, anything that could pop up on screen.
4. **Test your mic** in Loom's preview. Speak at normal volume — Loom usually picks up well.

---

## SCENE 1 — Live Happy Path (3-5 min)

**Goal:** Show the agent's dashboard updating live as it walks through a successful reconciliation.

### Setup

- One terminal window, maximized
- Loom in "Screen + Mic" mode

### Commands + script

**Start recording**, then say:

> "Hi, I'm walking through Recon Agent — my submission for the GrabOn AI Labs Loop assignment. This is a single autonomous agent that reconciles transactions across two mock data sources. I'll show you the live agent loop first."

Type and run:

```powershell
.venv\Scripts\python scripts\_see_dashboard.py
```

**As the panel appears**, say:

> "The dashboard you're seeing is built with Rich — Python's terminal library. The cyan border, the budget bars, the tool-call table — all of it updates live as the agent runs. Top row shows current step, current phase, total tool calls so far."

**As tools appear in the table (~1.2 sec apart)**, narrate:

> "Step 1 — agent picks `load_csv`. Tool succeeds, OK marker appears. Step 2 — `fetch_api` fetches mock PayU settlements. Step 3 — `normalize_timezone` converts IST timestamps to UTC. Step 4 — `match_records` pairs up the CSV and API records. Step 5 — `verify_reconciliation` checks the final state."

> "Notice the budget bars filling as tokens accumulate. Notice the 'Last reasoning' line at the bottom updating each iteration. This is what an autonomous agent looks like when it's actually doing something."

**When the panel closes and the summary prints**, say:

> "Final status: completed. Five tool calls, ten LLM calls — five Plan + five Decide. Total cost is shown in rupees. The agent halted because the Decide phase returned HALT — the model decided reconciliation was complete. This whole run was deterministic — no real API calls, runs in about 12 seconds. The real version that hits the live LLM looks identical, just slower and costs about a rupee."

**End Scene 1 recording.** Stop recording, save the take.

---

## SCENE 2 — Failure Recovery (3-5 min)

**Goal:** Show that when a tool keeps failing, the agent recovers — retries, replans, and ultimately degrades cleanly instead of crashing or looping forever.

### Setup

Same terminal. Clear the screen first: `Clear-Host` (or `cls`).

### Commands + script

**Start recording**, then say:

> "Now the failure-recovery path. I'm going to force `fetch_api` to fail every single time — 100% failure rate. The agent will try, fail, retry with backoff, fail again, escalate, and eventually halt gracefully. The recovery layer handles this without crashing the loop."

Type and run:

```powershell
.venv\Scripts\python scripts\loom_scene2_recovery.py
```

**As `fetch_api` shows ERR in the table**, narrate:

> "First call to fetch_api — RATE_LIMIT error, marked ERR in red. The recovery classifier saw a transient error, dispatched a retry. Backoff kicks in — about a second of sleep — then the retry fires. Also fails."

> "After three retries on the same error code, the classifier escalates: 'this transient error is now persistent.' The recovery layer dispatches a REPLAN — the loop jumps back to PLAN with a hint to the next planner: 'fetch_api unreliable, consider alternative.'"

> "In this demo the mock planner stubbornly picks fetch_api again, so we get another failure. After three consecutive failures regardless of error type, the classifier short-circuits to DEGRADE. The agent halts cleanly with status 'graceful degrade'."

**When the panel closes**, point at the halt_reason line:

> "Halt reason: graceful degrade, 3+ consecutive failures. Not a crash. Not an infinite loop. The agent recognized the system was stuck and produced a partial report instead of pretending success."

**Then show the log file**, say:

> "Every recovery decision is logged structurally. Let me show you."

Run:

```powershell
type reports\_loom_scene2_recovery\log.jsonl | findstr recovery.dispatched | Select-Object -First 6
```

(If `findstr` and `Select-Object` mix weirdly, use this instead:)

```powershell
Get-Content reports\_loom_scene2_recovery\log.jsonl | Select-String "recovery.dispatched" | Select-Object -First 6
```

**As the lines appear**, say:

> "Each recovery dispatch is one JSON line — kind, reason, hint. A reviewer asking 'why did the agent give up at step 5' can grep this file and see the exact chain: retry, retry, retry, replan, replan, degrade. This is what the rubric means by 'observability shows every decision'."

**End Scene 2 recording.**

---

## SCENE 3 — Architecture Walkthrough (4-6 min)

**Goal:** Prove you understand every layer. Walk through the key files in your editor while explaining.

### Setup

Open VS Code (or your editor). Open these files in tabs:

1. `src/recon_agent/agent/loop.py`
2. `docs/architecture.md`
3. `docs/model_routing.md`
4. `docs/recovery_strategies.md`

Make the editor full-screen with the file tree visible on the left.

### Script

**Start recording**, then say:

> "Architecture walkthrough. The whole project is under `src/recon_agent/`. Seven subpackages: `agent` for the loop, `tools` for the eight typed tools, `llm` for the router and providers, `recovery` for the error-classifier and strategies, `observability` for the dashboard and structured logger, `data` for the fixture generator, and `cli` for the entry point."

**Open `loop.py`, scroll to `AgentLoop.run`**:

> "The loop is about 70 lines. While not terminal: budget gate, plan, act, observe, decide, snapshot. Each phase is a real class — Plan, Act, Observe, Decide — in `phases.py`. They each return typed Pydantic outputs, never raw dicts. State is versioned — every `apply` call bumps a counter and writes a JSON snapshot to disk. A reviewer can diff two snapshots and see exactly what one iteration changed."

**Switch to `docs/architecture.md`**:

> "The data flow looks like this." (read the ASCII diagram aloud, briefly)

**Switch to `docs/model_routing.md`**:

> "Three LLM providers used deliberately. OpenRouter with `openai/gpt-oss-120b:free` handles Plan, Decide, Propose, Summary — the high-volume reasoning calls. OpenAI's `gpt-4o-mini` handles Classify because OpenAI's strict json_schema mode is the most reliable for fixed-enum batch classification. OpenAI's `gpt-4o` is reserved for shadow comparison, only invoked when the `--shadow` flag is set."

> "We started on Gemini Flash but free-tier quota was 20 requests per day — too tight for cassette recording. We documented the migration story honestly in 'what broke first' in the README."

**Switch to `docs/recovery_strategies.md`**:

> "Recovery classifier maps every error code to a strategy. RATE_LIMIT — transient, retry with exponential backoff. API_NOT_FOUND, that's a 404 — persistent, no retry, replan immediately with a hint. API_AUTH — fatal, degrade immediately. Three consecutive failures regardless of kind — degrade. This table is the answer to 'a 404 is not a rate limit, the agent must distinguish.'"

**Open `src/recon_agent/agent/budget.py` briefly**:

> "Budget enforcement — five ceilings. Tokens, wall-clock, tool calls, consecutive failures, cost in rupees. Checked at the top of every loop iteration before any LLM call. Breach writes a PARTIAL_REPORT.md and exits with code 2. The 'set max_tool_calls=3 on a task that needs 15' stress test produces a clean halt every time."

**End Scene 3 recording.**

---

## SCENE 4 — Eval Run + Real Numbers (2-3 min)

**Goal:** Show the eval suite is real, fast, deterministic, and reviewer-verifiable.

### Setup

Switch back to the terminal. Clear it: `Clear-Host`.

### Commands + script

**Start recording**, then say:

> "The eval suite. Twelve scenarios — five happy path, three failure-recovery, two budget-exceeded, two impossible. All run in cassette-replay mode, no live API calls, runs in about six seconds total. This is what the GitHub Actions CI gate executes on every pull request."

Run:

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

**As the 12 scenarios print PASS one by one**, narrate:

> "Each line is one scenario — fixture generated deterministically, agent runs end-to-end, verifier checks five things: status, finding counts within tolerance, correction coverage, recovery invoked correctly, total cost under budget. Twelve out of twelve PASS."

**When it finishes**, type:

```powershell
type evals\latest_eval_results.md
```

**As the table appears**, say:

> "Same numbers, frozen as a submission artifact in `evals/latest_eval_results.md`. Pass rate, status per scenario, recovery flag, cost in rupees. Zero API spend in replay mode."

**Then briefly show the cassettes folder**:

```powershell
Get-ChildItem evals\cassettes\
```

> "Twelve cassette files, one per scenario. Each is a JSONL file with every recorded LLM response. Committed to the repo so reviewers can run `make eval` without any API keys at all."

**Closing 30 seconds**, say:

> "Repo's at github.com/[your-username]/recon-agent. Setup is `make setup`, add two API keys to .env, then `make eval` for the deterministic suite or `make demo` for a live run. Full architecture doc, model routing rationale, recovery strategies table — all in `docs/`. Design spec and brainstorming log in `docs/superpowers/`. Thanks for watching."

**End Scene 4 recording.**

---

## AFTER ALL FOUR SCENES

### Concatenate in Loom

Loom's editor lets you stitch multiple takes together. Open each take, drag them into one timeline in order: Scene 1 → Scene 2 → Scene 3 → Scene 4. Trim any dead air at the start/end of each scene. Export.

### Set sharing

- Click "Share" → check that "Anyone with the link can view" is selected (NOT "Only people I invite")
- Copy the share link

### Update README + push

```powershell
# Open README.md in your editor
# Find line: Demo walkthrough: `<LOOM_URL>`
# Replace <LOOM_URL> with the actual link you just copied

git add README.md
git commit -m "docs: add Loom walkthrough link"
git push
```

---

## COMMON GOTCHAS

**The dashboard looks garbled (no colors, weird characters)**

→ You're on cmd.exe. Switch to Windows Terminal or VS Code's integrated terminal.

**Loom captures the dashboard but the ANSI codes show as junk text**

→ Loom occasionally has trouble with terminal animations. Two fixes: (a) use Loom desktop app, not the browser extension. (b) If still bad, take a screenshot of the final dashboard frame and narrate over it instead of relying on the live animation.

**A script errors out mid-recording**

→ Stop recording. Run the script once to verify the error is real (not a transient terminal weirdness). If real, ping me in the next session — most likely a path or env-var issue. If just a transient, restart that scene.

**You stumble on a sentence**

→ Just keep going. Edit it out in Loom's editor afterward. Don't restart the whole scene unless the flub is dealbreaking.

**Mic sounds quiet/echoey**

→ Stop, redo Loom's audio test, use a different mic if available. Reviewers will watch the whole video; audio quality matters.

---

## TIME BUDGET

| Activity | Time |
|---|---|
| Pre-prep (verify scripts) | 5 min |
| Scene 1 recording | 4 min |
| Scene 2 recording | 4 min |
| Scene 3 recording | 5 min |
| Scene 4 recording | 3 min |
| Stitching + trimming in Loom | 15-30 min |
| Re-watch end-to-end | 16 min |
| Buffer for re-takes | 20 min |
| **Total** | **~75-90 min** |

You can absolutely do this in one focused 90-minute block.

---

## SCRIPT FILES THAT ARE READY

- `scripts/_see_dashboard.py` — Scene 1 (happy path, dashboard live)
- `scripts/loom_scene2_recovery.py` — Scene 2 (forced failure → recovery → degrade)
- `evals/latest_eval_results.md` — Scene 4 reference table
- `docs/architecture.md`, `docs/model_routing.md`, `docs/recovery_strategies.md` — Scene 3 reference files
- `LOOM_SCRIPT.md` — the originally-written more-detailed script (this LOOM_DAY.md is the simplified hands-on version)

You don't need to memorize a script — keep this `LOOM_DAY.md` open in a window you can glance at while recording. Read out the bolded "say" sections; the rest is your own narration.
