# Loom Recording Day — Hands-On Guide

> Use this DURING recording. Keep it open in a window you can glance at. Every command + every "what to say" is below.

---

## ONE-TIME PREP (do this BEFORE you hit record)

### Tools you need installed

- **Loom desktop app** (https://www.loom.com/desktop) — free tier is fine
- **Windows Terminal** (Microsoft Store, free) — looks WAY better than cmd.exe for the dashboard
- Your editor — VS Code, Cursor, or whatever you usually use

### Two recording approaches — PICK ONE

**Approach A (RECOMMENDED): Real cassette replay with dashboard.** Uses the actual recorded LLM responses from the 12 cassettes. Dashboard shows real provider/model names ("openrouter / openai/gpt-oss-120b:free"). 100% authentic — what reviewers will see when they `make eval` themselves.

**Approach B (fallback): MagicMock helper scripts.** Faster, simpler, doesn't depend on cassettes existing. Dashboard shows realistic-looking labels but it IS a mock. Use this if a cassette gets corrupted mid-record-day or you want a more controlled demo.

Both are documented below. Approach A is the right default — try it first.

### Verify Approach A works (5 min)

Open a PowerShell terminal in the project folder. Run these in order:

```powershell
# 1. Verify Scene 1 — real cassette replay with dashboard + slow-mo for readability
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario happy_02_minor_timezone --dashboard --slow-ms 800
Remove-Item Env:\LLM_MODE
```

You should see a cyan-bordered live panel. Tool rows fill in slowly (about one per second). Headers show real "openrouter" / "openai" provider names. Ends with PASS + run summary.

```powershell
# 2. Verify Scene 2 — recovery scenario with dashboard
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario recovery_01_api_429 --dashboard --slow-ms 600
Remove-Item Env:\LLM_MODE
```

You should see fetch_api fail multiple times (red ERR markers), recovery dispatched, more attempts, eventually the agent completes. Real cassette data.

```powershell
# 3. Verify Scene 4 — full eval suite (no dashboard, full speed for CI parity)
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

12/12 PASS in ~6 seconds.

### Verify Approach B works (only if Approach A flickers or breaks)

```powershell
.venv\Scripts\python scripts\_see_dashboard.py
.venv\Scripts\python scripts\loom_scene2_recovery.py
```

Both should run their 12-second dashboard demos cleanly. These use MagicMock under the hood.

If your chosen approach works cleanly, you're ready to record. If both look weird → cmd.exe vs Windows Terminal is the usual culprit.

### Set up your screen ONCE before recording

1. **Increase terminal font size** to 18pt or larger (in Windows Terminal: Settings → Profile → Appearance → Font size). Reviewers will appreciate readable output.
2. **Maximize the terminal window** to roughly half your screen width. Leave the other half for the editor in Scene 3.
3. **Close** Slack, mail, browser notifications, anything that could pop up on screen.
4. **Test your mic** in Loom's preview. Speak at normal volume — Loom usually picks up well.

---

## SCENE 1 — Happy Path with Dashboard (3-5 min)

**Goal:** Show the agent's dashboard updating live as it walks through a successful reconciliation using REAL recorded cassette data.

### Setup

- One terminal window, maximized
- Loom in "Screen + Mic" mode

### Commands + script (Approach A — recommended)

**Start recording**, then say:

> "Hi, I'm walking through Recon Agent — my submission for the GrabOn AI Labs Loop assignment. This is a single autonomous agent that reconciles transactions across two mock data sources. I'll show the live agent loop first, running against the `happy_02_minor_timezone` eval scenario using cassette replay — same data the CI gate runs, no API calls in the recording but the responses are the real LLM outputs we captured."

Type and run:

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario happy_02_minor_timezone --dashboard --slow-ms 800
Remove-Item Env:\LLM_MODE
```

**As the panel appears**, say:

> "The dashboard is built with Rich — Python's terminal library. Cyan border, budget bars, tool-call table — all updates live as the agent runs. Top row shows current step, current phase, tool count, LLM call count, discrepancies found, corrections applied."

**As tools appear in the table (~one per second with slow-mo)**, narrate:

> "Step 1 — `load_csv` pulls 500 transactions from the CSV fixture. Step 2 — `fetch_api` pulls the matching PayU settlement records. Step 3 — `normalize_timezone` converts IST timestamps to UTC and flags suspicious IST-stored-as-UTC values. Step 4 — `match_records` pairs them up. Step 5 — `classify_discrepancy` invokes the LLM to classify the unmatched. Step 6 — `propose_correction` proposes a fix for each. Step 7 — `apply_correction` appends to the corrections ledger. Final step — `verify_reconciliation` confirms."

> "Notice the budget bars filling. Notice 'Last reasoning' updating with the LLM's actual thought from the cassette. The provider/model columns show `openrouter` and `openai/gpt-oss-120b:free` — that's the real routing."

**When the panel closes and the PASS line prints**, say:

> "Status: completed. Verification: PASS. The eval runner just executed the same scenario the CI gate runs, with the dashboard visible. Same agent, same code, real recorded data."

**End Scene 1 recording.** Stop recording, save the take.

### Fallback (Approach B — if cassette replay flickers or hits issues)

```powershell
.venv\Scripts\python scripts\_see_dashboard.py
```

This uses a MagicMock router instead of cassettes. Faster, simpler, but the labels are synthetic. Only use if Approach A misbehaves on recording day. Adjust your narration to say "this is the dashboard the live agent shows; for this demo I'm driving it with a mock to skip API latency."

---

## SCENE 2 — Failure Recovery (3-5 min)

**Goal:** Show that when a tool keeps failing, the agent recovers — retries, replans, eventually degrades — instead of crashing or looping forever.

### Setup

Same terminal. Clear: `Clear-Host` (or `cls`).

### Commands + script (Approach A — recommended)

**Start recording**, then say:

> "Now the failure-recovery path. The `recovery_01_api_429` eval scenario forces `fetch_api` to fail at sixty percent — the runner records what the agent does when faced with a flaky downstream API. Cassette replay shows the exact recorded behavior."

Type and run:

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario recovery_01_api_429 --dashboard --slow-ms 600
Remove-Item Env:\LLM_MODE
```

**As `fetch_api` rows appear (some ERR, some OK)**, narrate:

> "fetch_api hits a RATE_LIMIT — red ERR marker. Recovery classifier sees a transient error, dispatches a retry with exponential backoff plus jitter. Retry fires. Some succeed, some keep failing."

> "After multiple failures on the same error code, the classifier escalates: 'this transient error is becoming persistent.' The recovery layer dispatches a REPLAN — the loop jumps back to PLAN with a hint baked into the next planner's context."

> "Agent eventually completes — finds the discrepancies, classifies them, applies corrections to the ledger. Real recorded behavior from a live run."

**When PASS prints**, say:

> "Status: completed. Recovery invoked: true. The eval verifier asserts both — the scenario passes only if recovery actually fired AND the agent reached a clean terminal state."

**Then show the structured log**, say:

> "Every recovery decision is logged. Here's the trail."

```powershell
Get-Content reports\eval_*\recovery_01_api_429\log.jsonl | Select-String "recovery.dispatched" | Select-Object -First 6
```

**As the lines appear**, say:

> "Each recovery dispatch is one JSON line: kind, reason, hint. A reviewer asking 'why did the agent retry at step 4' can grep this file. The rubric calls this 'observability shows every decision' — that's what these lines are."

**End Scene 2 recording.**

### Fallback (Approach B — synthetic recovery cascade if you want a controlled demo)

```powershell
.venv\Scripts\python scripts\loom_scene2_recovery.py
```

This forces 100% failure on fetch_api and walks the full retry → replan → degrade cascade explicitly. Use if you want to dramatize the degrade path. Real cassettes don't always trigger degrade because the recovery often succeeds before then.

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
