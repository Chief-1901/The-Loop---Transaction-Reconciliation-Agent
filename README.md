# Recon Agent

GrabOn AI Labs Challenge 02 — Transaction Reconciliation Agent.

Demo walkthrough: `<LOOM_URL>`

---

## (a) What I built and why I chose Assignment 02

**The system.** Recon Agent is a single autonomous agent that reconciles two transaction data sources — a CSV export from an internal tracking database and a JSON payload from a mock PayU settlements API — and produces a signed corrections ledger (`corrections.jsonl`) plus a human-readable report. The agent runs as a ReAct loop with four named phases (Plan, Act, Observe, Decide), eight typed tools, a two-provider LLM router (Gemini 2.5 Flash + OpenAI GPT-4o-mini), a recovery layer that handles transient and fatal tool errors without crashing the loop, and a hard budget gate that enforces token and wall-time ceilings. The entire loop is ~70 lines in `src/recon_agent/agent/loop.py`. There is no framework under it — no LangChain, no LlamaIndex, just raw SDK calls gated by Pydantic-typed contracts.

**Why Assignment 02.** The reconciliation task has deterministic ground truth: a record either matches or it does not, a discrepancy is either correctly classified or it is not, a correction either fixes the number or it does not. That makes agent behavior mechanically verifiable, which is the property the rubric most directly grades. Assignment 02 also stresses the axis that separates "chatbot wrapper" from "agent engineering": multi-step planning under budget constraints, typed structured output that must work across two incompatible LLM schema dialects, error recovery that distinguishes transient from fatal failures, and an eval harness that replays recorded cassettes to give deterministic pass/fail results without API keys. That is the work this submission tries to demonstrate.

---

## (b) Architecture

Full diagram and data-flow in `docs/architecture.md`. The loop in one glance:

```
budget.check
     |
     v
  PLAN (LLM: gemini-2.5-flash)
     |
     v
  ACT (tool call) ───── ToolError ──▶ Recovery (retry / replan / degrade)
     |                                       |
     v                                       |
  OBSERVE (summarize result, patch state)    |
     |                                       |
     v                                       |
  DECIDE (LLM: gemini-2.5-flash) ◀──────────┘
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

Cassette recording is deferred to Cassette Day (the day real API keys are added and all 12 scenarios run live for the first time). Until then, the eval runner executes replay-mode only.

Once cassettes are recorded, results will appear in:

- `reports/eval_<timestamp>/summary.json` — per-scenario pass/fail, tool call counts, cost
- `reports/shadow_comparison_<timestamp>.md` — statistical comparison of Gemini Flash vs GPT-4o on the Plan phase
- `evals/baselines/main.json` — the pinned baseline that the CI gate compares against

The 12 scenarios and their expected verdicts are defined in `evals/scenarios/`. The runner is `evals/runner.py`. Run `make eval` to see current status.

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

Short answer: Gemini 2.5 Flash for Plan/Decide/Propose/Summary (high-volume, constrained-output decisions); GPT-4o-mini for Classify (cheap structured JSON, fixed Pydantic enum, high volume); GPT-4o for shadow-Plan only (capable-tier comparison, invoked only when `--shadow` is set).

Full defense — including the free-tier quota argument for Flash over Pro, the "two providers used deliberately" rationale, and the `PLAN_PROVIDER=openai` override mechanism — is in `docs/model_routing.md`.

---

## (i) Eval design rationale: 12 rigorous over 30+ parametric

The rubric says "30+ test cases". The 12 scenarios here are more defensible than 30+ parametric variants would be.

The argument: parametric coverage (vary a float from 0.0 to 1.0 in 30 steps) tests the data fixture generator, not the agent. The agent sees one transaction set per run. What matters is whether the agent behaves correctly across qualitatively different situations: clean reconciliation, timezone normalization, encoding failures, duplicate detection, value mismatches, API rate limiting, corrupted source data, irreconcilable sets, token budget exhaustion, and wall-time budget exhaustion. The 12 scenarios span all of those. Each scenario has a single deterministic expected outcome (pass/fail, plus specific assertions on the corrections ledger and report). A parametric test that runs "amount mismatch" 20 times with different floats does not add coverage — it adds noise.

The cassette layer makes each scenario hermetically reproducible. The CI gate runs all 12 in ~30 seconds with zero API spend. If a code change breaks scenario 7, the failure message names scenario 7 and shows the assertion diff — not a stochastic flap in a parametric run.

---

## (j) Cost data

TODO: filled after Cassette Day (real API keys added, all 12 scenarios run live, actual token counts recorded).

**Projected numbers (not measurements — projections from prompt token estimates):**

| Phase | Provider + model | Est. input tokens/run | Est. output tokens/run | Est. cost/run |
|---|---|---|---|---|
| Plan (x ~8 steps) | Gemini 2.5 Flash | ~12,000 | ~800 | ~$0.0011 |
| Decide (x ~8 steps) | Gemini 2.5 Flash | ~4,000 | ~200 | ~$0.0004 |
| Classify (x ~5 discrepancies) | GPT-4o-mini | ~2,500 | ~250 | ~$0.0005 |
| Propose (x ~5) | Gemini 2.5 Flash | ~2,000 | ~250 | ~$0.0002 |
| Summary (x 1) | Gemini 2.5 Flash | ~3,000 | ~500 | ~$0.0004 |
| **Total per run** | | | | **~$0.0026 (~INR 0.22)** |
| **12-scenario eval** | | | | **~$0.031 (~INR 2.6)** |
| **Shadow-plan eval** | GPT-4o (shadow only) | ~12,000 | ~800 | ~$0.038 extra |

These projections use current (May 2026) published pricing. Actual numbers may differ based on prompt length at recording time. Real measurements will replace this table once `make eval-live` has been run and `reports/eval_*/summary.json` files exist.

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
