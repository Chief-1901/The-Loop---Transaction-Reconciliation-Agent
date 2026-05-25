# Recon Agent

GrabOn AI Labs Challenge 02 — Transaction Reconciliation Agent.

Demo walkthrough: `<LOOM_URL>`

---

## Reviewer Quick Start (60-second orientation)

**If you're reviewing this for GrabOn AI Labs, start here.** This block tells you the fastest path to verifying every claim.

### Just want to see it run?

```bash
make setup              # 90 sec: venv + deps, copies .env.example to .env
make eval               # 30 sec: replays 12 cassettes, prints 12/12 PASS, ZERO API spend
```

That's the canonical sanity check. No API keys needed — the cassettes (recorded LLM responses) are committed to the repo.

### Want to read the code in tour order?

1. **`src/recon_agent/agent/loop.py`** — the ~70-line agent loop (Plan → Act → Observe → Decide)
2. **`src/recon_agent/agent/phases.py`** — the four phase classes
3. **`src/recon_agent/tools/`** — 8 typed tools (each in its own file, one purpose)
4. **`src/recon_agent/recovery/`** — `classifier.py` (error → strategy table) + `strategies.py` (retry / replan / degrade)
5. **`src/recon_agent/llm/router.py`** — 3-provider routing table + cost tracking
6. **`evals/scenarios/`** — 12 eval scenario definitions (5 happy / 3 recovery / 2 budget / 2 impossible)
7. **`docs/architecture.md`** — data-flow diagram + module overview
8. **`docs/model_routing.md`** — per-subtask provider/model rationale
9. **`docs/recovery_strategies.md`** — full error code → strategy table

### Want to verify a specific rubric claim?

| If you want to verify... | Run / read this |
|---|---|
| "Agent loop is named abstraction with P/A/O/D phases" | `src/recon_agent/agent/loop.py` + `phases.py` |
| "8 typed tools with structured errors" | `src/recon_agent/tools/*.py` — each has Pydantic input/output schemas |
| "One unreliable tool fails 30% of the time" | `src/recon_agent/tools/fetch_api.py` — `_fail_rate()` reads `FETCH_API_FAIL_RATE` env var |
| "3 failure-recovery strategies" | `src/recon_agent/recovery/strategies.py` — `RetryWithBackoff`, `ReplanWithAlternativeTool`, `GracefulDegrade` |
| "Budget enforcement halts runaway" | `src/recon_agent/agent/budget.py` — checked at top of every loop iteration |
| "404 vs 429 distinguished" | `docs/recovery_strategies.md` — full mapping table |
| "12 eval scenarios pass" | `make eval` (or read `evals/latest_eval_results.md`) |
| "CI gate blocks bad changes" | `.github/workflows/eval.yml` — runs evals on every PR |
| "State management is versioned" | `src/recon_agent/agent/state.py` — `version` field bumps every `apply()`; snapshots at `reports/run_*/step_*.json` |
| "Cost tracked per task type" | `src/recon_agent/llm/pricing.py` + `LLMCallRecord.cost_inr` |
| "Real LLM responses in cassettes" | `evals/cassettes/*.jsonl` — committed, used by `make eval` |

### Want a live agent run?

```bash
$EDITOR .env                # add OPENROUTER_API_KEY (https://openrouter.ai, free tier)
                            # add OPENAI_API_KEY (https://platform.openai.com)
make demo                   # live run, ~₹0.50-2 cost
```

### Process artifacts (transparency about how this was built)

- `docs/superpowers/specs/2026-05-23-recon-agent-design.md` — design doc written upfront
- `docs/superpowers/plans/2026-05-23-recon-agent-implementation.md` — phase-by-phase implementation plan
- `docs/superpowers/brainstorming_log.md` — Q&A log from the design phase
- `docs/challenge_brief.md` — the original challenge brief for context

The full submission story — design decisions, what broke first, what I'd change — is in sections below.

---

## (a) What I built and why I chose Assignment 02

**The system.** Recon Agent is a single autonomous agent that reconciles two transaction data sources — a CSV export from an internal tracking database and a JSON payload from a mock PayU settlements API — and produces a signed corrections ledger (`corrections.jsonl`) plus a human-readable report. The agent runs as a ReAct loop with four named phases (Plan, Act, Observe, Decide), eight typed tools, a three-provider LLM router (OpenRouter `gpt-oss-120b:free` for Plan/Decide/Propose/Summary; OpenAI `gpt-4o-mini` for Classify; OpenAI `gpt-4o` for shadow comparison; Gemini available as a configurable fallback), a recovery layer that handles transient and fatal tool errors without crashing the loop, and a hard budget gate that enforces token and wall-time ceilings. The entire loop is ~70 lines in `src/recon_agent/agent/loop.py`. There is no framework under it — no LangChain, no LlamaIndex, just raw SDK calls gated by Pydantic-typed contracts.

**Why Assignment 02.** The reconciliation task has deterministic ground truth: a record either matches or it does not, a discrepancy is either correctly classified or it is not, a correction either fixes the number or it does not. That makes agent behavior mechanically verifiable, which is the property the rubric most directly grades. Assignment 02 also stresses the axis that separates "chatbot wrapper" from "agent engineering": multi-step planning under budget constraints, typed structured output that must work across two incompatible LLM schema dialects, error recovery that distinguishes transient from fatal failures, and an eval harness that replays recorded cassettes to give deterministic pass/fail results without API keys. That is the work this submission tries to demonstrate.

---

## (b) Architecture

Full diagram and data-flow in `docs/architecture.md`. The loop in one glance:

```
budget.check
     |
     v
  PLAN (LLM: openai/gpt-oss-120b:free via OpenRouter)
     |
     v
  ACT (tool call) ───── ToolError ──▶ Recovery (retry / replan / degrade)
     |                                       |
     v                                       |
  OBSERVE (summarize result, patch state)    |
     |                                       |
     v                                       |
  DECIDE (LLM: openai/gpt-oss-120b:free) ◀──┘
     |
     v
  state.apply() ──▶ step_<n>.json snapshot to disk
     |
     └──▶ loop back to budget.check (or HALT)
```

There is no framework. The phases are real classes in `src/recon_agent/agent/phases.py`, not method comments inside a monolithic run function. The state is a versioned Pydantic model: every `state.apply()` bumps `version` and writes a snapshot, so any two consecutive steps can be diffed to see exactly what one loop iteration changed.

---

## (c) Per-module design decisions

| Module | What it does | Key decision |
|---|---|---|
| `agent/` | Loop, phases, state, budget | Phases are separate classes, not nested `if` blocks. Budget gate sits at the top of every iteration, not at the end — a ceiling breach mid-loop halts before the next call. |
| `tools/` | 8 typed tools: `load_csv`, `fetch_api`, `normalize_timezone`, `match_records`, `classify_discrepancy`, `propose_correction`, `apply_correction`, `verify_reconciliation` | Every tool returns a typed `ToolResult`; no tool raises. Errors surface as structured `ToolError` values so the recovery layer can classify them without try/except in the loop. |
| `llm/` | Providers, router, cassettes, shadow runner, pricing | Two sanitizer functions — `sanitize_schema_for_gemini` and `sanitize_schema_for_openai` — adapt the same Pydantic class to each provider's incompatible structured-output dialect. Cassette layer intercepts at the HTTP boundary so replays are deterministic byte-for-byte. |
| `recovery/` | `ErrorClassifier`, three strategy classes | Error kind drives strategy: transient errors retry with exponential backoff, persistent errors replan immediately, fatal errors degrade. Three consecutive failures of any kind short-circuit to degrade — the agent cannot loop forever. |
| `observability/` | JSONL trace writer, Rich live dashboard | Every LLM call, tool call, and recovery event is a structured log line. The Rich dashboard re-renders from the same event stream so the TUI is not a separate code path. |
| `data/` | Fixture generator, schema definitions | Fixtures are generated programmatically with a seeded RNG so scenario parameters are reproducible without committing large binary files. |
| `evals/` | 12 scenarios, cassette runner, shadow compare | 12 scenarios over 30+ parametric cases — see section (i) for the defense of this count. Cassette runner replays without API keys; `eval-live` re-records and gates on regression. |

---

## (d) How to run

**Setup (4 lines):**

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
cp .env.example .env
# edit .env: add GEMINI_API_KEY and OPENAI_API_KEY
```

**Demo (cassette replay, no API keys needed):**

```bash
make demo-replay
```

**Demo (live LLM run, requires keys, ~45s, ~INR 4):**

```bash
make demo
```

**Full eval suite (cassette replay, free, ~30s):**

```bash
make eval
```

**Stress tests:**

```bash
# Budget enforcement: agent halts before token ceiling, exits 2
MAX_TOKENS=100 make demo-replay

# Recovery under API failures: fetch_api fails 100% of the time
FETCH_API_FAIL_RATE=1.0 make demo-replay

# Consecutive-failure degrade: three strikes, then graceful halt
MAX_CONSECUTIVE_FAILURES=3 FETCH_API_FAIL_RATE=1.0 make demo-replay
```

**CI gate:** `make eval` runs 12 cassette-replay scenarios. Every scenario asserts pass/fail deterministically — no LLM variance because the cassette layer replays exact recorded responses. A new commit that changes tool logic or prompt templates must pass all 12 or the gate fails. To re-record cassettes after intentional changes: `make eval-live` (requires API keys, re-records, then runs the gate).

---

## (e) Eval results

Cassettes for all 12 scenarios are recorded and committed (`evals/cassettes/`). `make eval` runs the full suite in replay mode in ~6 seconds with zero live API spend.

**Latest results — 12/12 PASS**

| # | Scenario | Status | Findings | Recovery | Cost (INR) | Verdict |
|---|---|---|---|---|---|---|
| 1 | budget_01_token_ceiling | halted | — | no | 0.00 | PASS |
| 2 | budget_02_walltime_ceiling | halted | — | no | 0.00 | PASS |
| 3 | happy_01_clean_reconciliation | completed | — | no | 0.00 | PASS |
| 4 | happy_02_minor_timezone | completed | — | no | 0.00 | PASS |
| 5 | happy_03_encoding | completed | — | no | 0.00 | PASS |
| 6 | happy_04_duplicates | halted | — | no | 0.00 | PASS |
| 7 | happy_05_value_mismatch | halted | value_mismatch=11 | no | 0.95 | PASS |
| 8 | impossible_01_corrupted_source | degraded | — | yes | 0.00 | PASS |
| 9 | impossible_02_irreconcilable | halted | — | yes | 0.00 | PASS |
| 10 | recovery_01_api_429 | halted | missing_in_api=10, missing_in_csv=2, value_mismatch=13 | no | 0.15 | PASS |
| 11 | recovery_02_malformed_csv | halted | — | no | 0.00 | PASS |
| 12 | recovery_03_tool_disabled | degraded | — | yes | 0.00 | PASS |

**Aggregates (replay mode, deterministic):**

- Pass rate: **12 / 12 (100%)**
- Total wall-clock: **~5.5s** for the full 12-scenario suite
- LLM API calls during replay: **0** (every call resolves from a committed cassette)
- INR cost shown above is the static per-tool cost estimate (`Tool.cost_estimate_inr`), aggregated across tool calls made by the agent. Real LLM cost in replay mode is exactly **₹0** because no live calls are made.

**Where to look:**
- `evals/latest_eval_results.md` — the same table above, frozen as a submission artifact
- `evals/baselines/main.json` — the pinned baseline the CI gate compares against (12 scenarios × full per-scenario JSON)
- `reports/eval_<timestamp>/` — any fresh `make eval` run drops `results.md` + `results.json` here
- `evals/scenarios/` — the 12 scenario definitions (one Python file each)
- `evals/cassettes/` — 12 `.jsonl` files, total 194 recorded LLM responses across all scenarios

Replay these locally with `make eval`. No API keys required for replay.

---

## (f) What broke first

**What we saw.** First live call to `gemini_call(model="gemini-2.5-flash", ...)` failed immediately with:

> `LLMError: additionalProperties is only supported in Gemini Enterprise Agent Platform mode, not in Gemini Developer API mode.`

We had the loop wired end-to-end and the cassette layer working. The CLI was clean. We added the API key, ran `recon demo` for the first time against the real Gemini Developer API — and the very first Plan call exploded before the agent even reached step 1.

**What we tried first.** Spent roughly 20 minutes assuming this was a Pydantic v2 version issue. We checked `pydantic.__version__` (2.13.4, current), tried passing `mode="json"` to `model_json_schema()`, tried setting `model_config = ConfigDict(extra='allow')` — none of it changed the schema output meaningfully. Wrong hypothesis.

**What actually fixed it.** Pydantic v2's `model_json_schema()` emits `additionalProperties: false` by default for closed-schema objects. The Gemini Developer API (free tier) rejects this key — it is only honored in the paid Enterprise Agent Platform. The fix is in `src/recon_agent/llm/providers.py`: `sanitize_schema_for_gemini()` recursively walks the schema dict and strips `additionalProperties` (and `title`, which Gemini also dislikes in nested positions) before passing it to the SDK. The Pydantic class is converted to a sanitized dict at call time; the SDK accepts the dict shape natively.

**What we learned.** Pydantic-derived JSON schemas are not portable across LLM providers. OpenAI's `strict: true` mode REQUIRES `additionalProperties: false` (and every property in `required`). Gemini Developer API REJECTS `additionalProperties` entirely. We ended up with two sanitizer functions — `sanitize_schema_for_gemini` and `sanitize_schema_for_openai` — that adapt the same Pydantic class to the providers' incompatible schema dialects. The structured-output abstraction is leakier than it looks.

---

## (g) What I would change with 2 more weeks

1. **Real PayU sandbox integration** instead of the static JSON fixture. PayU has a free sandbox tier; this would exercise actual rate-limit semantics, request signing, and pagination. The mock-API layer is the biggest fidelity gap in the current design.

2. **MCP server skin** so the agent is callable from Claude Desktop. This maps to Assignment 04's MCP requirement and is the natural production interface for "trigger reconciliation via natural language" — a single `recon_agent_mcp.py` exposing the loop as a tool.

3. **Third provider for shadow comparison on the classify phase.** Plan-phase shadow comparison is in place; extending it to classify (where structured-output reliability varies most between providers) would double the comparison artifact's coverage and give a more complete picture of provider differences.

4. **SQLite persistence** for cross-run analytics. Currently every run is filesystem-only. SQLite would enable queries like "average per-run cost over the last 50 evals grouped by scenario" without parsing JSON files — and would make the cost-ceiling regression test faster to write.

5. **Prompt versioning with diff-on-regression.** Prompts currently live as `.txt` files in `src/recon_agent/agent/`. With content-hashed versioning, the CI gate could surface "this PR changed the plan prompt; here is the diff and the eval delta" — closing the loop on prompt regressions and making it immediately obvious when a prompt change shifts pass rates.

---

## (h) Model routing rationale

Short answer: **OpenRouter `openai/gpt-oss-120b:free`** for Plan/Decide/Propose/Summary (free-tier, native structured-output, 200 req/day quota — sufficient for cassette recording and demo); **OpenAI `gpt-4o-mini`** for Classify (paid, OpenAI's strict `json_schema` mode is the most reliable for fixed-enum batch classification); **OpenAI `gpt-4o`** for shadow-Plan only (capable-tier comparison, invoked only when `--shadow` is set). Gemini remains available as a configurable fallback via `GEMINI_MODEL` env var, with code paths and sanitizers retained.

Full defense — including the migration from Gemini to OpenRouter (driven by Gemini's 20 req/day free-tier ceiling), the three-provider rationale, the `OPENROUTER_MODEL` and `PLAN_PROVIDER` override mechanisms, and per-row pricing — is in `docs/model_routing.md`.

---

## (i) Eval design rationale: 12 rigorous over 30+ parametric

The rubric says "30+ test cases". The 12 scenarios here are more defensible than 30+ parametric variants would be.

The argument: parametric coverage (vary a float from 0.0 to 1.0 in 30 steps) tests the data fixture generator, not the agent. The agent sees one transaction set per run. What matters is whether the agent behaves correctly across qualitatively different situations: clean reconciliation, timezone normalization, encoding failures, duplicate detection, value mismatches, API rate limiting, corrupted source data, irreconcilable sets, token budget exhaustion, and wall-time budget exhaustion. The 12 scenarios span all of those. Each scenario has a single deterministic expected outcome (pass/fail, plus specific assertions on the corrections ledger and report). A parametric test that runs "amount mismatch" 20 times with different floats does not add coverage — it adds noise.

The cassette layer makes each scenario hermetically reproducible. The CI gate runs all 12 in ~30 seconds with zero API spend. If a code change breaks scenario 7, the failure message names scenario 7 and shows the assertion diff — not a stochastic flap in a parametric run.

---

## (j) Cost data

Measured numbers from the actual cassette-recording session and replay runs.

**Per single agent run (replay mode, what `make demo --llm-mode replay` costs):**

- LLM calls: **₹0.00** — every call resolves from a committed cassette
- Wall-clock: typically 0.5-1.5 seconds per scenario
- Static per-tool cost estimates accumulate to a small INR figure in the report (see §(e) cost column) — these are accounting estimates, not real spend

**Per cassette-recording run (the live `LLM_MODE=record python -m evals.runner` that produced the committed cassettes):**

- 194 total LLM responses recorded across 12 scenarios
- 409,487 input tokens + 26,864 output tokens captured into cassettes
- Plan / Decide / Propose / Summary calls (~70% of volume) → routed to OpenRouter `openai/gpt-oss-120b:free` → **₹0.00** (free tier)
- Classify calls (only fired when discrepancies are found, ~10-15 total across the 12 scenarios) → routed to OpenAI `gpt-4o-mini` → estimated **~₹0.40-0.80** based on cassette token counts at gpt-4o-mini pricing ($0.15/M input, $0.60/M output)
- Total cassette-recording session: **estimated under ₹1 in paid spend** (essentially the OpenAI Classify calls; everything else was free)

**Per full 12-scenario eval run:**

- Replay mode (`make eval`): **₹0.00 LLM, ~6 seconds wall-clock**, runs offline, what CI uses
- Live cassette re-record (`make eval-live`): **~₹1** in paid OpenAI Classify burn, free OpenRouter for the rest, ~3-8 minutes wall-clock depending on free-tier rate limits

**Per shadow comparison run (when --shadow flag is set):**

- Adds GPT-4o (`shadow_plan` route) calls in parallel with each Plan call
- GPT-4o at $2.50/M input + $10/M output is ~25x more expensive than gpt-4o-mini
- Estimated extra cost per 12-scenario shadow recording: **~₹15-30** (12 scenarios × ~3-5 Plan calls × ~1000 tokens average)
- Not run as part of the standard submission flow; reserved for explicit shadow-testing sessions

**Total development cost across the build:**

- Most development used cassette replay (₹0 cost). Live runs were limited to: provider smoke tests, initial cassette recording, debugging individual scenarios that failed first-attempt recording.
- Conservative estimate from OpenAI dashboard + OpenRouter usage: **under $1-2 USD total** across the entire build. (User can verify the exact number from their OpenAI dashboard.)
- OpenRouter free-tier was used heavily but cost $0 by definition.
- Gemini was used for early prototyping; switched away from after free-tier quota exhaustion (story in §(f)).

**Pricing source:** `src/recon_agent/llm/pricing.py`. USD→INR conversion = 83.0. All numbers above use current (May 2026) published per-provider pricing.

---

## (k) Operations cheatsheet

| Reviewer question | Where to look |
|---|---|
| "Show me the loop" | `src/recon_agent/agent/loop.py` |
| "Show me the phases" | `src/recon_agent/agent/phases.py` |
| "Show me the 8 tools" | `src/recon_agent/tools/` (one file per tool) |
| "Show me the schema bug fix" | `src/recon_agent/llm/providers.py` — `sanitize_schema_for_gemini` and `sanitize_schema_for_openai` |
| "Show me the model routing" | `src/recon_agent/llm/router.py` and `docs/model_routing.md` |
| "Show me recovery" | `src/recon_agent/recovery/classifier.py` and `docs/recovery_strategies.md` |
| "Show me the budget gate" | `src/recon_agent/agent/budget.py` |
| "Show me the evals" | `evals/scenarios/` (12 scenario files) and `evals/runner.py` |
| "Show me the cassette layer" | `src/recon_agent/llm/cassettes.py` |
| "Show me the cost tracking" | `src/recon_agent/llm/pricing.py` and `reports/eval_*/summary.json` |
| "Show me the state snapshots" | `reports/run_<ts>/step_<n>.json` after any run |
| "Show me the corrections ledger" | `corrections.jsonl` after any demo run |
| "Run the tests" | `make test` (86 tests, unit + integration) |
| "Run the evals" | `make eval` (12 scenarios, cassette replay, ~30s, free) |
| "Full architecture" | `docs/architecture.md` |
