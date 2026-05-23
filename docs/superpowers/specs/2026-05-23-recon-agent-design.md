# Recon Agent — Design Spec

**Project:** GrabOn AI Labs Challenge — Assignment 02 ("The Loop") — Transaction Reconciliation Agent
**Date:** 2026-05-23
**Status:** Design approved; ready for implementation plan
**Target score:** 4-5/5 across all rubric dimensions (~92-94% projected)

This document is the canonical spec for the recon-agent project. It supersedes the prep doc embedded in the initial brainstorming message. The implementation plan reads from this spec.

---

## 1. Goals and scoring framework

### 1.1 What we are building

An autonomous single-agent system that reconciles GrabOn's deal-redemption transactions across two mock data sources (CSV + JSON/REST API), identifies discrepancies, proposes corrections, applies them to an append-only ledger, and produces a structured reconciliation report — without human intervention.

### 1.2 The rubric we are optimizing against

(Source: `grabon_challenge.md` §Evaluation Rubric, lines 365-376)

| Dimension | Weight | 5/5 criteria |
|-----------|--------|--------------|
| Agent Architecture | 25% | Clean named loop. Plan/Act/Observe/Decide visible. Tool registry discoverable. State management versioned. |
| Eval Rigor | 20% | 30+ cases, catches a real regression. Statistical comparison with p-values. CI/CD gate blocks bad changes. |
| Failure Recovery & Production | 20% | Distinguishes error types. Re-plans on persistent failure. Budget kills runaway. Observability shows every decision. |
| Multi-LLM & Cost | 15% | 4+ providers used deliberately. Cost tracked per task type. Cheaper model for subtasks. Shadow testing present. |
| Code & README | 20% | README is architecture doc. Diagram, tradeoffs, "what broke first", "what I'd change". Code clean. |

### 1.3 The "smart plan" decision

After analyzing the rubric, we deliberately chose **not** to inflate two dimensions:

- **Multi-LLM:** 2 providers (Gemini + OpenAI) instead of 4. Adding Groq + DeepSeek would buy ~3 rubric points but exposes us to "why does Groq specifically do error parsing?" — a question without a defensible answer. The brief warns explicitly against this anti-pattern.
- **Eval Rigor case count:** 12 rigorous scenarios instead of 30+ parametric inflations. The underlying criterion is "catches a real regression" — we meet that via cassette drift detection + paired bootstrap + CI gate, not case count.

We expect 4-5/5 on both dimensions with high execution confidence.

### 1.4 Approved design decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Planner output style | ReAct (single next action per iteration) |
| 2 | Apply-correction semantics | Append-only `corrections.jsonl` ledger |
| 3 | Eval LLM mode | Record-replay cassettes; demo stays live |
| 4 | LLM providers | Google Gemini + OpenAI; no Anthropic/Claude per user preference |
| 5 | Shadow testing | Plan-phase only, `--shadow` flag, off by default |
| 6 | Eval scenarios | 12 rigorous (5 happy + 3 recovery + 2 budget + 2 impossible) |
| 7 | Statistical comparison | Paired bootstrap, 10k resamples, p-value + 95% CI |
| 8 | CI gate | GitHub Actions, runs `make eval` on PR, blocks on regression |
| 9 | State management | Pydantic v2 `AgentState` with `version` field, snapshot per step |
| 10 | Recovery | Separate layer; 3 strategies dispatched by error kind |
| 11 | Budget | Pydantic `Budget`, checked top-of-loop, CLI-overridable |

---

## 2. High-level architecture

```
                    ┌─────────────────────────────────────────┐
                    │           AgentLoop.run()               │
                    │   while not state.is_terminal():        │
                    │       budget.check_or_halt()            │
                    │       plan     = Plan(state).run()      │
                    │       action   = Act(plan).run()        │
                    │       obs      = Observe(action).run()  │
                    │       decision = Decide(obs,state).run()│
                    │       state.apply(decision)             │
                    │       state.snapshot_to_disk()          │
                    └────┬───────┬───────────┬──────────┬─────┘
                         │       │           │          │
                    ┌────▼──┐ ┌──▼──┐    ┌───▼───┐   ┌──▼─────┐
                    │ Plan  │ │ Act │    │Observe│   │ Decide │
                    │ (LLM) │ │tool │    │(parse │   │ (LLM)  │
                    │       │ │reg. │    │ + sum)│   │        │
                    └───┬───┘ └──┬──┘    └───────┘   └────┬───┘
                        │        │                        │
                        │        ▼                        ▼
                        │  ┌──────────────┐       ┌────────────────┐
                        │  │ Tool Registry│       │ Recovery Layer │
                        │  │ load_csv     │       │ classify err   │
                        │  │ fetch_api ⚠  │──err─▶│ retry/replan/  │
                        │  │ normalize_tz │       │ degrade        │
                        │  │ match_records│       └────────────────┘
                        │  │ classify_dis.│
                        │  │ propose_corr.│
                        │  │ apply_corr.  │──ledger──▶ corrections.jsonl
                        │  │ verify_recon.│
                        │  └──────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │  LLM Router          │
              │  + Cost Tracker      │       ┌──────────────────────┐
              │                      │──opt──▶│ Shadow Runner        │
              │  Gemini 2.5 Pro      │ flag  │ (Plan: Gem-Pro vs    │
              │  Gemini 2.5 Flash    │       │  GPT-4o in parallel) │
              │  GPT-4o-mini         │       └─────────┬────────────┘
              │  GPT-4o (shadow)     │                 │
              └──────────────────────┘                 ▼
                                              ┌──────────────────────┐
                                              │ shadow.jsonl  ──┐    │
                                              │                 ▼    │
                                              │ Comparison Reporter  │
                                              │ (paired bootstrap,   │
                                              │  p-values, 95% CI)   │
                                              └──────────────────────┘

              ┌──────────────────────┐       ┌──────────────────────┐
              │  Budget Enforcer     │       │  Observability       │
              │  tokens/time/calls/  │       │  Rich live dashboard │
              │  fails/cost(INR)     │       │  structlog JSONL log │
              └──────────────────────┘       └──────────────────────┘
```

**Key commitments:**

- **One loop, four named-class phases.** `Phase.PLAN`, `Phase.ACT`, `Phase.OBSERVE`, `Phase.DECIDE` are `Enum` values. Each phase is a class in `src/recon_agent/agent/phases.py` with a `run(state) -> PhaseOutput` method.
- **Two providers used deliberately.** Gemini for reasoning (Plan/Decide/summary). OpenAI for cheap structured classification + shadow comparison.
- **Ledger is the only mutation point in the entire system.** All other persistence is append-only logs.
- **Shadow Runner wraps the router**; loop doesn't know shadow exists.
- **Recovery is its own layer.** Loop only sees "success" or "recovery decision".
- **Budget checked first** every iteration.
- **Snapshot per step** to `reports/run_<ts>/step_<n>.json` — versioned state on disk.

**Module count:** 7 source subpackages + 1 GitHub Actions workflow. Single agent. No framework. Raw SDKs.

---

## 3. Agent loop and state model

### 3.1 Phase enum (`src/recon_agent/agent/phases.py`)

```python
class Phase(str, Enum):
    PLAN    = "PLAN"
    ACT     = "ACT"
    OBSERVE = "OBSERVE"
    DECIDE  = "DECIDE"
    HALT    = "HALT"   # terminal, never re-entered
```

`Phase.HALT` is the only terminal phase.

### 3.2 AgentState (`src/recon_agent/agent/state.py`)

The Pydantic v2 model that holds the agent's entire working memory. Updated only via `state.apply(decision)`, which bumps `version` atomically.

```python
SCHEMA_VERSION = 1   # bump if AgentState shape changes; snapshots embed this

class ToolCallRecord(BaseModel):
    step:        int
    tool_name:   str
    args:        dict
    started_at:  datetime
    finished_at: datetime
    latency_ms:  int
    outcome:     Literal["ok", "error", "recovered"]
    error_kind:  Literal["transient", "persistent", "fatal", None] = None
    error_code:  str | None = None
    cost_inr:    float = 0.0

class LLMCallRecord(BaseModel):
    step:         int
    phase:        Phase
    provider:     str             # "gemini" | "openai"
    model:        str             # "gemini-2.5-pro" | "gpt-4o-mini" | ...
    subtask:      str             # "plan" | "decide" | "classify" | "summary" | "shadow_plan"
    tokens_in:    int
    tokens_out:   int
    latency_ms:   int
    cost_inr:     float
    cache_hit:    bool = False    # cassette replay sets this True

class Discrepancy(BaseModel):
    txn_id:      str
    kind:        Literal["missing_in_api", "missing_in_csv", "value_mismatch",
                         "duplicate", "timezone_shift", "encoding_corruption"]
    csv_record:  dict | None
    api_record:  dict | None
    severity:    Literal["low", "medium", "high"]
    confidence:  float           # 0..1

class CorrectionProposal(BaseModel):
    txn_id:     str
    field:      str
    old_value:  object
    new_value:  object
    reason:     str
    confidence: float

class AgentState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    version:        int = 0          # incremented on every state.apply()
    run_id:         str              # ISO timestamp
    task_brief:     str

    current_phase:  Phase = Phase.PLAN
    step:           int = 0
    started_at:     datetime
    last_decision_reasoning: str = ""

    csv_loaded:        bool = False
    api_loaded:        bool = False
    txns_csv:          list[dict] = Field(default_factory=list)
    txns_api:          list[dict] = Field(default_factory=list)
    timezone_normalized: bool = False
    matches:           list[dict] = Field(default_factory=list)
    discrepancies:     list[Discrepancy] = Field(default_factory=list)
    proposals:         list[CorrectionProposal] = Field(default_factory=list)
    corrections_applied: int = 0

    tool_calls:    list[ToolCallRecord] = Field(default_factory=list)
    llm_calls:     list[LLMCallRecord] = Field(default_factory=list)
    consecutive_failures: int = 0
    halt_reason:   str | None = None

    def is_terminal(self) -> bool:
        return self.current_phase == Phase.HALT

    def apply(self, decision: "DecideOutput") -> None:
        self.version += 1
        self.step    += 1
        self.current_phase            = decision.next_phase
        self.last_decision_reasoning  = decision.reasoning
        if decision.next_phase == Phase.HALT:
            self.halt_reason = decision.halt_reason

    def snapshot_to_disk(self, run_dir: Path) -> None:
        path = run_dir / f"step_{self.step:03d}.json"
        path.write_text(self.model_dump_json(indent=2))
```

### 3.3 Phase output contracts

```python
class PlanOutput(BaseModel):
    intended_tool:  str
    tool_args:      dict
    reasoning:      str
    estimated_cost_inr: float
    llm_call:       LLMCallRecord

class ActOutput(BaseModel):
    tool_name:      str
    tool_input:     dict
    tool_output:    dict | None
    error:          "ToolError | None"
    raw_record:     ToolCallRecord

class ObserveOutput(BaseModel):
    summary:        str
    state_patches:  dict
    discrepancies_found: int = 0
    correction_made:     bool = False

class DecideOutput(BaseModel):
    next_phase:      Phase
    halt_reason:     str | None = None
    reasoning:       str
    llm_call:        LLMCallRecord
    recovery_invoked: bool = False
```

### 3.4 AgentLoop (`src/recon_agent/agent/loop.py`)

Full body, ~80 lines:

```python
class AgentLoop:
    def __init__(self, task, tools, budget, llm_router, recovery, logger, run_dir):
        self.state    = AgentState(run_id=..., task_brief=task, started_at=...)
        self.tools    = tools
        self.budget   = budget
        self.router   = llm_router
        self.recovery = recovery
        self.logger   = logger
        self.run_dir  = run_dir

    def run(self) -> ReconciliationReport:
        self.state.snapshot_to_disk(self.run_dir)    # step_000.json = initial
        while not self.state.is_terminal():
            breach = self.budget.check(self.state)
            if breach:
                self._halt(f"budget breach: {breach}")
                break

            plan_out = Plan(self.router, self.logger).run(self.state)
            self.state.llm_calls.append(plan_out.llm_call)

            act_out = Act(self.tools, self.logger).run(plan_out, self.state)
            self.state.tool_calls.append(act_out.raw_record)

            if act_out.error:
                rec_decision = self.recovery.handle(act_out.error, self.state)
                if rec_decision.kind == "retry":
                    act_out = rec_decision.new_act_output
                elif rec_decision.kind == "replan":
                    self.state.consecutive_failures += 1
                    self.state.apply(DecideOutput(
                        next_phase=Phase.PLAN,
                        reasoning=f"recovery=replan: {rec_decision.reason}",
                        recovery_invoked=True,
                        llm_call=rec_decision.llm_call,
                    ))
                    self.state.snapshot_to_disk(self.run_dir)
                    continue
                elif rec_decision.kind == "degrade":
                    self._halt(f"graceful degrade: {rec_decision.reason}")
                    break

            obs_out = Observe(self.logger).run(act_out, self.state)
            self.state.discrepancies.extend(...)

            dec_out = Decide(self.router, self.logger).run(obs_out, self.state)
            self.state.llm_calls.append(dec_out.llm_call)
            self.state.consecutive_failures = 0

            self.state.apply(dec_out)
            self.state.snapshot_to_disk(self.run_dir)

        return self._build_report()
```

### 3.5 Terminal conditions

| Termination | Trigger | `halt_reason` |
|---|---|---|
| Goal achieved | Decide emits `next_phase=HALT, halt_reason="reconciliation complete"` | `"reconciliation complete"` |
| Goal impossible | Decide emits HALT after detecting irreconcilable data | `"irreconcilable: <details>"` |
| Budget breach | `budget.check()` returns a Breach | `"budget breach: tokens"` (etc.) |
| Recovery=degrade | Recovery layer chose graceful degradation | `"graceful degrade: <code>"` |
| Consecutive fail ceiling | Caught by budget check via `consecutive_failures` |  |

There is no other way out. All exceptions are caught and route through `_halt()`.

---

## 4. Tool registry + 8 tool specs

### 4.1 Base contract (`src/recon_agent/tools/base.py`)

```python
class ToolError(BaseModel):
    kind:      Literal["transient", "persistent", "fatal"]
    code:      str
    message:   str
    retriable: bool

class ToolResult(BaseModel, Generic[OUT]):
    ok:     bool
    output: OUT | None = None
    error:  ToolError | None = None

class Tool(ABC, Generic[IN, OUT]):
    name:             str
    input_schema:     type[IN]
    output_schema:    type[OUT]
    timeout_seconds:  float = 30.0
    cost_estimate_inr: float = 0.0

    @abstractmethod
    def run(self, inputs: IN) -> ToolResult[OUT]: ...

    def describe(self) -> dict:
        return {
            "name": self.name,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
            "cost_estimate_inr": self.cost_estimate_inr,
            "timeout_seconds": self.timeout_seconds,
        }
```

### 4.2 Registry (`src/recon_agent/tools/registry.py`)

Auto-discovers `.py` files in `src/recon_agent/tools/` that define a `Tool` subclass. Adding a new tool = drop file + restart. The deep-dive's "add a tool on the spot" stress test is ~3 minutes.

```python
class ToolRegistry:
    _tools: dict[str, Tool] = {}

    @classmethod
    def register(cls, tool: Tool) -> None: ...

    @classmethod
    def discover(cls) -> None:
        """Auto-import every .py in src/recon_agent/tools/ that defines a Tool subclass."""

    @classmethod
    def get(cls, name: str) -> Tool: ...

    @classmethod
    def available(cls, disabled: set[str] = ()) -> list[Tool]: ...

    @classmethod
    def schemas_for_llm(cls, disabled: set[str] = ()) -> list[dict]: ...
```

### 4.3 The 8 tools

| # | Tool | Purpose | Cost ₹ | Timeout |
|---|---|---|---|---|
| 1 | `load_csv` | Read CSV with encoding detection | 0.00 | 5s |
| 2 | `fetch_api` ⚠ | Fetch JSON; **30% transient failure** | 0.00 | 10s |
| 3 | `normalize_timezone` | IST↔UTC; detect IST-stored-as-UTC | 0.00 | 5s |
| 4 | `match_records` | Pair CSV vs API by txn_id + fuzzy | 0.00 | 10s |
| 5 | `classify_discrepancy` | LLM (GPT-4o-mini) | ~0.05/call | 15s |
| 6 | `propose_correction` | LLM (Gemini Flash) | ~0.10/call | 15s |
| 7 | `apply_correction` | Append to `corrections.jsonl` | 0.00 | 2s |
| 8 | `verify_reconciliation` | Re-match post-correction | 0.00 | 5s |

**Detailed schemas:**

```python
# Tool 1: load_csv
class LoadCSVInput(BaseModel):
    path: str
    expected_columns: list[str] | None = None
class LoadCSVOutput(BaseModel):
    rows: list[dict]
    detected_encoding: str
    row_count: int
    skipped_rows: int
# Errors: FILE_NOT_FOUND (fatal), MALFORMED_CSV (persistent), ENCODING_AMBIGUOUS (persistent)

# Tool 2: fetch_api  ⚠️ unreliable
class FetchAPIInput(BaseModel):
    endpoint: Literal["payu_settlements"]
    limit: int = 1000
class FetchAPIOutput(BaseModel):
    records: list[dict]
    pulled_at: datetime
    next_cursor: str | None
# Errors: RATE_LIMIT (transient, 30% inject rate), API_5XX (transient, 2%),
#         API_AUTH (fatal, 0.1%), API_NOT_FOUND (persistent, on --disable)

# Tool 3: normalize_timezone
class NormalizeTZInput(BaseModel):
    records: list[dict]
    timestamp_field: str = "timestamp"
    target_tz: Literal["UTC"] = "UTC"
class NormalizeTZOutput(BaseModel):
    records: list[dict]
    suspected_ist_as_utc: list[str]
    converted_count: int
# Errors: MISSING_FIELD (persistent), UNPARSEABLE_TIMESTAMP (persistent)

# Tool 4: match_records
class MatchRecordsInput(BaseModel):
    csv_records: list[dict]
    api_records: list[dict]
    key_field: str = "txn_id"
    fuzzy: bool = True
class MatchRecordsOutput(BaseModel):
    matched: list[dict]
    unmatched_csv: list[dict]
    unmatched_api: list[dict]
    value_conflicts: list[dict]
# Errors: EMPTY_INPUT (persistent)

# Tool 5: classify_discrepancy (LLM-backed)
class ClassifyDiscrepancyInput(BaseModel):
    unmatched_csv: list[dict]
    unmatched_api: list[dict]
    value_conflicts: list[dict]
    timezone_suspects: list[str]
class ClassifyDiscrepancyOutput(BaseModel):
    classified: list[Discrepancy]
# Errors: LLM_RATE_LIMIT (transient), LLM_TIMEOUT (transient), LLM_BAD_OUTPUT (persistent)

# Tool 6: propose_correction (LLM-backed)
class ProposeCorrectionInput(BaseModel):
    discrepancy: Discrepancy
class ProposeCorrectionOutput(BaseModel):
    proposal: CorrectionProposal
    fallback: str | None
# Errors: same as classify

# Tool 7: apply_correction
class ApplyCorrectionInput(BaseModel):
    proposal: CorrectionProposal
    ledger_path: str = "corrections.jsonl"
class ApplyCorrectionOutput(BaseModel):
    line_number: int
    applied_at: datetime
    skipped_reason: str | None
# Errors: LEDGER_WRITE_FAILED (fatal), LOW_CONFIDENCE (persistent)

# Tool 8: verify_reconciliation
class VerifyInput(BaseModel):
    csv_records: list[dict]
    api_records: list[dict]
    ledger_path: str = "corrections.jsonl"
class VerifyOutput(BaseModel):
    residual_discrepancies: list[Discrepancy]
    reconciliation_rate: float
    summary: str
```

### 4.4 Failure injection

```
--seed <int>              # controls fetch_api RNG
--disable-tool <name>     # filters tool out of registry
--fail-tool <name>:<code> # forces tool to always return that error
--seed-fail-rate <float>  # overrides fetch_api's 30% rate
```

---

## 5. LLM router + cost tracking + shadow + statistical comparison

### 5.1 Router interface (`src/recon_agent/llm/router.py`)

Single entry point for every LLM call in the system:

```python
class LLMRouter:
    def call(
        self,
        subtask:         str,           # "plan" | "decide" | "classify" | "summary" | "shadow_plan"
        messages:        list[dict],
        response_schema: type[BaseModel],
        timeout_s:       float = 30,
        step:            int = 0,
        phase:           Phase = Phase.PLAN,
    ) -> tuple[BaseModel, LLMCallRecord]:
        """Returns (parsed_output, call_record). Validates against schema.
        Raises LLMError on failure."""
```

### 5.2 Provider adapters (`src/recon_agent/llm/providers.py`)

Two stateless functions. Both return the same `RawLLMResponse` shape; router doesn't branch on provider downstream.

```python
def gemini_call(model, messages, response_schema, timeout_s) -> RawLLMResponse:
    """google-genai SDK. response_mime_type='application/json' + response_schema=<pydantic>."""

def openai_call(model, messages, response_schema, timeout_s) -> RawLLMResponse:
    """openai SDK. response_format={'type': 'json_schema', 'strict': True}."""
```

### 5.3 Routing table

| Subtask | Provider | Model | Rationale |
|---------|----------|-------|-----------|
| `plan` | gemini | gemini-2.5-pro | Reasoning-heavy. Drives every iteration. |
| `decide` | gemini | gemini-2.5-pro | Same reasoning bar; amortizes Gemini client. |
| `classify` | openai | gpt-4o-mini | Cheap structured output, high volume. |
| `summary` | gemini | gemini-2.5-flash | One call, natural-language, cheap. |
| `shadow_plan` | openai | gpt-4o | Apples-to-apples comparison vs Gemini Pro. |

### 5.4 Pricing (`src/recon_agent/llm/pricing.py`)

```python
USD_TO_INR = 83.0

PRICING = {
    "gemini-2.5-pro":    ModelPrice(input=1.25,  output=5.00),
    "gemini-2.5-flash":  ModelPrice(input=0.075, output=0.30),
    "gpt-4o":            ModelPrice(input=2.50,  output=10.00),
    "gpt-4o-mini":       ModelPrice(input=0.15,  output=0.60),
}

def cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING[model]
    usd = (tokens_in / 1_000_000) * p.input + (tokens_out / 1_000_000) * p.output
    return round(usd * USD_TO_INR, 4)
```

Every `LLMCallRecord` lands with `cost_inr` populated. Aggregations: total ₹/run, per-subtask ₹, per-provider ₹, per-model ₹.

### 5.5 Cassette layer (`src/recon_agent/llm/cassettes.py`)

Three modes: `live`, `record`, `replay`. Controlled by `LLM_MODE` env var or `--llm-mode` flag.

| Mode | Pre-call | Post-call |
|------|----------|-----------|
| `live` | none | none |
| `record` | none (always hit API) | `cassettes.put(hash, response)` |
| `replay` | `cassettes.get(hash)` — hit returns it; **no API call**; `cache_hit=True` | none |

Cassette miss in replay raises `CassetteMiss` with clear message. Never falls through to live.

Hash inputs: provider, model, subtask, messages (normalized), response_schema (JSON-schema dump).

Cassettes live in `evals/cassettes/<scenario>.jsonl`, committed to git.

### 5.6 Shadow Runner (`src/recon_agent/llm/shadow.py`)

Wraps the router for Plan phase only. Off by default. When on:
- Parallel calls: primary (Gemini Pro) + secondary (GPT-4o)
- Primary's output feeds the loop
- Secondary logged to `reports/run_<ts>/shadow.jsonl`
- Both `LLMCallRecord`s appended to `state.llm_calls`

### 5.7 Statistical comparison (`src/recon_agent/llm/comparison.py`)

Paired bootstrap, 10k resamples, seeded for reproducibility:

```python
def compare_configs(
    config_a_results: list[ScenarioResult],
    config_b_results: list[ScenarioResult],
    n_resamples: int = 10_000,
) -> ComparisonReport:
    """Per-scenario delta in pass-rate. 95% CI + two-sided p-value."""
```

Output: `reports/shadow_comparison_<ts>.md` with the per-scenario table, aggregate pass rates, p-value, and verdict.

---

## 6. Recovery, Budget, Observability

### 6.1 Error classifier (`src/recon_agent/recovery/classifier.py`)

```python
class RecoveryAction(BaseModel):
    kind:       Literal["retry", "replan", "degrade"]
    reason:     str
    backoff_ms: int = 0
    hint:       str = ""

class ErrorClassifier:
    def classify(self, error: ToolError, state: AgentState) -> RecoveryAction:
        retries_so_far = self._count_recent_retries(state, error.code)

        # transient: retry with backoff up to N times
        if error.kind == "transient" and retries_so_far < MAX_RETRIES:
            backoff = self._backoff_with_jitter(attempt=retries_so_far)
            return RecoveryAction(kind="retry", reason=f"transient {error.code}", backoff_ms=backoff)

        # transient that exhausted retries → escalates to persistent
        if error.kind == "transient" and retries_so_far >= MAX_RETRIES:
            return RecoveryAction(kind="replan",
                                  reason=f"transient {error.code} survived {MAX_RETRIES} retries",
                                  hint=self._alternative_hint(error, state))

        # persistent: re-plan with hint
        if error.kind == "persistent":
            return RecoveryAction(kind="replan", reason=f"persistent {error.code}",
                                  hint=self._alternative_hint(error, state))

        # fatal OR repeated_failure: degrade
        if error.kind == "fatal" or state.consecutive_failures >= 3:
            return RecoveryAction(kind="degrade", reason=f"fatal {error.code}")

        return RecoveryAction(kind="degrade", reason="unclassified error path")
```

### 6.2 Error → strategy table

| Error code | Kind | First strategy | If retries exhausted |
|---|---|---|---|
| RATE_LIMIT (429) | transient | retry w/ exp backoff | replan ("API rate-limited, try cached") |
| API_5XX | transient | retry w/ exp backoff | replan |
| API_TIMEOUT | transient | retry once | replan |
| API_NOT_FOUND (404) | persistent | **replan immediately** (no retry) | — |
| API_AUTH (401/403) | fatal | **degrade immediately** | — |
| MALFORMED_CSV | persistent | replan ("try encoding=latin-1") | — |
| FILE_NOT_FOUND | fatal | degrade | — |
| LLM_RATE_LIMIT | transient | retry w/ backoff | replan ("switch to cheaper model") |
| LLM_BAD_OUTPUT | persistent | retry once with stricter prompt | replan |
| LEDGER_WRITE_FAILED | fatal | degrade | — |
| LOW_CONFIDENCE | persistent | replan ("request manual review") | — |

This table goes verbatim into `docs/recovery_strategies.md` and the README.

### 6.3 Strategy implementations (`src/recon_agent/recovery/strategies.py`)

Three function-objects. RetryWithBackoff (re-runs same tool). ReplanWithAlternativeTool (jumps to PLAN with hint). GracefulDegrade (emits HALT with partial report).

### 6.4 Budget (`src/recon_agent/agent/budget.py`)

```python
class Budget(BaseModel):
    max_tokens:               int   = 100_000
    max_wall_clock_s:         float = 600
    max_tool_calls:           int   = 60
    max_consecutive_failures: int   = 5
    max_cost_inr:             float = 50.0

class Breach(BaseModel):
    dim:        str
    observed:   float
    limit:      float
    message:    str
```

Checked at top of every iteration. Breach → `PARTIAL_REPORT.md` written → exit code 2. All CLI-overridable.

### 6.5 Observability

Three layers:

1. **Rich live dashboard** (`src/recon_agent/observability/dashboard.py`) — `rich.live.Live`, 100ms refresh. Shows phase, last 5 tool calls, budget bars, last Decide reasoning.
2. **Structured JSONL log** (`reports/run_<ts>/log.jsonl`) — one event per line via `structlog.JSONRenderer`. Every phase enter/exit, tool call, LLM call, recovery decision, budget check.
3. **Step snapshots** (`reports/run_<ts>/step_<n>.json`) — full `AgentState` per step. Reviewer can `diff` consecutive snapshots to see one iteration's changes.

Plus the final `report.md` with status, findings, corrections, telemetry, per-subtask cost.

---

## 7. Mock fixtures, ground truth, ledger

### 7.1 CSV schema (`fixtures/tracking_db.csv`)

Columns: `txn_id`, `redemption_ts` (IST), `merchant`, `merchant_category`, `deal_id`, `coupon_code`, `order_value_inr`, `discount_inr`, `user_id`, `channel`.

### 7.2 JSON schema (`fixtures/payu_settlements.json`)

PayU-shaped response: `page`, `page_size`, `total`, `next_cursor`, `records[]`. Each record: `settlement_id`, `reference_id` (= csv.txn_id), `settled_at` (claims UTC), `payee`, `gross_amount`, `net_amount`, `settlement_status`.

### 7.3 Realistic data

| Category | Merchants | Amount range (₹) | Mean |
|---|---|---|---|
| Fashion | Myntra, Ajio, Puma, Nykaa | 500-5000 | 1,800 |
| Travel | MakeMyTrip, Goibibo, Cleartrip, Uber | 1000-15000 | 4,500 |
| Food | Zomato, Swiggy, BigBasket | 150-800 | 400 |
| Electronics | Amazon, Flipkart, Croma, BoAt | 1000-50000 | 6,000 |
| Health | PharmEasy, Mamaearth, Lenskart | 200-2000 | 800 |

Coupon pool: `FLAT200, SAVE40, NEW100, WELCOME, MEGA50, WEEKEND, RAKHI25, DIWALI60, MONDAY10, CRED50`.

Indian-business-hours-biased timestamps.

### 7.4 Defect injection (default variant, 500 txns)

| Defect kind | Rate | Count | Injection |
|---|---|---|---|
| value_mismatch | 3% | 15 | API.gross_amount rounded to nearest ₹10 |
| timezone_shift | 5% | 25 | API.settled_at claims +00:00 but value is IST |
| duplicate | 2% | 10 | CSV row written twice, slightly different ts |
| missing_in_api | 2% | 10 | CSV has it, API omits |
| missing_in_csv | 0.5% | 3 | API has it, CSV omits |
| encoding_corruption | 1% | 5 | CSV merchant name is double-encoded |
| clean | 86.5% | 432 | — |

### 7.5 Fixture variants

| Variant | Used by scenario | Purpose |
|---|---|---|
| `happy_clean` | happy_01 | 0 defects |
| `tz_only` | happy_02 | only timezone |
| `encoding_only` | happy_03 | only encoding |
| `duplicate_only` | happy_04 | only duplicates |
| `value_only` | happy_05 | only value mismatches |
| `default` | recovery_01/02, budget_01/02 | full mix |
| `default_disabled_api` | recovery_03 | full mix + --disable-tool fetch_api |
| `default_latin1_csv` | recovery_02 | CSV written in latin-1 |
| `corrupted_source` | impossible_01 | CSV is binary garbage |
| `irreconcilable` | impossible_02 | 0 shared txn_ids |

### 7.6 Ground truth format

`src/recon_agent/data/ground_truth_<variant>.json`:

```json
{
  "fixture_seed": 42,
  "variant": "default",
  "total_txns": 500,
  "expected_summary": {
    "value_mismatch": 15, "timezone_shift": 25, "duplicate": 10,
    "missing_in_api": 10, "missing_in_csv": 3, "encoding_corruption": 5,
    "_total": 68
  },
  "injected": [ { "txn_id": ..., "kind": ..., "csv": ..., "api": ..., "expected_correction": {...} } ]
}
```

### 7.7 Corrections ledger format

`reports/run_<ts>/corrections.jsonl`, one JSON object per line, append-only:

```jsonl
{"txn_id":"TX-2026-00042","kind":"value_mismatch","field":"order_value_inr","old":2500.00,"new":2499.00,"reason":"rounding","confidence":0.97,"applied_at":"...","by":"agent-v1","step":12,"action":"applied"}
```

`action`: `"applied"` (confidence ≥ 0.7) or `"skipped"` (low_confidence). Ledger is per-run, inside `reports/run_<ts>/`.

### 7.8 Eval verification (`evals/verify.py`)

Five orthogonal checks; scenario passes only if all five pass.

1. Status check (against `expected.status`)
2. Discrepancy count check (with per-kind tolerance)
3. Correction coverage (`applied_ids ∩ expected_ids / expected_ids`)
4. Recovery-invoked check (against `expected.recovery_invoked`)
5. Cost check (`total_cost_inr ≤ expected.max_cost_inr`)

---

## 8. Eval framework + 12 scenarios + CI gate

### 8.1 Scenario shape (`evals/scenarios/base.py`)

```python
class Scenario(BaseModel):
    name:               str
    fixture_variant:    str
    fixture_seed:       int
    cli_args:           list[str] = []
    tool_overrides:     list[ToolOverride] = []
    budget_overrides:   BudgetOverride | None = None
    expected:           Expected
    cassette_file:      Path
    timeout_s:          int = 120
```

### 8.2 The 12 scenarios (full specs in `evals/scenarios/*.py`)

**Happy path:** happy_01_clean_reconciliation, happy_02_minor_timezone, happy_03_encoding, happy_04_duplicates, happy_05_value_mismatch.

**Recovery:** recovery_01_api_429 (high failure rate), recovery_02_malformed_csv (latin-1 source), recovery_03_tool_disabled (--disable-tool fetch_api).

**Budget:** budget_01_token_ceiling (max_tokens=2000), budget_02_walltime_ceiling (max_wall_clock_s=5).

**Impossible:** impossible_01_corrupted_source (binary garbage CSV), impossible_02_irreconcilable (0 shared txn_ids).

Each scenario file exports `SCENARIO: Scenario` with full `Expected` block.

### 8.3 Runner (`evals/runner.py`)

Discovers scenarios by glob, runs each, verifies, writes `reports/eval_<ts>/results.{json,md}`, exits 0 on all-pass else 1.

### 8.4 Cassette workflow

```makefile
eval:      LLM_MODE=replay  python -m evals.runner   # ~30s, free
eval-live: LLM_MODE=record  python -m evals.runner   # ~5min, ~₹52
```

### 8.5 Shadow comparison (`make eval-compare`)

Runs evals twice (Plan = Gemini Pro, Plan = GPT-4o), produces `reports/shadow_comparison_<ts>.md` with paired bootstrap.

### 8.6 CI gate (`.github/workflows/eval.yml`)

Triggers on PR + push to main. Runs `make eval` in replay mode (no API keys). Posts pass/fail PR comment. Blocks merge on any scenario failure. Compares against `evals/baselines/main.json`.

---

## 9. Repo layout, CLI, Makefile

### 9.0 Full directory tree

```
recon-agent/
├── README.md                              # architecture doc
├── BRAINSTORMING_LOG.md                   # running Q&A log
├── LOOM_SCRIPT.md                         # video script
├── DEEP_DIVE_PREP.md                      # interview prep
├── LICENSE                                # MIT
├── pyproject.toml                         # project metadata + deps + console scripts
├── .env.example
├── .gitignore
├── Makefile
│
├── .github/workflows/eval.yml             # CI gate
│
├── src/recon_agent/
│   ├── __init__.py
│   ├── __main__.py                        # `python -m recon_agent` → CLI
│   ├── agent/
│   │   ├── loop.py                        # AgentLoop
│   │   ├── phases.py                      # Phase enum + Plan/Act/Observe/Decide classes
│   │   ├── state.py                       # AgentState + snapshotting
│   │   ├── budget.py
│   │   └── prompts/
│   │       ├── plan_system.txt
│   │       ├── decide_system.txt
│   │       ├── classify_discrepancy.txt
│   │       └── propose_correction.txt
│   ├── tools/
│   │   ├── base.py                        # Tool ABC, ToolResult, ToolError
│   │   ├── registry.py                    # ToolRegistry
│   │   ├── load_csv.py
│   │   ├── fetch_api.py                   # the unreliable one
│   │   ├── normalize_timezone.py
│   │   ├── match_records.py
│   │   ├── classify_discrepancy.py
│   │   ├── propose_correction.py
│   │   ├── apply_correction.py
│   │   └── verify_reconciliation.py
│   ├── llm/
│   │   ├── router.py
│   │   ├── providers.py                   # gemini_call(), openai_call()
│   │   ├── pricing.py
│   │   ├── cassettes.py
│   │   ├── shadow.py
│   │   └── comparison.py
│   ├── recovery/
│   │   ├── __init__.py                    # RecoveryLayer
│   │   ├── classifier.py
│   │   └── strategies.py
│   ├── observability/
│   │   ├── logger.py
│   │   └── dashboard.py                   # Rich live dashboard
│   ├── data/
│   │   ├── generate_fixtures.py
│   │   ├── fixtures/                      # generated at runtime, gitignored
│   │   └── ground_truth_*.json            # one per variant, committed
│   └── cli/
│       ├── demo.py                        # `recon demo`
│       ├── eval.py
│       └── shared.py
│
├── evals/
│   ├── runner.py
│   ├── compare.py
│   ├── compare_baseline.py                # CI regression check
│   ├── verify.py
│   ├── report.py
│   ├── scenarios/                         # 12 scenario .py files
│   ├── cassettes/                         # 12 .jsonl files, committed
│   └── baselines/main.json
│
├── reports/                               # runtime output; gitignored
│   └── .gitkeep
│
├── docs/
│   ├── architecture.md
│   ├── model_routing.md
│   ├── recovery_strategies.md
│   └── superpowers/specs/
│       └── 2026-05-23-recon-agent-design.md   # this file
│
└── tests/
    ├── unit/                              # ~10 unit test files
    └── integration/                       # 2 integration tests
```

**Counts:** 7 source subpackages, 8 tools, 12 eval scenarios, 1 GitHub Action, ~50 Python files total.

### 9.0.1 pyproject.toml essentials

```toml
[project]
name = "recon-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "google-genai>=1.0",
    "openai>=1.50",
    "pydantic>=2.7",
    "structlog>=24.1",
    "rich>=13.7",
    "python-dotenv>=1.0",
    "chardet>=5.2",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.5", "mypy>=1.10"]

[project.scripts]
recon = "recon_agent.__main__:main"
```

**Deliberate non-deps:** no LangChain, no CrewAI, no Pydantic-AI, no Instructor. Raw SDKs only.

### 9.1 CLI flags (recon demo)

Input: `--task`, `--fixture-variant`, `--fixture-seed`.
Tool control: `--disable-tool`, `--fail-tool`, `--seed-fail-rate`.
Budget: `--budget-tokens`, `--budget-time`, `--budget-calls`, `--budget-fails`, `--budget-cost`.
LLM: `--llm-mode`, `--shadow`.
Output: `--no-dashboard`, `--run-dir`, `-v`/`-q`.

### 9.2 Setup contract

```bash
git clone ... && cd recon-agent
make setup           # ~90s
$EDITOR .env         # add GEMINI_API_KEY + OPENAI_API_KEY
make eval            # ~30s, 12/12 PASS
make demo            # ~45s live run
```

Total: ~3-4 minutes. Well under the brief's 15-minute requirement.

### 9.3 What's deliberately NOT here

No Docker, no frontend, no database, no `requirements.txt`, no LangChain/CrewAI/Pydantic-AI/Instructor. Tight, focused, defensible.

---

## 10. README outline

Sections in order: (a) what+why, (b) architecture, (c) per-module decisions, (d) how to run, (e) eval results, (f) what broke first, (g) what I'd change with 2 more weeks, (h) model routing table, (i) eval design rationale, (j) cost data, (k) operations cheatsheet.

Target length: 1,500-2,500 words. No emojis except a CI badge. Every claim has a file path.

---

## 11. Loom video script

See `LOOM_SCRIPT.md` — separate file. Four scenes: happy path (3-5 min), failure recovery (3-5 min), architecture walkthrough (4-6 min), eval + comparison (2-3 min). Total ~12-19 min, inside the 15-20 min window.

---

## 12. Cost model

**Per agent run (live, 500 txns, no shadow):** ~₹4.34 (~$0.052)
**Per agent run (live, --shadow):** ~₹8.96 (~$0.11)
**Per eval-live run (re-record 12 scenarios):** ~₹52 (~$0.63)
**Per eval-compare run (2 × 12 scenarios):** ~₹104 (~$1.26)
**Per eval-replay run:** ₹0
**Total dev cost estimate:** ~₹585 (~$7)

Fits within free tiers (Gemini AI Studio + OpenAI signup credits).

---

## 13. Submission checklist

- [ ] Public GitHub repo
- [ ] README sections (a-k) complete; especially (f) with real story
- [ ] `evals/baselines/main.json` + latest `reports/eval_*/results.md` committed
- [ ] `reports/shadow_comparison_*.md` committed
- [ ] Cost table populated with real numbers
- [ ] Cassettes committed for all 12 scenarios
- [ ] CI green
- [ ] Loom 15-20 min with audio, unlisted link
- [ ] Resume PDF separate
- [ ] Email to `careers@grabon.in`, subject `AI Labs - <Name> - Assignment 02`

---

## 14. Projected score

| Dimension | Wt | Expected |
|-----------|----|----|
| Agent Architecture | 25% | 5/5 |
| Eval Rigor | 20% | 4-5/5 |
| Failure Recovery & Production | 20% | 5/5 |
| Multi-LLM & Cost | 15% | 4/5 |
| Code & README | 20% | 5/5 |
| **Total** | | **~92-94%** |

High execution confidence.

---

**Spec status:** Approved, ready for implementation plan.
**Next:** invoke `writing-plans` skill to produce the phase-by-phase build plan (no day-by-day calendar).
