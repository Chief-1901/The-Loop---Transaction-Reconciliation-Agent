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

## SCENE 1 — Show the Data, Then Run the Agent (3-5 min)

**Goal:** Show the actual CSV + JSON fixtures (the agent's input), then run the agent against them, then show what the agent produced. This is the most authentic version because you're literally showing what reviewers can `cat` themselves.

### Setup

- One terminal window, maximized
- Optionally: editor open in a separate window with `src/recon_agent/data/fixtures/tracking_db.csv` already loaded so you can flip to it

### Step 1 — Open the recording, briefly introduce

**Talking points (rephrase in YOUR words):**

- This is Recon Agent — your submission for GrabOn AI Labs Loop assignment
- Single autonomous agent that reconciles transactions across two data sources
- You'll show the inputs, run the agent live, show the outputs

Don't read this verbatim. 30-45 seconds in your own words is better.

### Step 2 — Show the input data (the CSV)

Type and run:

```powershell
Get-Content src\recon_agent\data\fixtures\tracking_db.csv -TotalCount 5
```

**Facts to mention while it's on screen:**

- This is the CSV from GrabOn's internal tracking DB — 500 transactions in the full file
- Each row: `txn_id`, `redemption_ts` (IST timezone with `+05:30`), `merchant`, `merchant_category`, `coupon_code`, `order_value_inr`, etc.
- Realistic GrabOn merchants: Amazon, Myntra, Ajio, Mamaearth, Swiggy, etc.
- This is one of the two data sources the agent will reconcile

### Step 3 — Show the other data source (the PayU API JSON)

```powershell
Get-Content src\recon_agent\data\fixtures\payu_settlements.json -TotalCount 20
```

**Facts to mention:**

- This is the mock PayU settlements API response — 490 settlement records
- Each record has `settlement_id`, `reference_id` (which matches CSV's `txn_id`), `settled_at` (UTC timezone), `payee`, `gross_amount`, etc.
- The agent's job: pair these two sources up and find discrepancies. Why the count differs (500 vs 490): the fixture generator deliberately injects ~10 "missing in API" defects.

### Step 4 — Run the agent with the dashboard

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario happy_02_minor_timezone --dashboard --slow-ms 800
Remove-Item Env:\LLM_MODE
```

**Facts to mention as the dashboard appears + updates:**

- Dashboard built with Rich (Python terminal library)
- This is **cassette replay** — same code path as a live run, but reads recorded LLM responses from `evals/cassettes/happy_02_minor_timezone.jsonl` instead of calling APIs
- The cassette was recorded from real OpenRouter + OpenAI calls during cassette day
- Top row: step counter, phase, tool count, LLM count, discrepancies found, corrections applied — all update live as the loop iterates
- Tool table fills in step-by-step: each row is a real ToolCallRecord with name, status, latency
- Budget bars in the middle: tokens / tool calls / cost — these are real consumed values
- "Last reasoning" at bottom: the LLM's actual decision text from the cassette
- The scenario name is `happy_02_minor_timezone` — focuses on timezone-shifted records (~25 of them)

### Step 5 — When PASS prints, point to it

**Facts to mention:**

- Status: completed, the eval verifier marked it PASS
- The verifier checks five things: status, findings count within tolerance, correction coverage, recovery flag, total cost
- All five passed → green checkmark in the CI gate

### Step 6 — Show what the agent produced

```powershell
# Show the latest run directory
Get-ChildItem reports\eval_* | Sort-Object LastWriteTime | Select-Object -Last 1
```

```powershell
# Show the corrections ledger the agent wrote
$latest = Get-ChildItem reports\eval_* | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content "$($latest.FullName)\happy_02_minor_timezone\corrections.jsonl" | Select-Object -First 3
```

**Facts to mention:**

- Each line in `corrections.jsonl` is one correction the agent proposed and applied
- Fields: `txn_id`, `kind` (timezone_shift / value_mismatch / etc), `field`, `old`, `new`, `reason`, `confidence`, `applied_at`, `step`, `action`
- This is append-only — the agent never mutates the source CSV or API records; everything goes through this ledger
- A reviewer can `git diff` two run directories to compare exactly what differed

### Step 7 — Wrap Scene 1

**Facts to mention:**

- Whole thing was reproducible — same input, same cassette, same output
- No API spend during this demo, but the cassette captures real LLM outputs from when we recorded it
- Next scene: what happens when something goes wrong

**End Scene 1 recording.** Save the take.

### Fallback (Approach B — if cassette replay flickers)

```powershell
.venv\Scripts\python scripts\_see_dashboard.py
```

Uses MagicMock router. Faster but less authentic. Adjust narration to say "the live agent shows this same dashboard; I'm driving it with a mock here to skip API latency."

---

## SCENE 2 — Show Failure + Recovery (3-5 min)

**Goal:** Show that the agent handles tool failures gracefully — retries, replans, doesn't crash. The `recovery_01_api_429` scenario was recorded against a 60% forced fetch_api failure rate, so the cassette has real failure-recovery behavior baked in.

### Setup

Same terminal as Scene 1. Clear: `cls`.

### Step 1 — Set up the scene

**Talking points (your own words):**

- This scenario is `recovery_01_api_429`
- `fetch_api` was forced to fail at 60% during recording — simulating PayU's sandbox returning 429s like the brief describes
- Cassette captured what the agent actually did across those failures

### Step 2 — Show the scenario spec briefly (proves it's real, not staged)

```powershell
Get-Content evals\scenarios\recovery_01_api_429.py
```

**Facts to mention:**

- `cli_env={"FETCH_API_FAIL_RATE": "0.6", "FETCH_API_RNG_SEED": "1"}` — that's how the failure was injected
- `expected.recovery_invoked=True` — the verifier asserts recovery actually fired
- `findings_by_kind` and `findings_tolerance` — what the agent is expected to find (with tolerance for LLM variance)

### Step 3 — Run with the dashboard

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --scenario recovery_01_api_429 --dashboard --slow-ms 600
Remove-Item Env:\LLM_MODE
```

**Facts to mention as the dashboard updates:**

- Watch the tool table — fetch_api rows will have ERR markers (red) when 429 hit
- Recovery dispatched: the classifier sees `transient RATE_LIMIT`, picks retry-with-backoff
- Retry might succeed (different RNG result) — table shows the recovered call as a fresh row
- After repeated failures: classifier escalates to replan, loop goes back to PLAN with a hint
- Eventually completes — the agent works around the unreliable API and still produces results

### Step 4 — When PASS prints, point to it

**Facts to mention:**

- Status: completed (or halted, depending on cassette specifics)
- Recovery invoked: yes — verifier confirmed it
- This is what the rubric means by "agent distinguishes error types and recovers"

### Step 5 — Show the structured log to prove every recovery decision was logged

```powershell
$latest = Get-ChildItem reports\eval_* | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content "$($latest.FullName)\recovery_01_api_429\log.jsonl" | Select-String "recovery.dispatched"
```

**Facts to mention:**

- Each line is one recovery decision: action (retry/replan/degrade), reason, hint
- This is what observability means in the rubric — every decision auditable
- A reviewer asking "at step N why did the agent X?" can grep this exact file

### Step 6 — Show the error→strategy table briefly

Switch to your editor (or `cat` the file):

```powershell
Get-Content docs\recovery_strategies.md | Select-Object -First 30
```

**Facts to mention:**

- This is the rule book — every error code mapped to a recovery strategy
- 404 (API_NOT_FOUND) is persistent → replan, no retry (the rubric explicitly tests this)
- 429 (RATE_LIMIT) is transient → retry with exponential backoff + jitter
- 401 (API_AUTH) is fatal → degrade immediately
- 3+ consecutive failures regardless of kind → degrade (the runaway guard)

**End Scene 2 recording.**

### Fallback (Approach B — forced-failure cascade for a dramatic degrade visual)

```powershell
.venv\Scripts\python scripts\loom_scene2_recovery.py
```

Forces 100% failure → guarantees the full retry → replan → degrade cascade. Use this if you specifically want the degrade path visible (real cassettes often recover before degrading). Be honest in narration: "I'm cranking the failure rate to 100% to show the full cascade in one demo."

---

## SCENE 3 — Architecture Walkthrough in Your Editor (4-6 min)

**Goal:** Prove you understand every layer. Open real files, talk about what's actually in them.

### Setup

Open VS Code (or your editor). Have these files in tabs ready:

1. `src/recon_agent/agent/loop.py`
2. `src/recon_agent/agent/phases.py`
3. `docs/architecture.md`
4. `docs/model_routing.md`
5. `docs/recovery_strategies.md`
6. `src/recon_agent/agent/budget.py`

Editor full-screen, file tree visible.

### What to actually do (not a script — a tour)

This is the scene where you talk in your OWN words. Below are the facts/talking-points for each file. Pick what feels natural, skip what doesn't. Aim for ~5 minutes total.

### File 1 — `src/recon_agent/agent/loop.py`

Scroll to `AgentLoop.run`. Talking points:

- ~70 lines total — the entire agent loop
- The `while not self.state.is_terminal()` pattern with named phases: Plan, Act, Observe, Decide
- Budget gate at the top of every iteration (before any LLM call)
- `self.state.apply()` is the single mutation point on the hot path
- `self.state.snapshot_to_disk()` writes a JSON snapshot per iteration — versioned state on disk
- Recovery is handled inside the loop but the recovery LOGIC lives in `src/recon_agent/recovery/`

### File 2 — `src/recon_agent/agent/phases.py`

- The four phase classes: `Plan`, `Act`, `Observe`, `Decide`
- Each has a `run(state)` method that returns a typed Pydantic output (`PlanOutput`, `ActOutput`, etc.)
- This is what "Plan/Act/Observe/Decide must be recognizable phases in code" means in the rubric — they're literally classes

### File 3 — `docs/architecture.md`

- Show the data flow diagram (the box-arrow ASCII)
- "Cassettes" + "ledger" + "snapshots" — three distinct outputs the agent produces

### File 4 — `docs/model_routing.md`

- Three providers in the routing table:
  - **OpenRouter `openai/gpt-oss-120b:free`** → plan / decide / propose / summary (free tier, ~200 req/day)
  - **OpenAI `gpt-4o-mini`** → classify (strict json_schema mode, paid)
  - **OpenAI `gpt-4o`** → shadow_plan (only when `--shadow` is set)
- Why these specifically: cost-conscious for high-volume; reliability-conscious for strict-schema classify
- Why NOT Gemini: free tier was 20 req/day — too tight; story in README §(f)
- `GEMINI_MODEL` and `PLAN_PROVIDER` env vars are runtime override levers

### File 5 — `docs/recovery_strategies.md`

- The error → strategy mapping table
- **404 (API_NOT_FOUND) is persistent** → replan immediately, no retry (the brief's "404 is not a rate limit" test)
- **429 (RATE_LIMIT) is transient** → retry with exponential backoff + jitter
- **401 (API_AUTH) is fatal** → degrade immediately
- **3+ consecutive failures** of any kind → degrade (the runaway guard)
- The backoff constants: MAX_RETRIES=3, BACKOFF_BASE_MS=1000, BACKOFF_MAX_MS=8000, JITTER=±30%

### File 6 — `src/recon_agent/agent/budget.py`

- The `Budget` Pydantic model: 5 ceilings
- The `check()` function returns a `Breach` object if any ceiling is exceeded (or `None`)
- AgentLoop calls `check()` at the top of every iteration before doing any expensive work
- On breach: writes `PARTIAL_REPORT.md` to the run dir, halts, exits code 2
- This is what makes "set max_tool_calls=3" terminate cleanly

### How to end Scene 3

Talking points to close:

- This is a single-agent system with no framework — raw SDK calls everywhere
- The whole thing is ~2,200 lines of Python in `src/recon_agent/`
- 86 unit + integration tests cover the contracts
- Every file you just saw is in the repo; reviewers can `cat` them themselves

**End Scene 3 recording.**

---

## SCENE 4 — Eval Suite + Cassettes (2-3 min)

**Goal:** Show that the full 12-scenario eval suite runs deterministically in seconds with zero API cost — the CI-gate proof.

### Setup

Switch back to terminal. Clear: `cls`.

### Step 1 — Set up the scene

**Talking points:**

- The eval suite is 12 scenarios — 5 happy / 3 recovery / 2 budget / 2 impossible
- All run in cassette replay → no API calls → free, deterministic, ~6 seconds
- This is what the GitHub Actions CI gate runs on every PR

### Step 2 — Run the full suite

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

**Facts to mention as scenarios print:**

- Each line: scenario name, PASS/FAIL marker, wall-clock seconds
- The runner generates fresh fixtures for each scenario (deterministic by seed)
- For each scenario the verifier checks 5 things: status matches expected, findings count within tolerance, correction coverage above threshold, recovery_invoked flag matches, cost under max

### Step 3 — Show the committed results artifact

```powershell
Get-Content evals\latest_eval_results.md
```

**Facts to mention:**

- This file is committed to git — the eval report artifact for submission
- Pass rate, status, findings, recovery flag, cost per scenario
- Cost column shows static per-tool cost estimates (real LLM cost in replay is exactly ₹0)

### Step 4 — Show the cassettes folder briefly

```powershell
Get-ChildItem evals\cassettes\
```

**Facts to mention:**

- 12 cassette files — one per scenario
- Each is a JSONL with every recorded LLM response from the original record session
- Total ~436K input + 27K output tokens captured across all 12
- Committed to git → reviewers can run `make eval` immediately, no API keys needed

### Step 5 — Show the CI workflow (optional, 30 sec)

```powershell
Get-Content .github\workflows\eval.yml
```

**Facts to mention:**

- The workflow runs `python -m evals.runner` in replay mode
- Compares against `evals/baselines/main.json` for regression detection
- Blocks PR merge if any scenario fails or regression detected
- Posts pass/fail summary as a PR comment

### Step 6 — Wrap

Talking points to close (your own words):

- Whole project: ~58 commits, 86 tests, 12/12 eval passing
- Setup is `make setup`, then add API keys, then `make eval` or `make demo`
- Full architecture + model routing + recovery strategies all documented in `docs/`
- Brainstorming log + design spec + this very recording guide are in the repo for reviewer transparency
- Thanks for watching

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
