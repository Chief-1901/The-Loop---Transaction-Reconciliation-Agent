# Deep-Dive Interview Prep — Recon Agent

**Format expected:** 60-minute technical deep-dive after submission shortlisting.
**Reviewers will:**
- Walk through architecture with you
- Stress-test the agent live
- Ask you to make a change on the spot (prompt swap, model swap, new eval case)
- Probe whether you actually built it and understand it

This document is your study guide. Don't memorize verbatim — internalize the reasoning so you can answer variations.

---

## Section A — The 4 stress-test questions from the brief (verbatim)

The brief lists these four (`grabon_challenge.md` §lines 149-154). Each has a prepared answer + a command to demonstrate.

### A.1 "We will disable a tool mid-run. Does the agent re-plan?"

**Answer:**

Yes. Tool registry has runtime filtering via `--disable-tool <name>`. When disabled, `ToolRegistry.available()` excludes it; the planner's `schemas_for_llm()` doesn't see it. If the agent already started before the disable, the next `Plan` call gets the filtered list and chooses an alternative tool, with reasoning logged at the Decide step.

**Live demo:**
```bash
recon demo --disable-tool fetch_api
```

The agent will load CSV successfully, attempt to call `fetch_api`, get `API_NOT_FOUND` (the registry returns this for disabled tools), classifier marks it `persistent`, recovery emits `ReplanWithAlternativeTool` with hint "fetch_api not available; proceed with CSV-only analysis". Next Plan call routes to `normalize_timezone` / `match_records` on CSV-only path. Agent halts with `status=degraded` and the report flags all API-side records as `missing_in_api`.

**Show:**
```bash
grep recovery.dispatched reports/run_*/log.jsonl
```

Reviewer sees the exact recovery decision trail.

### A.2 "We will set max_tool_calls=3 on a task that needs 15. Does it halt cleanly?"

**Answer:**

Yes. Budget enforcer checks at the **top** of every loop iteration, before any LLM/tool call. On breach: writes `PARTIAL_REPORT.md` (what got done vs what's pending), flushes state snapshot, exits code 2. Never crashes mid-write. Never loops forever.

**Live demo:**
```bash
recon demo --budget-calls 3
```

The agent will get through Plan→Act for load_csv (1 call), Plan→Act for fetch_api (2 calls), Plan→Act for normalize_timezone (3 calls), then next iteration's budget check fires `Breach(dim="tool_calls", observed=3, limit=3)`. Halt with `halt_reason="budget breach: tool_calls (3 > 3)"`.

**Show:**
```bash
cat reports/run_*/PARTIAL_REPORT.md
```

Reviewer sees what completed (3 tool calls, CSV+API loaded, TZ normalized) vs pending (matching, classification, corrections).

### A.3 "At step 7, why did the agent try X instead of Y?"

**Answer:**

Three sources of truth, all in `reports/run_<ts>/`:

1. **`step_007.json`** — full agent state at step 7. Shows `current_phase`, `last_decision_reasoning`, accumulated discrepancies so far.
2. **`log.jsonl`** — chronological log. Filter for step 7: `jq 'select(.step == 7)' log.jsonl`. Shows every event: phase enters, LLM call (with tokens + cost + provider), tool call (with args + latency + outcome), Decide reasoning.
3. **`diff step_006.json step_007.json`** — shows exactly what one iteration changed.

The Decide phase's LLM call has its full prompt + response in the cassette (if replayed) or can be reconstructed from log.jsonl (if live). So even the model's "why" is recoverable.

**Live demo:**
```bash
# Pick any step from a recent run
jq 'select(.step == 7)' reports/run_*/log.jsonl
diff reports/run_*/step_006.json reports/run_*/step_007.json
```

### A.4 "Add a new tool on the spot. How long does it take?"

**Answer:**

Three minutes. Tool registry auto-discovers any `.py` file in `src/recon_agent/tools/` that defines a `Tool` subclass.

**Walkthrough to perform live:**

1. (~30 sec) Create new file `src/recon_agent/tools/check_merchant_blacklist.py`:
   ```python
   from .base import Tool, ToolResult
   from pydantic import BaseModel

   BLACKLIST = {"FraudMerchant1", "ShadyCo"}

   class BlacklistInput(BaseModel):
       merchants: list[str]
   class BlacklistOutput(BaseModel):
       flagged: list[str]

   class CheckMerchantBlacklist(Tool[BlacklistInput, BlacklistOutput]):
       name = "check_merchant_blacklist"
       input_schema = BlacklistInput
       output_schema = BlacklistOutput
       cost_estimate_inr = 0.0
       timeout_seconds = 2.0

       def run(self, inputs):
           flagged = [m for m in inputs.merchants if m in BLACKLIST]
           return ToolResult(ok=True, output=BlacklistOutput(flagged=flagged))
   ```

2. (~30 sec) Restart agent (Ctrl-C if running): `recon demo`

3. (~2 min) Show the planner now sees it. Optionally craft a Plan-phase prompt addition that mentions the new tool exists — but typically the LLM picks it up from the schemas alone.

**The point:** zero wiring beyond the file itself. No registry edit, no `__init__.py` change, no test glue.

---

## Section B — "Explain what's under the abstraction" (the framework question)

The brief says (§lines 422-424): "If you use LangChain and cannot explain what happens between your function call and the HTTP request to Anthropic's API, that is a problem."

We use **no framework**. Raw SDKs. So our answer to every "what's under this?" is: "I built it. Here's the file."

### B.1 "What happens between `router.call('plan', ...)` and the HTTPS request to Gemini?"

1. **`LLMRouter.call(subtask='plan', ...)`** in `src/recon_agent/llm/router.py` looks up the routing table entry: `{provider: 'gemini', model: 'gemini-2.5-pro'}`.
2. **Cassette check.** If `LLM_MODE=replay`, computes SHA-256 hash of `(provider, model, subtask, messages, schema)`, looks up in `evals/cassettes/<scenario>.jsonl`. Hit → return immediately, no API call, `cache_hit=True`.
3. **Provider dispatch.** Calls `gemini_call(model, messages, schema, timeout_s)` in `providers.py`.
4. **SDK call.** `gemini_call` instantiates `genai.Client(api_key=os.environ['GEMINI_API_KEY'])`, calls `client.models.generate_content(...)` with `response_mime_type='application/json'` and `response_schema=<pydantic_class>`. The SDK serializes to a JSON HTTP body and POSTs to `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent`.
5. **Response parsing.** SDK returns a structured response. We extract `.text` (validated JSON), parse via Pydantic into the schema class, record `tokens_in`, `tokens_out`, latency.
6. **Cost computation.** `cost_inr(model, tokens_in, tokens_out)` reads from the static `PRICING` dict. Multiplies by `USD_TO_INR = 83.0`.
7. **Return.** Wraps as `(parsed_output, LLMCallRecord)`.

If `LLM_MODE=record`, after step 5 we `cassettes.put(hash, raw_response)` so future replays match.

### B.2 "Why ReAct over Plan-and-Execute?"

- Reconciliation is **branchy**: the right next tool depends on what previous tools found. A pre-planned 8-step sequence either over-specifies (and gets wrong on edge cases) or under-specifies (and is just ReAct in disguise).
- Recovery is simpler. ReAct re-plans one step on failure. Plan-and-Execute either re-plans the whole sequence (waste) or patches mid-sequence (complexity).
- "Decide reasoning at step N" is concrete and visible. With Plan-and-Execute, the reasoning is mostly in step 0, and step N is "I'm doing what the plan said."
- ReAct fits the rubric's "Plan/Act/Observe/Decide visible" criterion more naturally — Decide is real per-iteration meta-cognition, not just sequence-pointer management.

### B.3 "Why a corrections ledger over in-place mutation?"

- **Auditability:** every correction has a timestamp, confidence, reason, applier. Reviewer can trace any change.
- **Reversibility:** sources are immutable. Re-run with different config? Just point at the same fixtures.
- **Eval verification:** `applied_ids ∩ expected_ids` is a one-liner. With mutation we'd need to diff full files.
- **Production parallel:** real payments-ops teams keep correction journals; they never mutate the source of truth.
- **Demo repeatability:** Loom recording can be re-run cleanly. No "reset fixtures" step.

### B.4 "Why structured output via response_schema vs free text + parse?"

- **Validation at the boundary.** If the LLM returns malformed output, we catch it inside the provider call, not after the agent has acted on it.
- **Provider-native.** Both Gemini's `response_schema` and OpenAI's `json_schema strict` are first-class APIs. Using them costs nothing extra; reinventing JSON parsing is fragile.
- **Pydantic alignment.** Same `BaseModel` defines the LLM's output contract AND our internal state shape. No translation layer.
- **Recovery clarity.** `LLM_BAD_OUTPUT` is its own error code, classified `persistent`, with a clear recovery path. Free-text parse fails are messier to classify.

### B.5 "Why paired bootstrap for the comparison?"

- The 12 scenarios are **paired observations** (same fixture seed, two configs). Independent-samples t-test would discard the pairing structure and have less power.
- Pass/fail is **binary**. Paired bootstrap on a per-scenario delta handles this without normality assumptions. McNemar's test would also work but bootstrap gives us a CI directly.
- **Resampling is intuitive to defend:** "10,000 times, I resampled the 12 scenarios with replacement, recomputed the pass-rate delta. The 2.5th and 97.5th percentiles of those deltas are my 95% CI."
- 10k resamples is fast (<1s on 12 paired observations) and well over what's needed for a stable estimate.

### B.6 "Why structlog?"

- JSON output is grep-able and `jq`-able. `print()` isn't.
- Bound loggers — every event from a phase, a tool, a recovery decision carries the scenario name, the step, the phase. No string interpolation.
- Multiple renderers — JSON to disk for analysis, KeyValueRenderer for the dashboard if needed.
- Standard library doesn't have this; `structlog` is small + well-maintained + no transitive deps.

### B.7 "Why Pydantic v2?"

- Mandatory for the rubric — typed schemas. v2's `model_json_schema()` is what we feed to the LLM as the structured-output contract.
- v2 is 5-50× faster than v1 (Rust core). Matters when we serialize state every step.
- `Discriminated unions` for `ToolError.kind` and `RecoveryAction.kind` give exhaustive matching with type checker support.

---

## Section C — Model routing defense (defend every row)

The deep-dive WILL ask "why X for Y." Prepared answers below.

### C.1 "Why Gemini 2.5 Pro for Plan?"

> Plan is the hot reasoning path — every iteration starts with it. Mistakes cascade. Gemini 2.5 Pro has the highest reasoning quality of the models I evaluated for tool-selection tasks. The cost premium over Flash is about 20x, but plan calls are ~1 per iteration × 22 iterations = 22 calls per run, so per-run plan cost is still under ₹3. Worth it.

### C.2 "Why GPT-4o-mini for classify?"

> Classify is the opposite of plan — high volume (one call per discrepancy bucket × ~5 buckets), constrained JSON output, no reasoning needed beyond pattern-matching against a fixed taxonomy. GPT-4o-mini at $0.15/1M-input is roughly 1% of Gemini Pro's price. Using one model for everything would mean either paying Gemini Pro prices for classification (~30× waste) or accepting 4o-mini quality on planning (worse decisions, longer runs).

### C.3 "Why Gemini 2.5 Flash for summary?"

> One call at the end. Natural-language only, no structure. Flash is the cheap-Gemini answer and amortizes the auth/client I already opened for Plan/Decide. About ₹0.02 per call. Switching to a third provider for this single call would add an SDK and trade ₹0.01 for SDK complexity. Bad trade.

### C.4 "Why two providers, not four?"

> The rubric's 5/5 says '4+ providers used deliberately'. The keyword is **deliberately**. Adding Groq for shadow comparison and DeepSeek for error parsing would be subtasks-in-search-of-a-provider, not the other way around. The brief itself warns against this anti-pattern: 'Using GPT-4o for everything shows a lack of judgment' — and so does using four providers when two are doing real work.
>
> Instead, I made the 2-provider story tight: each provider has multiple justified subtasks, costs are tracked per task, the shadow comparison statistically validates the Plan-phase choice. I'd rather lose ~3 rubric points on the count and gain trust on the judgment.

### C.5 "Why shadow only the Plan phase, not Decide?"

> Plan is the iteration's bottleneck — wrong plan → wrong action → wrong observation. Decide is reactive (continue/replan/halt) and constrained by the observation. The cost-benefit math: shadowing Plan doubles ~22 calls/run (one critical decision each). Shadowing Decide doubles another ~22 calls/run for less variance in outcome. The marginal information from shadow-Decide isn't worth the cost.
>
> Also: shadowing both would make the comparison artifact noisier (two confounded dimensions). One-axis comparison gives a clean answer.

### C.6 "Could you swap Gemini for Claude right now?"

> Yes — `ROUTING_TABLE` in `src/recon_agent/llm/router.py` is a dict. Add a Claude entry, point Plan/Decide rows at it. Provider adapter file: `claude_call(model, messages, schema, timeout_s)` in `providers.py`. Pricing entry in `pricing.py`. About 20 lines of code total. Then re-record cassettes with `make eval-live`. Total time: ~15 minutes to ship, ~5 more minutes for cassettes.

### C.7 "Could you swap Gemini for Llama via Ollama right now?"

> Same shape as Claude swap. Provider adapter would use the Ollama Python client. Pricing entry would be `ModelPrice(input=0, output=0)` for local. Only catch: Ollama doesn't always honor `response_schema` strictly, so I'd add a Pydantic validation retry loop in the adapter — 2-3 extra lines. Total: 25-30 minutes.

---

## Section D — "What broke first" (TO BE FILLED ON DAY 4)

After implementation, write here the actual hardest bug encountered. Format:

```
### What we saw
The symptom that surfaced. Be specific — error message, stack trace, observable behavior.

### What we tried first
Wrong hypothesis #1. Wasted N hours.

### What we tried next
Wrong hypothesis #2. Wasted M hours.

### What actually fixed it
The root cause + the fix.

### What we learned
Generalizable lesson. Something we'd do differently next time.
```

**Reviewers love this section.** It's the strongest possible signal that I wrote this code and debugged it, not that I generated it and shipped it untouched.

**Candidate "what broke first" stories to watch for during build (any of these would qualify):**

- Pydantic v2 strict schema validation on Gemini's response — when the model returns extra keys or skips optional fields
- Cassette hash collisions if we forget to include `response_schema` in the hash inputs
- Encoding detection edge case: a CSV that's mostly utf-8 with a few latin-1 bytes — chardet gives low confidence either way
- IST-stored-as-UTC detection false-positive on Indian-merchant late-night transactions
- Race condition between snapshot-to-disk and the dashboard's read of step files
- Recovery infinite loop — transient → retry → transient → retry → ... if the classifier doesn't count retries correctly
- Shadow runner's asyncio.gather error handling — what if the secondary call fails?

Pick the real one. Write it honestly.

---

## Section E — "What I'd change with 2 more weeks" (TO BE FILLED ON DAY 4)

Honest, concrete, production-thinking. Don't be falsely modest, don't be falsely ambitious. Likely candidates:

1. **Replace static fixture API with a real PayU sandbox integration.** Right now we mock the response shape; with 2 more weeks I'd hit the actual sandbox (PayU has a free tier), include real rate-limiting behavior, add request signing.
2. **Add MCP server skin** so the agent is callable from Claude Desktop. Brief mentions MCP in Assignment 04; it's a credible "production interface" upgrade.
3. **Add a third provider** (Groq Llama 3.1 70B) for shadow comparison on the Classify subtask. We have shadow on Plan; extending it to a second subtask doubles the artifact's coverage. Skipped in 3-day scope because the Plan comparison is the higher-leverage one.
4. **Persist runs to SQLite** for cross-run analysis. Right now everything is filesystem. SQLite would let us query "average cost over the last 50 runs grouped by scenario" without parsing JSON files.
5. **Migrate prompts to per-version files + diff on regression.** Currently prompts are in `src/recon_agent/agent/prompts/*.txt`. With versioning, the CI gate could surface "this PR changed the plan prompt; here's the diff and the eval impact."
6. **Add real PayU sandbox + Slack webhook for failure-recovery alerts.** Brief Assignment 04 mentions this pattern; it's a natural extension to add ops-style alerting on recovery=degrade events.

Pick 3-4. Don't list 10 — looks unfocused.

---

## Section F — Walkthrough script (for the live deep-dive, not Loom)

Same content as Loom but more interactive. Reviewers will interrupt. Prepare for that.

### F.1 Opening (1-2 min)

> "I picked Assignment 02 because reconciliation has unambiguous ground truth — the discrepancies are injected by my generator, so I can verify the agent's correctness mechanically. That lets me focus on the agent-engineering axis the rubric is grading, not on whether my parsing of a real PayU statement is correct.
>
> Stack: Python 3.11, Pydantic v2 for schemas, structlog for logging, Rich for the dashboard, no framework. Two LLM providers — Gemini and OpenAI — wired through a single router. I'll start with the loop, then tools, then recovery, then evals. Stop me at any point."

### F.2 Loop walkthrough (5 min)

Open `src/recon_agent/agent/loop.py`. Trace through `run()` step by step. Highlight:
- Budget gate first, before any cost
- Four phase classes, each typed input/output
- Recovery branch (3 kinds: retry / replan / degrade)
- Snapshot after every `apply()`

**Expected interruption:** "What happens if Plan returns an unsupported tool name?"
**Answer:** Pydantic validation at Plan's output catches it (it's a Literal of registry names). If somehow it slips through, `tools.get(name)` raises KeyError, caught as `fatal` error, recovery degrades.

### F.3 Recovery deep dive (5 min)

Open `src/recon_agent/recovery/classifier.py`. Walk the error→strategy table. Demo with `--fail-tool fetch_api:API_NOT_FOUND` (forces persistent immediately) to show replan path.

**Expected interruption:** "What if recovery itself fails?"
**Answer:** Recovery layer has no LLM dependency (classifier is deterministic, strategies are pure). The only way it can fail is `RetryWithBackoff` re-running a tool that fails again — caught as next iteration's error, classified again. If 3 consecutive failures → budget check fires → halt.

### F.4 Eval walkthrough (5 min)

Open `evals/scenarios/recovery_01_api_429.py`. Walk through the `Scenario` model: fixture variant, seed, expected. Open `evals/verify.py` — show the 5 orthogonal checks.

Demo `make eval` live (replay mode, ~30s).

Open `reports/shadow_comparison_*.md`. Walk the p-value table.

Open `.github/workflows/eval.yml`. Walk the CI gate.

**Expected interruption:** "What if the cassette is stale?"
**Answer:** `make eval-live` re-records. The record mode also diffs new responses against existing cassettes and prints a warning if behavior changed — so we don't silently update cassettes when prompts drift.

### F.5 On-the-spot tasks (likely 5-10 min)

Be ready to do **any of these on screen**:

- "Add a new eval scenario." → Copy `happy_01_clean_reconciliation.py`, edit name/variant/expected, save. Done in 60s. Then `make eval-live` regenerates cassette.
- "Add a new tool." → Walkthrough from §A.4 above. ~3 min.
- "Swap Gemini for Claude on Plan." → §C.6 above. ~15 min.
- "Change the budget breach to allow one warning before halt." → Edit `budget.py` to add a `warning_count` field, hook into `check()`, expose as `--budget-warnings`. ~10 min.
- "Make Decide use the same shadow runner as Plan." → Generalize ShadowRunner from Plan-only to subtask-parametric. ~15 min.

### F.6 Closing (1-2 min)

> "Couple of honest notes. With more time I'd add a real PayU sandbox, an MCP skin, and a third provider for Classify-phase shadow. The hardest bug during build was [actual story from §D]. Happy to take more questions."

---

## Section G — Quick-reference cheat sheet

Things to have ready to recite:

- **Pass rate on the 12 eval scenarios:** 12/12 (replay mode) — fill in real number after final eval run
- **Total dev cost:** ~₹585 (~$7) — fill in real number from provider dashboards
- **Per-run cost (live):** ~₹4.34 — fill in real
- **Per-run cost (shadow on):** ~₹8.96
- **Eval-replay cost:** ₹0
- **Setup time from `git clone`:** ~3-4 minutes
- **Lines of code total:** ~50 Python files, ~3000 LOC — fill in real
- **No-framework justification:** "I built it. Here's the file."
- **Multi-LLM count:** 2 providers, 4 models — chose this over 4 providers because boxchecking ≠ judgment
- **Eval scenario count:** 12 rigorous over 30+ parametric — defended in README §(i)

---

## Section H — Questions to ask THEM at the end

Always ask 2-3 questions. Signals you're evaluating the role too.

1. "How much of GrabOn's real agent infrastructure is currently in production vs in research? What's the gap between AI Labs and the rest of GrabOn?"
2. "When you've shipped agents in production, what's been the most common failure mode you didn't anticipate during build?"
3. "Where does the team draw the line between 'agent should retry' and 'agent should escalate to a human'? Is that policy or per-agent?"
4. "How do you measure success of an autonomous agent in production — is it pass rate on synthetic evals, or operator-time-saved, or something else?"
5. (If applicable) "Is the AI Labs team co-located in Hyderabad or is remote on the table?"

Pick 2-3 that fit the room's energy.

---

**Final reminder:** This document is for **your prep**. Don't read from it in the interview. Internalize the reasoning, then talk like a person who built the thing.
