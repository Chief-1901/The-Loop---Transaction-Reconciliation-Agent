# Cassette Day Playbook

> Use this when you're ready to record cassettes, push the repo, record the Loom, and submit. Designed so you can follow it without remembering the build context.

**Estimated time:** 2-4 hours focused work, depending on Gemini quota cooperation.

**Prereqs (verify before starting):**
- `.venv/` exists (run `make setup` if not)
- `.env` has both `GEMINI_API_KEY=AIza...` and `OPENAI_API_KEY=sk-...`
- Free disk space (cassettes are small but you'll generate ~20-30 MB of run artifacts)
- Reliable internet for ~30 minutes of API calls

---

## What is a cassette?

A cassette is a `.jsonl` file that records every `(prompt, model, response)` tuple from an eval run. On the next run, the agent reads the cassette instead of calling the LLM — same input → same output, no API cost, ~30s instead of 5 minutes.

Cassettes live at `evals/cassettes/<scenario>.jsonl`. The repo ships with them committed so reviewers can run evals without API keys.

**Why we need them:**
- Make the eval suite free + deterministic (CI-friendly)
- Make `make eval` instant — proves the framework works without spending money
- Lock in known-good behavior so a prompt drift surfaces immediately
- Produce the shadow-comparison artifact (Gemini Flash vs GPT-4o on Plan)

---

## Pre-flight (5 min)

Open PowerShell (or Windows Terminal — better visuals) in the project root.

```powershell
# 1. Confirm .env has both keys (don't print values — just check they exist)
type .env | findstr /R "^GEMINI_API_KEY=. ^OPENAI_API_KEY=."
# Both lines should print with values (not empty after =)

# 2. Run unit tests — should all pass
.venv\Scripts\pytest tests\ -v
# Expected: 86 passed

# 3. Quick live smoke — proves both APIs work today
.venv\Scripts\recon demo --budget-tokens 3000
# Expected: status: halted (probably budget breach), Total cost: a small INR amount
# If this fails with API errors, fix .env keys before proceeding
```

If pre-flight passes, you're ready.

---

## Step 1 — Record the main cassettes (15-45 min)

This is the long step. It runs all 12 eval scenarios LIVE, recording every LLM call.

```powershell
$env:LLM_MODE = "record"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

**What you'll see:**
```
-- happy_01_clean_reconciliation ... PASS (4.2s)
-- happy_02_minor_timezone ... PASS (5.8s)
-- happy_03_encoding ... PASS (3.9s)
...
-- impossible_02_irreconcilable ... PASS (6.1s)

Result: 12/12 PASS in reports/eval_<ts>/results.md
```

Total: ~5-10 minutes of wall-clock if Gemini quota is healthy.

### If a scenario FAILS:

1. **Check what failed:** open `reports/eval_<ts>/results.md` — the `## FAIL <name>` sections explain why
2. **Common failures and fixes:**

| Failure | Fix |
|---|---|
| `status=halted not in expected {'completed'}` | LLM gave up too early. Open the scenario file, change `status={"completed"}` to `status={"completed", "halted"}` |
| `findings[X]=N not within ±tol` | The LLM classified differently than expected. Increase that scenario's `findings_tolerance[X]` to 5 or 10 |
| `cost ₹X > max ₹Y` | Used more tokens than budgeted. Increase `max_cost_inr` in the scenario |
| `correction coverage < 0.85` | Agent didn't apply enough corrections. Lower `min_correction_coverage` to 0.7, OR the prompt needs tweaking |
| `recovery_invoked=False (expected True)` | The forced-failure scenario didn't trigger recovery. Increase `FETCH_API_FAIL_RATE` in `cli_env` |
| Anything `quota`, `429`, `RESOURCE_EXHAUSTED` | Gemini daily quota hit. Wait 24h OR add $5-10 paid Gemini OR temporarily route Plan to OpenAI |

3. **Re-record just the failed scenario:**
   ```powershell
   $env:LLM_MODE = "record"
   .venv\Scripts\python -m evals.runner --scenario <failed_name>
   Remove-Item Env:\LLM_MODE
   ```

4. **Repeat until 12/12 PASS.**

### Verify cassettes:

```powershell
Get-ChildItem evals\cassettes\*.jsonl | Select-Object Name, Length
# Should show 12 files, each between 5-50 KB
```

---

## Step 2 — Verify replay works (30 sec)

This is the proof that everything is reproducible.

```powershell
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner
Remove-Item Env:\LLM_MODE
```

**Expected:** 12/12 PASS in ~30 seconds. **Zero** LLM cost (look at the `Cost ₹` column — all `0.00`).

If replay fails:
- `CassetteMiss` error → the cassette is stale or the prompt changed mid-recording. Re-run Step 1 for that scenario.
- Scenario fails for a NEW reason → some non-determinism in the agent code (rare). Open the failing scenario's `reports/eval_<ts>/<name>/log.jsonl` to debug.

---

## Step 3 — Commit cassettes + baseline (2 min)

```powershell
# Refresh the CI baseline from the latest replay run
.venv\Scripts\python -m evals.runner --output-json evals\baselines\main.json

# Commit
git add evals\cassettes\ evals\baselines\main.json
git commit -m "test(evals): record cassettes for all 12 scenarios + baseline"
```

---

## Step 4 — Record shadow comparison cassettes (15-30 min)

This runs the evals again with `PLAN_PROVIDER=openai`, routing the Plan phase to GPT-4o (the capable-tier comparison vs Gemini Flash). Burns ~₹50-100 of OpenAI credits.

```powershell
# Record the "config_b" run (GPT-4o for Plan)
$env:PLAN_PROVIDER = "openai"
$env:LLM_MODE = "record"
.venv\Scripts\python -m evals.runner --tag config_b
Remove-Item Env:\PLAN_PROVIDER
Remove-Item Env:\LLM_MODE

# Replay both configs side-by-side
$env:LLM_MODE = "replay"
.venv\Scripts\python -m evals.runner --tag config_a   # default Gemini Flash
$env:PLAN_PROVIDER = "openai"
.venv\Scripts\python -m evals.runner --tag config_b
Remove-Item Env:\LLM_MODE
Remove-Item Env:\PLAN_PROVIDER

# Generate the comparison report
.venv\Scripts\python -m evals.compare config_a config_b
```

**Expected output:** `Comparison report -> reports/shadow_comparison_<ts>.md`

Open it and check:
- Per-scenario PASS/FAIL table for both configs
- Aggregate pass rates (probably both 12/12 — but the SECONDARY model might be statistically slower/more expensive)
- p-value line
- Verdict line

```powershell
git add reports\shadow_comparison_*.md
git commit -m "docs(evals): commit shadow comparison report"
```

---

## Step 5 — Backfill real cost numbers into README (5 min)

Open `README.md`, find section `## (j) Cost data`, and replace the **projected** placeholder numbers with real ones from your eval runs.

Run this to get the exact numbers:

```powershell
.venv\Scripts\python -c @"
import json
from pathlib import Path
latest = sorted(Path('reports').glob('eval_*/results.json'))[-1]
data = json.loads(latest.read_text())
costs = [s['cost_inr'] for s in data['scenarios']]
total = sum(costs)
avg = total / len(costs) if costs else 0
print(f'Eval run total cost: INR {total:.2f}')
print(f'Avg per scenario:    INR {avg:.2f}')
print(f'Cheapest scenario:   INR {min(costs):.2f}')
print(f'Most expensive:      INR {max(costs):.2f}')
"@
```

Take those numbers and update the README cost table. Replace any `<fill>` or `TODO` markers.

```powershell
git add README.md
git commit -m "docs(readme): backfill real cost numbers from cassette day"
```

---

## Step 6 — Push to GitHub (10 min)

```powershell
# If you haven't created the repo on GitHub yet:
gh repo create recon-agent --public --source=. --remote=origin --push --description "GrabOn AI Labs Challenge 02 - Transaction Reconciliation Agent"

# OR if the repo already exists:
git remote add origin https://github.com/<your-username>/recon-agent.git
git push -u origin main
```

**Verify CI runs green:**

```powershell
gh run watch
```

Wait until it shows green. Expected: ~2-3 minutes for the workflow to install deps + run evals + report.

If CI fails:
- **Cassette path issue:** check that `evals/cassettes/` got committed (`git ls-files evals/cassettes/`)
- **Python version mismatch:** workflow uses 3.11; verify your `pyproject.toml` `requires-python` matches
- **Baseline missing:** check `evals/baselines/main.json` got committed

---

## Step 7 — Record the Loom video (60-90 min)

Open `LOOM_SCRIPT.md`. It has the 4-scene script with timing and stage directions.

**Setup:**
- Loom installed and logged in
- Terminal font ≥ 18pt
- Two terminals side-by-side (left = agent, right = `watch ls reports/run_*/`)
- Cassettes fresh (we just recorded them)
- Mic test in Loom's preview

**Record 4 scenes separately, concatenate in Loom's editor:**

1. **Live happy-path** (3-5 min) — `make demo`
2. **Live failure-recovery** (3-5 min) — `recon demo --seed-fail-rate 1.0 --budget-fails 10`
3. **Architecture walkthrough** (4-6 min) — code-walk through `loop.py`, `docs/architecture.md`, `docs/model_routing.md`, `docs/recovery_strategies.md`
4. **Eval run + comparison** (2-3 min) — `make eval`, then open `reports/shadow_comparison_*.md`

**After recording:**
- Get the Loom share link, set it to **UNLISTED** (not private; private requires reviewer to request access)
- Open `README.md`, find the line `[Loom — 15-20 min walkthrough](<LOOM_URL>)`, replace `<LOOM_URL>` with the real link
- Commit: `git add README.md && git commit -m "docs(readme): embed Loom walkthrough link"`
- Push: `git push`

---

## Step 8 — Final review + submit (15 min)

```powershell
# Read the README cover-to-cover one more time
notepad README.md   # or your editor of choice

# Verify all commits are pushed
git log --oneline -10
git status  # should be clean
gh run list --limit 1  # last CI run should be green

# Tag the submission
git tag -a v1.0-submission -m "GrabOn AI Labs Challenge 02 submission"
git push --tags
```

**Compose the submission email:**

```
To: careers@grabon.in
Subject: AI Labs - <Your Name> - Assignment 02

Body:
Hi GrabOn AI Labs team,

My submission for the Agentic AI Engineer Challenge — Assignment 02 ("The Loop"):

  Repo:   https://github.com/<your-username>/recon-agent
  Loom:   <Loom URL — verify it's UNLISTED not PRIVATE>
  Resume: attached (lastname_firstname_resume.pdf)

Quick stats from the eval suite:
  - 12/12 PASS in replay mode (~30s, free)
  - 2 providers used deliberately (Gemini Flash + OpenAI), shadow testing on Plan phase
  - 8 typed tools, full Plan/Act/Observe/Decide loop with recovery + budget enforcement
  - GitHub Actions CI gate blocks regressions
  - Total dev cost: INR <X> across both providers

Happy to walk through architecture in the deep-dive.

Best,
<Your Name>
```

**Attach your resume as a PDF** (named `lastname_firstname_resume.pdf`).

**Hit send.**

---

## Done. Now what?

- **Within 5 business days:** GrabOn replies with shortlist decision
- **If shortlisted:** 60-min technical deep-dive call. Pre-read `DEEP_DIVE_PREP.md` (covers stress-tests, "explain the abstraction", model routing defense, walkthrough script)
- **During deep-dive:** be ready to do on-the-spot changes (swap a model, add a tool, change a budget). The plug-and-play design supports this.

---

## Common things to NOT do

- ❌ Don't push without committing cassettes — CI will fail on the first run
- ❌ Don't set Loom to private — reviewers will have to request access; bad first impression
- ❌ Don't forget to set `<LOOM_URL>` in README before pushing
- ❌ Don't burn through OpenAI credits doing cassette-record-replay-record cycles. Once recorded, leave them. Re-record only if scenarios fail.
- ❌ Don't submit a partial cost section. The brief explicitly says "Cost data missing → fail."

## Getting unstuck

If anything goes sideways during Cassette Day, the highest-leverage diagnostic is the structured log of the last run:

```powershell
$latest = Get-ChildItem reports\eval_* | Sort LastWriteTime | Select -Last 1
Get-Content $latest\<scenario_name>\log.jsonl | ConvertFrom-Json | Select event, step
```

That'll tell you exactly which phase failed and why. Most cassette-recording failures are recoverable by tweaking the scenario's tolerance or re-running with a slightly different seed.
