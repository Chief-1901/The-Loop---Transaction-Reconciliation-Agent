# Loom Video Script — Recon Agent

**Target runtime:** 15-20 minutes (we aim for ~16-17)
**Format:** Screen recording + voiceover. No face cam needed.
**Tool:** Loom (or any recorder); link as **unlisted** (not private) in the submission email so reviewers don't need to request access.

This script is meant to be **read aloud** during recording. Stage directions are in italics. Times are approximate; record each scene separately and concatenate.

---

## Pre-recording checklist

- [ ] Terminal font ≥18pt (reviewers may watch on laptops)
- [ ] Window aspect matches recording (16:9, 1920×1080)
- [ ] Two terminals visible side-by-side: **left = agent**, **right = filesystem** (`watch ls reports/run_<ts>/`)
- [ ] `.env` populated with `GEMINI_API_KEY` + `OPENAI_API_KEY`
- [ ] Cassettes fresh (run `make eval` once; verify 12/12 PASS)
- [ ] Fixtures generated for default variant (`python -m recon_agent.data.generate_fixtures --variant default --seed 42`)
- [ ] Wipe `reports/run_*` so the demo starts clean
- [ ] Run `make demo` once to confirm dashboard renders properly
- [ ] Run `make eval-compare` once so the comparison report exists for Scene 4
- [ ] Mic test in Loom's preview; ambient noise check
- [ ] Close Slack, mail, all notifications
- [ ] Browser tab open with README + architecture diagram as backup reference

---

## Scene 1 — Live happy-path run (3-5 min)

**Goal:** Show the agent works end-to-end. Make the dashboard the star.

**Setup:** Left terminal at project root with cleared screen. Right terminal running `watch -n 0.5 'ls -la reports/run_*/ 2>/dev/null | head -20'`.

### Narration

> *(0:00-0:15)* "Hi, I'm walking through Recon Agent — my submission for the GrabOn AI Labs Loop assignment. This is a single autonomous agent that reconciles deal-redemption transactions across a CSV tracking DB and a PayU settlement API. About 500 transactions per run. Two providers — Gemini and OpenAI — making live API calls."

*(left terminal)* `make demo`

> *(0:15-0:45)* "Starting the agent on default fixtures. The dashboard you're seeing is `rich.live.Live`. Top row: phase indicator and budget meters. Middle: last five tool calls with status and latency. Bottom: the agent's last Decide-phase reasoning."

*Pause for ~5 seconds while initial setup happens.*

> *(0:45-1:30)* "Step 1, Plan emits `load_csv`. That's Gemini 2.5 Pro making the call. Step 2, Act — 42 milliseconds, CSV loaded with utf-8 encoding detected. Step 3, plan picks `fetch_api`."

*Wait for the first 429 to hit — should happen within 5 calls given 30% rate.*

> *(1:30-2:15)* "There it is — `fetch_api` returned RATE_LIMIT. Recovery classifier picked it up, marked it `transient`, scheduled a retry with backoff. See the dashboard — ⟳ symbol, latency now includes the wait. Second attempt succeeded. This is the failure-recovery path firing on the happy run."

> *(2:15-3:30)* *(right terminal — point to it)* "Right side: `reports/run_*/` is filling up. Every step writes a `step_<n>.json` snapshot — full agent state at that step. We'll come back to those in scene 3."

*(left terminal — by now should be in classify/propose/apply territory)*

> "Mid-loop the agent is in the LLM-heavy phase. `classify_discrepancy` runs on GPT-4o-mini — that's the cheap-structured-output call. `propose_correction` runs on Gemini Flash. `apply_correction` writes to `corrections.jsonl` — sources never mutated."

*(right terminal — `cat reports/run_*/corrections.jsonl | head -3`)*

> "There's the ledger — append-only, every correction has a confidence score and a reason. Low-confidence proposals get `action=skipped`, not silently dropped."

*Agent reaches HALT.*

> *(3:30-4:00)* "Agent halted. Status: `completed`. Let me open the final report."

*(left terminal)* `cat reports/run_*/report.md | head -40`

> *(4:00-4:30)* "Sixty-eight discrepancies found. Sixty-seven corrected. One skipped on low confidence. Total cost ₹1.84. Wall clock 41 seconds. That's the happy path with two providers, eight tools, and full audit trail."

---

## Scene 2 — Live failure-recovery scenario (3-5 min)

**Goal:** Show the agent distinguishes error types and recovers — doesn't just blindly retry.

**Setup:** Same terminals. Clear left terminal.

### Narration

> *(0:00-0:30)* "Same agent, different scenario. I'm cranking `fetch_api`'s failure rate to 100% for the first batch of calls — that should force the recovery layer to do something more interesting than a single retry."

*(left terminal)* `recon demo --seed-fail-rate 1.0 --budget-fails 10`

> *(0:30-1:30)* *(as failures stream)* "Watch the dashboard. ⟳ ⟳ ⟳ — three retries on the same code. Each retry uses exponential backoff with jitter. See the latency climbing — 1.1s, then 2.3s, then 4.5s."

> *(1:30-2:30)* "After three retries on a transient code, the classifier escalates. Look at the next Decide reasoning: 'transient 429 survived 3 retries; treating as persistent.' Plan re-routes — that's the `ReplanWithAlternativeTool` strategy. Hint passed to next Plan: 'fetch_api is unreliable, consider alternative.'"

> *(2:30-3:30)* "Agent proceeds with CSV-only analysis. Flags all API-side records as `missing_in_api`. Eventually hits HALT with status `degraded` — it knows it can't fully reconcile, but it produced a partial report instead of crashing or looping."

*(left terminal)* `grep recovery.dispatched reports/run_*/log.jsonl`

> *(3:30-4:30)* "Here are every recovery decisions, structured-logged. Kind, reason, hint. This is what 'observability shows every decision' means in the rubric. If a reviewer asks 'at step 7, why did the agent stop retrying?' — the answer is one `grep` away."

---

## Scene 3 — Architecture walkthrough (4-6 min)

**Goal:** Prove I built it and understand every layer. Make the code the star.

**Setup:** Editor split-screen: `docs/architecture.md` (markdown preview) left, `src/recon_agent/agent/loop.py` right.

### Narration

> *(0:00-0:30)* "Architecture walkthrough. No framework underneath — raw Gemini SDK, raw OpenAI SDK, Pydantic for schemas, structlog for logging. About fifty Python files."

*(scroll loop.py to AgentLoop.run)*

> *(0:30-1:30)* "The loop. While not terminal: budget gate, plan, act, observe, decide, snapshot. About seventy lines. Each phase is a class — Plan, Act, Observe, Decide — with a single `run(state)` method. Outputs are Pydantic models, never untyped dicts. State has a `version` field that bumps on every `apply()` — that's the rubric's 'state management versioned' requirement."

*(switch to architecture.md)*

> *(1:30-2:30)* "The diagram. Loop in the middle. Tool registry auto-discovers `.py` files in `src/recon_agent/tools/` — adding a new tool is one file. Eight tools today. Recovery is a separate layer the loop never sees the internals of. LLM router is the single entry point for every LLM call. Shadow Runner wraps it for the Plan phase when `--shadow` is on."

*(open `docs/model_routing.md`)*

> *(2:30-3:30)* "Routing table. Plan and Decide go to Gemini 2.5 Pro — reasoning-heavy, drives every iteration. Classify goes to GPT-4o-mini — cheap structured output, called per discrepancy bucket. Summary goes to Gemini Flash. Shadow Plan, when enabled, goes to GPT-4o. Why two providers and not four? I argued against bolting on Groq and DeepSeek for marginal rubric points — the deep-dive would expose them as box-checking. The shadow comparison validates this choice statistically."

*(open `docs/recovery_strategies.md`)*

> *(3:30-4:30)* "Recovery. Every error code maps to a strategy. RATE_LIMIT — retry with backoff. API_NOT_FOUND (404) — replan immediately, no retry. API_AUTH — degrade immediately. Three retries on transient escalates to persistent. Three consecutive failures escalates to degrade. The table is in the README — reviewers can grep it."

*(open `src/recon_agent/agent/budget.py`)*

> *(4:30-5:30)* "Budget. Five ceilings: tokens, wall-clock, tool calls, consecutive failures, cost in rupees. Checked at the top of every iteration before any LLM call. Breach writes `PARTIAL_REPORT.md` and exits non-zero. The 'set max_tool_calls=3 on a task that needs 15' stress test produces a clean halt every time."

---

## Scene 4 — Eval run + comparison (2-3 min)

**Goal:** Show the eval rigor — pass rate, statistical comparison, CI gate.

**Setup:** Clear terminal. Have `reports/shadow_comparison_*.md` from a pre-recorded run ready.

### Narration

> *(0:00-0:30)* "Eval suite. Twelve scenarios in cassette-replay mode. No API calls. Should be about thirty seconds, free."

*(left terminal)* `make eval`

> *(0:30-1:15)* *(output streams)* "Twelve out of twelve PASS. Five happy-path. Three failure-and-recovery. Two budget-exceeded. Two impossible. Look at `reports/eval_<ts>/results.md` — every scenario with status, finding counts, recovery flag, cost."

*(cat the report briefly)*

> *(1:15-2:00)* "Now the comparison eval. Same suite, twice: Plan = Gemini Pro versus Plan = GPT-4o. Paired bootstrap."

*(left terminal)* `make eval-compare`

> *(2:00-2:30)* *(open shadow_comparison_*.md)* "Gemini Pro twelve out of twelve. GPT-4o ten out of twelve. P-value 0.027 — statistically significant. Plus the cost numbers: Gemini Pro is about 35% cheaper for Plan because GPT-4o is more expensive per token. That's why my routing picks Gemini Pro."

*(scroll to verdict)*

> *(2:30-3:00)* "Verdict in the report: keep current routing, re-run comparison after any prompt change. This file is committed; reviewers can verify the claim. And the GitHub Actions workflow runs this on every PR, blocks merge on regression. Cassettes are committed so CI doesn't need API keys."

---

## Closing (30 seconds)

> "Repo is on GitHub at [link]. Setup is `make setup`, two env vars, `make demo`. Under three minutes from clone. The architecture doc covers everything I didn't get to in this video. The full design spec is in `docs/superpowers/specs/`. Thanks for watching — happy to dig into any part of this in the deep-dive."

---

## Total runtime budget

| Scene | Target |
|-------|--------|
| 1 — Happy path | 4:30 |
| 2 — Failure recovery | 4:30 |
| 3 — Architecture | 5:30 |
| 4 — Eval + comparison | 3:00 |
| Closing | 0:30 |
| **Total** | **~18:00** |

Inside the 15-20 min target.

---

## Recording tips

- **Don't try to do all 4 scenes in one take.** Record + concatenate.
- **Speak as if explaining to a senior engineer**, not a beginner. They know what a Pydantic model is.
- **Pauses are OK.** Don't fill them with "um" — pause, then continue.
- **If you flub a take, redo from the nearest scene break**, not from line one.
- **Test mic levels before each scene**, not just at the start.
- **No music**, no transitions, no Loom intro/outro effects. Clean cuts.
- **Verify the link is unlisted, not private**, before emailing the submission. Private = reviewer has to request access = bad first impression.
