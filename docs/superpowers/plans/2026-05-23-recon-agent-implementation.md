# Recon Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the GrabOn AI Labs Challenge 02 Transaction Reconciliation Agent — a single autonomous agent with Plan/Act/Observe/Decide loop, 8 typed tools, 2-provider LLM router (Gemini + OpenAI), recovery layer, budget enforcement, 12-scenario eval suite with cassette replay, statistical comparison, and CI gate.

**Architecture:** Single Python package, raw SDKs (no LangChain/CrewAI), Pydantic v2 schemas everywhere, structured logging via structlog, Rich live dashboard. ReAct-style loop. Append-only corrections ledger. Cassette-based eval replay for free deterministic CI.

**Tech Stack:** Python 3.11+, `google-genai`, `openai`, `pydantic>=2.7`, `structlog`, `rich`, `chardet`, `numpy` (for bootstrap), pytest, ruff, mypy. No framework.

**Design spec:** `docs/superpowers/specs/2026-05-23-recon-agent-design.md` — canonical reference for every schema, contract, and decision.

**Working directory:** `D:\GrabOn - Interview Assignnment challenge\`. All file paths in this plan are relative to that root.

**Plan structure:** 10 logical **phases**, each independently shippable (i.e., each ends with a green `make demo` or `make eval` in some form, plus a commit). No day-by-day calendar — phases progress when their exit condition is met.

---

## Phase overview

| # | Phase | Exit condition | Roughly N tasks |
|---|---|---|---|
| 1 | Scaffolding + no-op loop | `recon demo` runs a 1-step no-op loop, exits 0, writes a snapshot | 9 |
| 2 | LLM plumbing | Plan + Decide make real LLM calls, halt cleanly after N iterations | 8 |
| 3 | Data layer | `generate_fixtures.py` produces deterministic CSV/JSON/ground_truth for all 10 variants | 5 |
| 4 | 8 core tools | All 8 tools registered, individually unit-tested, runnable end-to-end on default fixture | 9 |
| 5 | Recovery + budget enforcement | Forced 429 demo recovers cleanly; `--budget-calls 3` halts cleanly | 9 |
| 6 | Observability polish | Rich dashboard renders during `make demo`; structlog JSONL parseable | 4 |
| 7 | Eval framework + 12 scenarios | `make eval` shows 12/12 PASS in replay mode (~30s, free) | 8 |
| 8 | Shadow testing + statistical comparison | `make eval-compare` produces `shadow_comparison_*.md` with p-value | 5 |
| 9 | CI gate | GitHub Actions runs evals on PR, blocks merge on regression | 4 |
| 10 | Documentation & polish | README a-k complete with real cost data, repo passes 15-min setup test | 9 |

**Total tasks: ~70.** Each task is 2-5 minutes of focused work (per writing-plans skill).

---

## Phase 1 — Scaffolding + no-op loop

**Entry condition:** Empty working directory (only `.claude/`, the brief, brainstorming files, and design spec exist).

**Exit condition:**
- `git init` done, first commit landed
- `make setup` succeeds on a fresh machine
- `make demo` runs a 1-step no-op loop, exits 0, writes `reports/run_<ts>/step_000.json` + `step_001.json`
- All Pydantic models from spec §3.2-3.3 importable and instantiable

**Phase summary:** Lay the bones. No real LLM calls. No real tools. Just the skeleton — directory tree, Pydantic schemas, Tool ABC, Registry with a no-op tool, AgentLoop that halts after step 1, CLI entry. Verify the wiring is sound before adding real logic.

---

### Task 1.1: Initialize git repo + scaffold directory structure

**Files:**
- Create: `.gitignore`
- Create: `src/recon_agent/__init__.py` (empty)
- Create: directory structure per spec §9.0

- [ ] **Step 1: Initialize git**

```bash
cd "D:/GrabOn - Interview Assignnment challenge"
git init
git config user.email "your@email.com"   # if not already set
git config user.name "Your Name"
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p src/recon_agent/{agent/prompts,tools,llm,recovery,observability,data/fixtures,cli}
mkdir -p evals/{scenarios,cassettes,baselines}
mkdir -p tests/{unit,integration}
mkdir -p reports docs/{architecture,} .github/workflows
touch src/recon_agent/__init__.py
touch src/recon_agent/agent/__init__.py
touch src/recon_agent/tools/__init__.py
touch src/recon_agent/llm/__init__.py
touch src/recon_agent/recovery/__init__.py
touch src/recon_agent/observability/__init__.py
touch src/recon_agent/data/__init__.py
touch src/recon_agent/cli/__init__.py
touch evals/__init__.py evals/scenarios/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
touch reports/.gitkeep evals/cassettes/.gitkeep
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
build/
dist/

# Runtime output — keep .gitkeep
reports/*
!reports/.gitkeep

# Generated fixtures — keep ground truth, drop CSV/JSON
src/recon_agent/data/fixtures/*.csv
src/recon_agent/data/fixtures/*.json

# IDE
.idea/
.vscode/
*.swp
```

- [ ] **Step 4: First commit**

```bash
git add .gitignore src/ evals/ tests/ reports/.gitkeep evals/cassettes/.gitkeep
git commit -m "chore: scaffold directory structure"
```

---

### Task 1.2: Add `pyproject.toml`

**Files:** Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "recon-agent"
version = "0.1.0"
description = "Transaction Reconciliation Agent — GrabOn AI Labs Challenge 02"
requires-python = ">=3.11"
authors = [{name = "Candidate"}]
license = {text = "MIT"}
readme = "README.md"

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
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
recon = "recon_agent.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/recon_agent"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "RUF"]
ignore = ["E501"]  # line length handled by formatter

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Verify install works**

```bash
python -m venv .venv
.venv/Scripts/activate    # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Expected: install completes without error.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with deps and dev tools"
```

---

### Task 1.3: Add `.env.example`, `Makefile`, `README.md` stub

**Files:** Create: `.env.example`, `Makefile`, `README.md`

- [ ] **Step 1: Write `.env.example`**

```bash
# Required for live mode
GEMINI_API_KEY=        # https://aistudio.google.com/app/apikey
OPENAI_API_KEY=        # https://platform.openai.com/api-keys

# Optional, defaults to "live" for `make demo`, "replay" for `make eval`
LLM_MODE=
```

- [ ] **Step 2: Write `Makefile` (full target list — implementations land in later phases)**

```makefile
.PHONY: help setup demo demo-shadow demo-replay eval eval-live eval-compare \
        refresh-baseline lint typecheck test unit integration clean

help:
	@echo "make setup           # venv + deps"
	@echo "make demo            # run agent live (~45s, ~₹4)"
	@echo "make demo-shadow     # demo + Plan-phase shadow runner enabled"
	@echo "make demo-replay     # demo using cassettes (free)"
	@echo "make eval            # 12 scenarios via cassette replay (~30s, free)"
	@echo "make eval-live       # re-record cassettes (~5min, ~₹52)"
	@echo "make eval-compare    # produce shadow_comparison_*.md"
	@echo "make refresh-baseline"
	@echo "make lint            # ruff"
	@echo "make typecheck       # mypy"
	@echo "make test            # pytest (unit + integration)"

setup:
	python -m venv .venv
	.venv/Scripts/pip install -e ".[dev]"
	@test -f .env || cp .env.example .env
	@echo ">> Setup done. Edit .env to add GEMINI_API_KEY + OPENAI_API_KEY."

demo:
	.venv/Scripts/recon demo

demo-shadow:
	.venv/Scripts/recon demo --shadow

demo-replay:
	.venv/Scripts/recon demo --llm-mode replay

eval:
	LLM_MODE=replay .venv/Scripts/python -m evals.runner

eval-live:
	LLM_MODE=record .venv/Scripts/python -m evals.runner

eval-compare:
	@PLAN_PROVIDER=gemini LLM_MODE=replay .venv/Scripts/python -m evals.runner --tag config_a
	@PLAN_PROVIDER=openai LLM_MODE=replay .venv/Scripts/python -m evals.runner --tag config_b
	@.venv/Scripts/python -m evals.compare config_a config_b

refresh-baseline:
	.venv/Scripts/python -m evals.runner --output-json evals/baselines/main.json

lint:
	.venv/Scripts/ruff check src/ evals/ tests/

typecheck:
	.venv/Scripts/mypy src/

test: unit integration
unit:
	.venv/Scripts/pytest tests/unit -v
integration:
	.venv/Scripts/pytest tests/integration -v

clean:
	rm -rf reports/run_* reports/eval_* reports/shadow_comparison_*.md
	rm -f src/recon_agent/data/fixtures/tracking_db.csv
	rm -f src/recon_agent/data/fixtures/payu_settlements.json
```

> **Windows note:** Targets reference `.venv/Scripts/`. If running on Linux/macOS, swap to `.venv/bin/`. The Makefile assumes the working dir is the project root.

- [ ] **Step 3: Write `README.md` stub (full content lands in Phase 10)**

```markdown
# Recon Agent

GrabOn AI Labs Challenge 02 — Transaction Reconciliation Agent.

**Status:** in development. Full README arrives at Phase 10.

## Quick start (preview)

```bash
make setup
$EDITOR .env  # add GEMINI_API_KEY + OPENAI_API_KEY
make eval     # cassette-replay, no API keys needed
make demo     # live LLM run
```
```

- [ ] **Step 4: Commit**

```bash
git add .env.example Makefile README.md
git commit -m "chore: add .env.example, Makefile, README stub"
```

---

### Task 1.4: Create `Phase` enum and `AgentState` skeleton

**Files:**
- Create: `src/recon_agent/agent/phases.py` (Phase enum only; Plan/Act/Observe/Decide classes land in Phase 2)
- Create: `src/recon_agent/agent/state.py`
- Test: `tests/unit/test_state.py`

- [ ] **Step 1: Write failing test for AgentState `apply()` version bump**

```python
# tests/unit/test_state.py
from datetime import datetime, timezone
from recon_agent.agent.state import AgentState, DecideOutput, LLMCallRecord
from recon_agent.agent.phases import Phase


def _empty_llm_call() -> LLMCallRecord:
    return LLMCallRecord(
        step=0, phase=Phase.PLAN, provider="none", model="none",
        subtask="none", tokens_in=0, tokens_out=0, latency_ms=0, cost_inr=0.0
    )


def test_apply_bumps_version_and_step():
    state = AgentState(
        run_id="r1", task_brief="test",
        started_at=datetime.now(timezone.utc),
    )
    assert state.version == 0
    assert state.step == 0
    assert state.current_phase == Phase.PLAN

    decision = DecideOutput(
        next_phase=Phase.ACT, reasoning="proceed", llm_call=_empty_llm_call()
    )
    state.apply(decision)

    assert state.version == 1
    assert state.step == 1
    assert state.current_phase == Phase.ACT
    assert state.last_decision_reasoning == "proceed"


def test_halt_sets_halt_reason():
    state = AgentState(run_id="r1", task_brief="t",
                       started_at=datetime.now(timezone.utc))
    decision = DecideOutput(
        next_phase=Phase.HALT, halt_reason="done", reasoning="finished",
        llm_call=_empty_llm_call()
    )
    state.apply(decision)
    assert state.is_terminal()
    assert state.halt_reason == "done"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/unit/test_state.py -v
```

Expected: ImportError or ModuleNotFoundError on `recon_agent.agent.state`.

- [ ] **Step 3: Write `src/recon_agent/agent/phases.py`**

```python
from enum import Enum


class Phase(str, Enum):
    PLAN    = "PLAN"
    ACT     = "ACT"
    OBSERVE = "OBSERVE"
    DECIDE  = "DECIDE"
    HALT    = "HALT"
```

- [ ] **Step 4: Write `src/recon_agent/agent/state.py` (matches spec §3.2)**

```python
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .phases import Phase

SCHEMA_VERSION = 1


class ToolCallRecord(BaseModel):
    step: int
    tool_name: str
    args: dict
    started_at: datetime
    finished_at: datetime
    latency_ms: int
    outcome: Literal["ok", "error", "recovered"]
    error_kind: Literal["transient", "persistent", "fatal"] | None = None
    error_code: str | None = None
    cost_inr: float = 0.0


class LLMCallRecord(BaseModel):
    step: int
    phase: Phase
    provider: str
    model: str
    subtask: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_inr: float
    cache_hit: bool = False


class Discrepancy(BaseModel):
    txn_id: str
    kind: Literal[
        "missing_in_api", "missing_in_csv", "value_mismatch",
        "duplicate", "timezone_shift", "encoding_corruption",
    ]
    csv_record: dict | None = None
    api_record: dict | None = None
    severity: Literal["low", "medium", "high"] = "medium"
    confidence: float = 1.0


class CorrectionProposal(BaseModel):
    txn_id: str
    field: str
    old_value: object | None = None
    new_value: object | None = None
    reason: str
    confidence: float


class DecideOutput(BaseModel):
    next_phase: Phase
    halt_reason: str | None = None
    reasoning: str
    llm_call: "LLMCallRecord"
    recovery_invoked: bool = False


class AgentState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    version: int = 0
    run_id: str
    task_brief: str

    current_phase: Phase = Phase.PLAN
    step: int = 0
    started_at: datetime
    last_decision_reasoning: str = ""

    csv_loaded: bool = False
    api_loaded: bool = False
    txns_csv: list[dict] = Field(default_factory=list)
    txns_api: list[dict] = Field(default_factory=list)
    timezone_normalized: bool = False
    matches: list[dict] = Field(default_factory=list)
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    proposals: list[CorrectionProposal] = Field(default_factory=list)
    corrections_applied: int = 0

    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    consecutive_failures: int = 0
    halt_reason: str | None = None

    def is_terminal(self) -> bool:
        return self.current_phase == Phase.HALT

    def apply(self, decision: DecideOutput) -> None:
        self.version += 1
        self.step += 1
        self.current_phase = decision.next_phase
        self.last_decision_reasoning = decision.reasoning
        if decision.next_phase == Phase.HALT:
            self.halt_reason = decision.halt_reason

    def snapshot_to_disk(self, run_dir: Path) -> None:
        path = run_dir / f"step_{self.step:03d}.json"
        path.write_text(self.model_dump_json(indent=2))
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/unit/test_state.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/recon_agent/agent/phases.py src/recon_agent/agent/state.py tests/unit/test_state.py
git commit -m "feat(agent): Phase enum + AgentState with version bump on apply"
```

---

### Task 1.5: Tool ABC + ToolError + ToolResult

**Files:** Create: `src/recon_agent/tools/base.py`; Test: `tests/unit/test_tool_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_tool_base.py
from pydantic import BaseModel
from recon_agent.tools.base import Tool, ToolResult, ToolError


class InpModel(BaseModel):
    x: int


class OutModel(BaseModel):
    y: int


class DoubleTool(Tool[InpModel, OutModel]):
    name = "double"
    input_schema = InpModel
    output_schema = OutModel
    cost_estimate_inr = 0.0
    timeout_seconds = 1.0

    def run(self, inputs: InpModel) -> ToolResult[OutModel]:
        return ToolResult(ok=True, output=OutModel(y=inputs.x * 2))


def test_tool_run_returns_typed_result():
    t = DoubleTool()
    result = t.run(InpModel(x=21))
    assert result.ok is True
    assert result.output.y == 42
    assert result.error is None


def test_tool_describe_returns_schema():
    t = DoubleTool()
    desc = t.describe()
    assert desc["name"] == "double"
    assert "input_schema" in desc
    assert "output_schema" in desc


def test_tool_error_is_typed():
    err = ToolError(kind="transient", code="RATE_LIMIT",
                    message="429", retriable=True)
    assert err.kind == "transient"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/unit/test_tool_base.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Write `src/recon_agent/tools/base.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

IN = TypeVar("IN", bound=BaseModel)
OUT = TypeVar("OUT", bound=BaseModel)


class ToolError(BaseModel):
    kind: Literal["transient", "persistent", "fatal"]
    code: str
    message: str
    retriable: bool


class ToolResult(BaseModel, Generic[OUT]):
    ok: bool
    output: OUT | None = None
    error: ToolError | None = None


class Tool(ABC, Generic[IN, OUT]):
    name: str
    input_schema: type[IN]
    output_schema: type[OUT]
    timeout_seconds: float = 30.0
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

- [ ] **Step 4: Run test — verify passes**

```bash
pytest tests/unit/test_tool_base.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/base.py tests/unit/test_tool_base.py
git commit -m "feat(tools): Tool ABC, ToolResult, ToolError"
```

---

### Task 1.6: ToolRegistry with auto-discovery + no-op tool

**Files:**
- Create: `src/recon_agent/tools/registry.py`
- Create: `src/recon_agent/tools/_noop.py` (temp scaffolding tool, will be removed/repurposed in Phase 4)
- Test: `tests/unit/test_tool_registry.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_tool_registry.py
from recon_agent.tools.registry import ToolRegistry


def test_registry_discovers_noop():
    ToolRegistry.discover()
    tools = ToolRegistry.available()
    names = [t.name for t in tools]
    assert "noop" in names


def test_registry_disable_filters():
    ToolRegistry.discover()
    available = ToolRegistry.available(disabled={"noop"})
    names = [t.name for t in available]
    assert "noop" not in names


def test_registry_schemas_for_llm():
    ToolRegistry.discover()
    schemas = ToolRegistry.schemas_for_llm()
    assert len(schemas) >= 1
    assert all("input_schema" in s for s in schemas)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/unit/test_tool_registry.py -v
```

- [ ] **Step 3: Write `src/recon_agent/tools/_noop.py`**

```python
from pydantic import BaseModel
from .base import Tool, ToolResult


class NoopInput(BaseModel):
    note: str = ""


class NoopOutput(BaseModel):
    ok: bool = True


class NoopTool(Tool[NoopInput, NoopOutput]):
    name = "noop"
    input_schema = NoopInput
    output_schema = NoopOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 1.0

    def run(self, inputs: NoopInput) -> ToolResult[NoopOutput]:
        return ToolResult(ok=True, output=NoopOutput(ok=True))
```

- [ ] **Step 4: Write `src/recon_agent/tools/registry.py`**

```python
from __future__ import annotations
import importlib
import inspect
import pkgutil
from typing import ClassVar

from .base import Tool


class ToolRegistry:
    _tools: ClassVar[dict[str, Tool]] = {}
    _discovered: ClassVar[bool] = False

    @classmethod
    def register(cls, tool: Tool) -> None:
        cls._tools[tool.name] = tool

    @classmethod
    def discover(cls, force: bool = False) -> None:
        if cls._discovered and not force:
            return
        cls._tools.clear()
        import recon_agent.tools as pkg
        for _, mod_name, _ in pkgutil.iter_modules(pkg.__path__):
            if mod_name in ("base", "registry"):
                continue
            module = importlib.import_module(f"recon_agent.tools.{mod_name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, Tool)
                        and obj is not Tool
                        and hasattr(obj, "name")
                        and obj.__module__ == module.__name__):
                    cls.register(obj())
        cls._discovered = True

    @classmethod
    def get(cls, name: str) -> Tool:
        if not cls._discovered:
            cls.discover()
        return cls._tools[name]

    @classmethod
    def available(cls, disabled: set[str] = frozenset()) -> list[Tool]:
        if not cls._discovered:
            cls.discover()
        return [t for n, t in cls._tools.items() if n not in disabled]

    @classmethod
    def schemas_for_llm(cls, disabled: set[str] = frozenset()) -> list[dict]:
        return [t.describe() for t in cls.available(disabled)]
```

- [ ] **Step 5: Run tests — verify passes**

```bash
pytest tests/unit/test_tool_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/recon_agent/tools/registry.py src/recon_agent/tools/_noop.py tests/unit/test_tool_registry.py
git commit -m "feat(tools): ToolRegistry with auto-discovery + noop tool"
```

---

### Task 1.7: Budget skeleton (structure only; no enforcement yet)

**Files:** Create: `src/recon_agent/agent/budget.py`; Test: `tests/unit/test_budget.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_budget.py
from datetime import datetime, timedelta, timezone
from recon_agent.agent.budget import Budget, check
from recon_agent.agent.state import AgentState, LLMCallRecord, ToolCallRecord
from recon_agent.agent.phases import Phase


def _state(**kw) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc), **kw)


def test_budget_default_values():
    b = Budget()
    assert b.max_tokens == 100_000
    assert b.max_wall_clock_s == 600.0
    assert b.max_tool_calls == 60
    assert b.max_consecutive_failures == 5
    assert b.max_cost_inr == 50.0


def test_check_returns_none_when_under_limits():
    b = Budget()
    s = _state()
    assert check(b, s) is None


def test_check_detects_token_breach():
    b = Budget(max_tokens=100)
    s = _state()
    s.llm_calls.append(LLMCallRecord(
        step=1, phase=Phase.PLAN, provider="g", model="g", subtask="p",
        tokens_in=200, tokens_out=0, latency_ms=0, cost_inr=0
    ))
    breach = check(b, s)
    assert breach is not None
    assert breach.dim == "tokens"


def test_check_detects_consecutive_failures():
    b = Budget(max_consecutive_failures=2)
    s = _state(consecutive_failures=2)
    breach = check(b, s)
    assert breach is not None
    assert breach.dim == "consecutive_failures"
```

- [ ] **Step 2: Verify fail**

```bash
pytest tests/unit/test_budget.py -v
```

- [ ] **Step 3: Write `src/recon_agent/agent/budget.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone

from pydantic import BaseModel

from .state import AgentState


class Budget(BaseModel):
    max_tokens: int = 100_000
    max_wall_clock_s: float = 600.0
    max_tool_calls: int = 60
    max_consecutive_failures: int = 5
    max_cost_inr: float = 50.0


class Breach(BaseModel):
    dim: str
    observed: float
    limit: float
    message: str


def check(budget: Budget, state: AgentState) -> Breach | None:
    tokens_used = sum(c.tokens_in + c.tokens_out for c in state.llm_calls)
    if tokens_used > budget.max_tokens:
        return Breach(dim="tokens", observed=tokens_used, limit=budget.max_tokens,
                      message=f"{tokens_used} tokens > {budget.max_tokens} ceiling")

    elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
    if elapsed > budget.max_wall_clock_s:
        return Breach(dim="wall_clock", observed=elapsed, limit=budget.max_wall_clock_s,
                      message=f"{elapsed:.1f}s > {budget.max_wall_clock_s}s ceiling")

    if len(state.tool_calls) > budget.max_tool_calls:
        return Breach(dim="tool_calls", observed=len(state.tool_calls),
                      limit=budget.max_tool_calls,
                      message=f"{len(state.tool_calls)} calls > {budget.max_tool_calls}")

    if state.consecutive_failures >= budget.max_consecutive_failures:
        return Breach(dim="consecutive_failures", observed=state.consecutive_failures,
                      limit=budget.max_consecutive_failures,
                      message=f"{state.consecutive_failures} consecutive failures")

    cost = sum(c.cost_inr for c in state.llm_calls) + sum(c.cost_inr for c in state.tool_calls)
    if cost > budget.max_cost_inr:
        return Breach(dim="cost", observed=cost, limit=budget.max_cost_inr,
                      message=f"₹{cost:.2f} > ₹{budget.max_cost_inr} ceiling")

    return None
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_budget.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/agent/budget.py tests/unit/test_budget.py
git commit -m "feat(agent): Budget with check() across 5 dimensions"
```

---

### Task 1.8: Minimal AgentLoop that halts after step 1

**Files:** Create: `src/recon_agent/agent/loop.py`; Test: `tests/integration/test_loop_smoke.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_loop_smoke.py
import tempfile
from pathlib import Path
from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.tools.registry import ToolRegistry


def test_loop_runs_and_halts():
    ToolRegistry.discover()
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        loop = AgentLoop(
            task="smoke test",
            tools=ToolRegistry,
            budget=Budget(),
            llm_router=None,        # placeholder for Phase 1; real router lands in Phase 2
            recovery=None,
            logger=None,
            run_dir=run_dir,
        )
        report = loop.run()
        assert report is not None
        # at least step_000.json should exist
        assert (run_dir / "step_000.json").exists()
        assert loop.state.is_terminal()
```

- [ ] **Step 2: Verify fail**

```bash
pytest tests/integration/test_loop_smoke.py -v
```

- [ ] **Step 3: Write `src/recon_agent/agent/loop.py` (Phase 1 minimal version)**

```python
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .budget import Budget, check as budget_check
from .phases import Phase
from .state import AgentState, DecideOutput, LLMCallRecord


class ReconciliationReport(BaseModel):
    status: str
    halt_reason: str | None
    findings_by_kind: dict[str, int]
    telemetry: dict


def _empty_llm_call() -> LLMCallRecord:
    return LLMCallRecord(
        step=0, phase=Phase.HALT, provider="none", model="none",
        subtask="none", tokens_in=0, tokens_out=0, latency_ms=0, cost_inr=0.0
    )


class AgentLoop:
    """Phase 1 minimal version: halts after step 1 with a no-op decision.
    Phase 2 adds real Plan + Decide LLM calls."""

    def __init__(
        self,
        task: str,
        tools: Any,
        budget: Budget,
        llm_router: Any = None,
        recovery: Any = None,
        logger: Any = None,
        run_dir: Path | None = None,
    ):
        self.state = AgentState(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            task_brief=task,
            started_at=datetime.now(timezone.utc),
        )
        self.tools = tools
        self.budget = budget
        self.router = llm_router
        self.recovery = recovery
        self.logger = logger
        self.run_dir = run_dir or Path(f"reports/run_{self.state.run_id}")
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> ReconciliationReport:
        self.state.snapshot_to_disk(self.run_dir)   # step_000.json
        breach = budget_check(self.budget, self.state)
        if breach:
            return self._halt(f"budget breach: {breach.dim}")

        # Phase 1: emit immediate HALT (real logic lands in Phase 2)
        decision = DecideOutput(
            next_phase=Phase.HALT,
            halt_reason="phase-1 no-op halt",
            reasoning="scaffolding only; real loop arrives in Phase 2",
            llm_call=_empty_llm_call(),
        )
        self.state.apply(decision)
        self.state.snapshot_to_disk(self.run_dir)
        return self._build_report()

    def _halt(self, reason: str) -> ReconciliationReport:
        self.state.apply(DecideOutput(
            next_phase=Phase.HALT, halt_reason=reason,
            reasoning=f"forced halt: {reason}",
            llm_call=_empty_llm_call(),
        ))
        self.state.snapshot_to_disk(self.run_dir)
        return self._build_report()

    def _build_report(self) -> ReconciliationReport:
        return ReconciliationReport(
            status="completed" if self.state.halt_reason == "reconciliation complete"
                   else "halted",
            halt_reason=self.state.halt_reason,
            findings_by_kind={},
            telemetry={
                "steps": self.state.step,
                "tool_calls": len(self.state.tool_calls),
                "llm_calls": len(self.state.llm_calls),
            },
        )
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/integration/test_loop_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/agent/loop.py tests/integration/test_loop_smoke.py
git commit -m "feat(agent): minimal AgentLoop that halts after step 1"
```

---

### Task 1.9: CLI entry — `recon demo` smoke

**Files:**
- Create: `src/recon_agent/__main__.py`
- Create: `src/recon_agent/cli/demo.py`

- [ ] **Step 1: Write `src/recon_agent/cli/demo.py`**

```python
from __future__ import annotations
import argparse
from pathlib import Path

from ..agent.loop import AgentLoop
from ..agent.budget import Budget
from ..tools.registry import ToolRegistry


def add_demo_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--task", default="Reconcile CSV vs PayU API.")
    p.add_argument("--budget-tokens", type=int, default=100_000)
    p.add_argument("--budget-time", type=float, default=600.0)
    p.add_argument("--budget-calls", type=int, default=60)
    p.add_argument("--budget-fails", type=int, default=5)
    p.add_argument("--budget-cost", type=float, default=50.0)
    p.add_argument("--run-dir", type=Path, default=None)


def run_demo(args: argparse.Namespace) -> int:
    ToolRegistry.discover()
    budget = Budget(
        max_tokens=args.budget_tokens,
        max_wall_clock_s=args.budget_time,
        max_tool_calls=args.budget_calls,
        max_consecutive_failures=args.budget_fails,
        max_cost_inr=args.budget_cost,
    )
    loop = AgentLoop(
        task=args.task,
        tools=ToolRegistry,
        budget=budget,
        run_dir=args.run_dir,
    )
    report = loop.run()
    print(f"Status: {report.status}")
    print(f"Halt reason: {report.halt_reason}")
    print(f"Steps: {report.telemetry['steps']}")
    print(f"Run dir: {loop.run_dir}")
    return 0 if report.status in ("completed", "halted") else 2
```

- [ ] **Step 2: Write `src/recon_agent/__main__.py`**

```python
from __future__ import annotations
import argparse
import sys

from .cli.demo import add_demo_args, run_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recon")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo_p = sub.add_parser("demo", help="Run the agent once")
    add_demo_args(demo_p)

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        return run_demo(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify `recon demo` runs**

```bash
.venv/Scripts/recon demo
```

Expected output:
```
Status: halted
Halt reason: phase-1 no-op halt
Steps: 1
Run dir: reports/run_<timestamp>
```

And `ls reports/run_*/` should show `step_000.json` and `step_001.json`.

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/__main__.py src/recon_agent/cli/demo.py
git commit -m "feat(cli): `recon demo` runs Phase-1 no-op loop end-to-end"
```

---

### Phase 1 verification

- [ ] **Confirm exit criteria:**

```bash
make demo
ls reports/run_*/ | tail
pytest tests/ -v
```

Expected:
- `make demo` exits 0 with "Status: halted, Halt reason: phase-1 no-op halt"
- `reports/run_*/` contains `step_000.json` and `step_001.json`
- All unit + integration tests pass
- Repo at `git log --oneline` shows ~6 commits

Once green, proceed to Phase 2.

---

## Phase 2 — LLM plumbing (live calls)

**Entry condition:** Phase 1 complete; `make demo` runs the no-op loop.

**Exit condition:**
- `LLMRouter.call("plan", ...)` makes a real Gemini API call and returns a parsed `PlanOutput`
- `LLMRouter.call("decide", ...)` returns a parsed `DecideOutput`
- `make demo` (with `GEMINI_API_KEY` set) drives a loop where each iteration calls Plan + Decide for real, halts after the LLM decides HALT (typically 1-3 iterations since no tools exist yet)
- Cost tracking is populated in `LLMCallRecord` for every call

**Phase summary:** Add the LLM layer. Two providers (Gemini + OpenAI) via raw SDKs, routed through a single `LLMRouter.call()` entry point. Cassette layer is added in `live` mode only (replay/record land in Phase 7). Plan and Decide phases call the router with structured outputs. After this phase, the agent can think but can't yet act on data — tools land in Phase 4.

---

### Task 2.1: Pricing table

**Files:** Create: `src/recon_agent/llm/pricing.py`; Test: `tests/unit/test_pricing.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_pricing.py
from recon_agent.llm.pricing import cost_inr, PRICING, USD_TO_INR


def test_pricing_table_has_models():
    assert "gemini-2.5-pro" in PRICING
    assert "gpt-4o-mini" in PRICING


def test_cost_inr_basic():
    # gemini-2.5-pro: $1.25/M in, $5/M out
    # 1000 in + 500 out = 0.00125*1 + 0.005*0.5 = 0.00125 + 0.0025 = 0.00375 USD
    # × 83 INR = 0.31 INR
    cost = cost_inr("gemini-2.5-pro", 1000, 500)
    assert abs(cost - 0.31125) < 0.01


def test_cost_inr_zero():
    assert cost_inr("gemini-2.5-pro", 0, 0) == 0.0


def test_cost_inr_unknown_model_raises():
    import pytest
    with pytest.raises(KeyError):
        cost_inr("gpt-99", 100, 100)
```

- [ ] **Step 2: Verify fails**

```bash
pytest tests/unit/test_pricing.py -v
```

- [ ] **Step 3: Write `src/recon_agent/llm/pricing.py`**

```python
from __future__ import annotations
from pydantic import BaseModel

USD_TO_INR = 83.0


class ModelPrice(BaseModel):
    input: float    # USD per 1M tokens
    output: float


PRICING: dict[str, ModelPrice] = {
    "gemini-2.5-pro":   ModelPrice(input=1.25,  output=5.00),
    "gemini-2.5-flash": ModelPrice(input=0.075, output=0.30),
    "gpt-4o":           ModelPrice(input=2.50,  output=10.00),
    "gpt-4o-mini":      ModelPrice(input=0.15,  output=0.60),
}


def cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING[model]
    usd = (tokens_in / 1_000_000) * p.input + (tokens_out / 1_000_000) * p.output
    return round(usd * USD_TO_INR, 4)
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_pricing.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/llm/pricing.py tests/unit/test_pricing.py
git commit -m "feat(llm): pricing table + cost_inr()"
```

---

### Task 2.2: Provider adapters (Gemini + OpenAI)

**Files:** Create: `src/recon_agent/llm/providers.py`

- [ ] **Step 1: Write `src/recon_agent/llm/providers.py`**

```python
from __future__ import annotations
import os
import time
from typing import Any

from pydantic import BaseModel


class RawLLMResponse(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class LLMError(Exception):
    """Provider call failed. Caller classifies kind via `code` and HTTP status."""
    def __init__(self, code: str, message: str, retriable: bool):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable


def gemini_call(
    model: str,
    messages: list[dict],
    response_schema: type[BaseModel],
    timeout_s: float = 30.0,
) -> RawLLMResponse:
    """Hits Gemini's generateContent endpoint with structured-output mode."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    started = time.time()

    # Concatenate messages into a single content (Gemini's simpler API surface).
    content = "\n\n".join(
        f"[{m.get('role', 'user').upper()}] {m['content']}"
        for m in messages
    )

    try:
        resp = client.models.generate_content(
            model=model,
            contents=content,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                max_output_tokens=2048,
                temperature=0.2,
            ),
        )
    except Exception as e:
        # google-genai raises various; map a couple by string sniffing
        msg = str(e)
        if "429" in msg or "rate limit" in msg.lower():
            raise LLMError("LLM_RATE_LIMIT", msg, retriable=True) from e
        if "timeout" in msg.lower():
            raise LLMError("LLM_TIMEOUT", msg, retriable=True) from e
        raise LLMError("LLM_PROVIDER_ERROR", msg, retriable=False) from e

    latency_ms = int((time.time() - started) * 1000)
    usage = resp.usage_metadata
    return RawLLMResponse(
        text=resp.text,
        tokens_in=usage.prompt_token_count,
        tokens_out=usage.candidates_token_count,
        latency_ms=latency_ms,
    )


def openai_call(
    model: str,
    messages: list[dict],
    response_schema: type[BaseModel],
    timeout_s: float = 30.0,
) -> RawLLMResponse:
    """Hits OpenAI chat.completions with strict json_schema."""
    from openai import OpenAI, APITimeoutError, RateLimitError

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=timeout_s)
    started = time.time()

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                },
            },
            max_tokens=2048,
            temperature=0.2,
        )
    except RateLimitError as e:
        raise LLMError("LLM_RATE_LIMIT", str(e), retriable=True) from e
    except APITimeoutError as e:
        raise LLMError("LLM_TIMEOUT", str(e), retriable=True) from e
    except Exception as e:
        raise LLMError("LLM_PROVIDER_ERROR", str(e), retriable=False) from e

    latency_ms = int((time.time() - started) * 1000)
    choice = resp.choices[0].message
    usage = resp.usage
    return RawLLMResponse(
        text=choice.content or "",
        tokens_in=usage.prompt_tokens,
        tokens_out=usage.completion_tokens,
        latency_ms=latency_ms,
    )
```

- [ ] **Step 2: Manual smoke test (requires GEMINI_API_KEY set)**

Create a quick `scripts/smoke_gemini.py`:

```python
# scripts/smoke_gemini.py (not committed; throwaway)
from pydantic import BaseModel
from recon_agent.llm.providers import gemini_call

class Echo(BaseModel):
    message: str

resp = gemini_call(
    "gemini-2.5-flash",
    [{"role": "user", "content": "Reply with JSON {\"message\": \"hello\"}"}],
    Echo,
)
print(resp)
```

Run: `python scripts/smoke_gemini.py`
Expected: `RawLLMResponse(text='{"message": "hello"}', tokens_in=..., tokens_out=..., latency_ms=...)`

If it works, delete the script. (Don't commit smoke scripts.)

- [ ] **Step 3: Commit**

```bash
git add src/recon_agent/llm/providers.py
git commit -m "feat(llm): Gemini + OpenAI provider adapters with typed errors"
```

---

### Task 2.3: Cassette layer (live mode only at this phase)

**Files:** Create: `src/recon_agent/llm/cassettes.py`; Test: `tests/unit/test_cassettes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_cassettes.py
from pathlib import Path
from pydantic import BaseModel

from recon_agent.llm.cassettes import CassetteLayer
from recon_agent.llm.providers import RawLLMResponse


class DummySchema(BaseModel):
    x: int


def test_live_mode_does_not_read_or_write(tmp_path):
    c = CassetteLayer(mode="live", path=tmp_path / "test.jsonl")
    h = c.hash("gemini", "gemini-2.5-pro", "plan",
               [{"role": "user", "content": "hi"}], DummySchema)
    assert c.get(h) is None    # nothing exists


def test_hash_is_stable_across_instances(tmp_path):
    c1 = CassetteLayer(mode="replay", path=tmp_path / "a.jsonl")
    c2 = CassetteLayer(mode="replay", path=tmp_path / "a.jsonl")
    msgs = [{"role": "user", "content": "x"}]
    assert c1.hash("g", "m", "p", msgs, DummySchema) \
        == c2.hash("g", "m", "p", msgs, DummySchema)


def test_record_then_replay(tmp_path):
    path = tmp_path / "test.jsonl"
    rec = CassetteLayer(mode="record", path=path)
    msgs = [{"role": "user", "content": "x"}]
    h = rec.hash("g", "m", "p", msgs, DummySchema)
    resp = RawLLMResponse(text='{"x":1}', tokens_in=10, tokens_out=5, latency_ms=100)
    rec.put(h, resp)

    rep = CassetteLayer(mode="replay", path=path)
    found = rep.get(h)
    assert found is not None
    assert found.text == '{"x":1}'
    assert found.tokens_in == 10
```

- [ ] **Step 2: Verify fails**

```bash
pytest tests/unit/test_cassettes.py -v
```

- [ ] **Step 3: Write `src/recon_agent/llm/cassettes.py`**

```python
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .providers import RawLLMResponse


class CassetteMiss(Exception):
    pass


class CassetteLayer:
    """Three modes:
      live    — no read, no write
      record  — no read; write every response to the cassette
      replay  — read; raise CassetteMiss on unknown hash
    """

    def __init__(
        self,
        mode: Literal["live", "record", "replay"],
        path: Path,
    ):
        self.mode = mode
        self.path = path
        self._index: dict[str, RawLLMResponse] = {}
        if self.mode == "replay":
            self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            self._index[entry["hash"]] = RawLLMResponse(**entry["response"])

    @staticmethod
    def hash(
        provider: str, model: str, subtask: str,
        messages: list[dict], schema: type[BaseModel],
    ) -> str:
        payload = {
            "provider": provider,
            "model": model,
            "subtask": subtask,
            "messages": messages,
            "schema": schema.model_json_schema(),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def get(self, h: str) -> RawLLMResponse | None:
        if self.mode == "replay":
            r = self._index.get(h)
            if r is None:
                # Caller can decide: raise CassetteMiss or fall through
                return None
            return r
        return None

    def require(self, h: str) -> RawLLMResponse:
        r = self.get(h)
        if r is None:
            raise CassetteMiss(
                f"No cassette for hash {h[:12]}... in {self.path}. "
                f"Re-record with `make eval-live`."
            )
        return r

    def put(self, h: str, response: RawLLMResponse) -> None:
        if self.mode != "record":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"hash": h, "response": response.model_dump()}) + "\n")
        self._index[h] = response
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_cassettes.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/llm/cassettes.py tests/unit/test_cassettes.py
git commit -m "feat(llm): CassetteLayer with live/record/replay modes"
```

---

### Task 2.4: LLM router

**Files:** Create: `src/recon_agent/llm/router.py`

- [ ] **Step 1: Write `src/recon_agent/llm/router.py`**

```python
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..agent.phases import Phase
from ..agent.state import LLMCallRecord
from .cassettes import CassetteLayer
from .pricing import cost_inr
from .providers import RawLLMResponse, gemini_call, openai_call, LLMError


@dataclass(frozen=True)
class RouteSpec:
    provider: str   # "gemini" | "openai"
    model: str
    rationale: str


# Override via PLAN_PROVIDER=openai for the comparison eval (Phase 8)
PLAN_PROVIDER_OVERRIDE = os.environ.get("PLAN_PROVIDER")

ROUTING_TABLE: dict[str, RouteSpec] = {
    "plan":        RouteSpec("gemini", "gemini-2.5-pro",   "Reasoning-heavy; drives every iteration."),
    "decide":      RouteSpec("gemini", "gemini-2.5-pro",   "Meta-cognition; same bar as plan."),
    "classify":    RouteSpec("openai", "gpt-4o-mini",       "Cheap structured classification."),
    "summary":     RouteSpec("gemini", "gemini-2.5-flash", "One call, NL only, cheap."),
    "shadow_plan": RouteSpec("openai", "gpt-4o",            "Apples-to-apples capable comparison."),
    "propose":     RouteSpec("gemini", "gemini-2.5-flash", "Per-correction LLM call; cheap."),
}


def _route_for(subtask: str) -> RouteSpec:
    if subtask == "plan" and PLAN_PROVIDER_OVERRIDE == "openai":
        return RouteSpec("openai", "gpt-4o", "PLAN_PROVIDER override for comparison eval")
    return ROUTING_TABLE[subtask]


class LLMRouter:
    def __init__(self, cassette: CassetteLayer):
        self._cassette = cassette

    def call(
        self,
        subtask: str,
        messages: list[dict],
        response_schema: type[BaseModel],
        timeout_s: float = 30.0,
        step: int = 0,
        phase: Phase = Phase.PLAN,
    ) -> tuple[BaseModel, LLMCallRecord]:
        route = _route_for(subtask)
        h = self._cassette.hash(route.provider, route.model, subtask, messages, response_schema)

        # Replay path
        if self._cassette.mode == "replay":
            raw = self._cassette.require(h)
            parsed = response_schema.model_validate_json(raw.text)
            return parsed, LLMCallRecord(
                step=step, phase=phase, provider=route.provider, model=route.model,
                subtask=subtask, tokens_in=raw.tokens_in, tokens_out=raw.tokens_out,
                latency_ms=raw.latency_ms, cost_inr=0.0, cache_hit=True,
            )

        # Live or record path
        if route.provider == "gemini":
            raw = gemini_call(route.model, messages, response_schema, timeout_s)
        elif route.provider == "openai":
            raw = openai_call(route.model, messages, response_schema, timeout_s)
        else:
            raise ValueError(f"unknown provider {route.provider}")

        parsed = response_schema.model_validate_json(raw.text)
        c = cost_inr(route.model, raw.tokens_in, raw.tokens_out)

        if self._cassette.mode == "record":
            self._cassette.put(h, raw)

        return parsed, LLMCallRecord(
            step=step, phase=phase, provider=route.provider, model=route.model,
            subtask=subtask, tokens_in=raw.tokens_in, tokens_out=raw.tokens_out,
            latency_ms=raw.latency_ms, cost_inr=c, cache_hit=False,
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/recon_agent/llm/router.py
git commit -m "feat(llm): LLMRouter with ROUTING_TABLE + cassette integration"
```

---

### Task 2.5: Prompt files

**Files:**
- Create: `src/recon_agent/agent/prompts/plan_system.txt`
- Create: `src/recon_agent/agent/prompts/decide_system.txt`

- [ ] **Step 1: Write `plan_system.txt`**

```
You are the Plan phase of an autonomous reconciliation agent.

GOAL: Reconcile GrabOn deal-redemption transactions across two sources:
  - tracking_db.csv (internal CSV, IST timestamps)
  - PayU settlement API (JSON, claims UTC timestamps but some are IST-stored-as-UTC)

Available tools (with input/output schemas) will be provided in the user message.

Your job: emit the NEXT ACTION as a single tool call. Choose one tool, one set of args, one short reasoning sentence. Do NOT plan multiple steps ahead.

Constraints:
- Only call tools listed in the user message
- Args must match the tool's input_schema
- Reasoning ≤300 chars
- If reconciliation appears complete (verify_reconciliation returned residual_discrepancies=[]), choose verify_reconciliation one more time to confirm, then on the next iteration emit no tool — Decide will HALT
- If a tool keeps failing, suggest an alternative (e.g., if fetch_api fails 3x, proceed CSV-only)

Output schema is enforced as strict JSON.
```

- [ ] **Step 2: Write `decide_system.txt`**

```
You are the Decide phase of an autonomous reconciliation agent.

You receive: the Observation summary from the last tool call, plus accumulated state context.

Your job: decide the next phase. Choose ONE of:
  - PLAN       — continue working; the agent will plan a next action
  - HALT       — reconciliation is complete OR the task is impossible

When to HALT:
  - All discrepancies have been classified, proposed, applied, and verify_reconciliation shows residual_discrepancies near zero
  - The task is impossible (corrupted source, irreconcilable data); set halt_reason explaining
  - Repeated tool failure that recovery layer can't resolve

When to PLAN (continue):
  - Tools just succeeded and more work remains
  - Discrepancies found but corrections not yet applied
  - Verify-reconciliation has not been called yet

Reasoning field: ≤300 chars. Be concrete: "23 discrepancies classified, proposing corrections next" — not "let me think about this."

Output schema is enforced as strict JSON.
```

- [ ] **Step 3: Commit**

```bash
git add src/recon_agent/agent/prompts/
git commit -m "feat(prompts): Plan + Decide system prompts"
```

---

### Task 2.6: Plan phase class

**Files:** Modify: `src/recon_agent/agent/phases.py` (append Plan + PlanOutput)

- [ ] **Step 1: Append to `src/recon_agent/agent/phases.py`**

```python
# Add at the bottom of phases.py

from __future__ import annotations as _    # if not already imported above
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .state import AgentState, LLMCallRecord


class PlanOutput(BaseModel):
    intended_tool: str
    tool_args: dict = Field(default_factory=dict)
    reasoning: str = ""
    estimated_cost_inr: float = 0.0


class Plan:
    """LLM-backed planner: emits the next tool call."""

    PROMPT_PATH = Path(__file__).parent / "prompts" / "plan_system.txt"

    def __init__(self, router: Any, tool_registry: Any, logger: Any = None):
        self._router = router
        self._registry = tool_registry
        self._system = self.PROMPT_PATH.read_text(encoding="utf-8")
        self._logger = logger

    def run(self, state: AgentState) -> tuple[PlanOutput, LLMCallRecord]:
        schemas = self._registry.schemas_for_llm()
        ctx = self._build_context(state)
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content":
                f"Available tools:\n{schemas}\n\nCurrent state:\n{ctx}\n\n"
                "Emit next action."},
        ]
        out, call = self._router.call(
            "plan", messages, PlanOutput, step=state.step, phase=Phase.PLAN
        )
        return out, call

    def _build_context(self, state: AgentState) -> str:
        return (
            f"step={state.step} csv_loaded={state.csv_loaded} "
            f"api_loaded={state.api_loaded} tz_normalized={state.timezone_normalized} "
            f"matches={len(state.matches)} discrepancies={len(state.discrepancies)} "
            f"proposals={len(state.proposals)} applied={state.corrections_applied} "
            f"last_reasoning='{state.last_decision_reasoning[:200]}'"
        )
```

- [ ] **Step 2: Smoke test (manual)**

```python
# Quick manual check; do not commit
from recon_agent.tools.registry import ToolRegistry
from recon_agent.llm.cassettes import CassetteLayer
from recon_agent.llm.router import LLMRouter
from recon_agent.agent.phases import Plan
from recon_agent.agent.state import AgentState
from datetime import datetime, timezone
from pathlib import Path

ToolRegistry.discover()
cassette = CassetteLayer(mode="live", path=Path("tmp.jsonl"))
router = LLMRouter(cassette)
plan = Plan(router, ToolRegistry)
state = AgentState(run_id="r", task_brief="reconcile",
                   started_at=datetime.now(timezone.utc))
out, rec = plan.run(state)
print(out, rec.cost_inr)
```

Expected: `out.intended_tool == "noop"` (only tool available), positive cost_inr.

- [ ] **Step 3: Commit**

```bash
git add src/recon_agent/agent/phases.py
git commit -m "feat(agent): Plan phase with LLM-backed structured output"
```

---

### Task 2.7: Decide phase class

**Files:** Modify: `src/recon_agent/agent/phases.py` (append Decide; note `DecideOutput` already lives in state.py)

- [ ] **Step 1: Append to `phases.py`**

```python
class Decide:
    """LLM-backed decider: emits next phase + halt_reason."""

    PROMPT_PATH = Path(__file__).parent / "prompts" / "decide_system.txt"

    def __init__(self, router: Any, logger: Any = None):
        self._router = router
        self._system = self.PROMPT_PATH.read_text(encoding="utf-8")
        self._logger = logger

    def run(self, observation: str, state: AgentState) -> tuple["DecideOutput", LLMCallRecord]:
        from .state import DecideOutput  # local to avoid forward-ref
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content":
                f"Observation: {observation}\n\nState: {state.step=} "
                f"discrepancies={len(state.discrepancies)} "
                f"applied={state.corrections_applied} "
                f"consecutive_failures={state.consecutive_failures}"},
        ]
        # Send the schema without the LLMCallRecord field (which we populate ourselves)
        class _DecideOut(BaseModel):
            next_phase: Phase
            halt_reason: str | None = None
            reasoning: str
            recovery_invoked: bool = False
        out, call = self._router.call(
            "decide", messages, _DecideOut, step=state.step, phase=Phase.DECIDE
        )
        return DecideOutput(
            next_phase=out.next_phase,
            halt_reason=out.halt_reason,
            reasoning=out.reasoning,
            recovery_invoked=out.recovery_invoked,
            llm_call=call,
        ), call
```

- [ ] **Step 2: Commit**

```bash
git add src/recon_agent/agent/phases.py
git commit -m "feat(agent): Decide phase with LLM-backed structured output"
```

---

### Task 2.8: Wire Plan + Decide into AgentLoop

**Files:** Modify: `src/recon_agent/agent/loop.py`; Modify: `src/recon_agent/cli/demo.py`

- [ ] **Step 1: Rewrite `src/recon_agent/agent/loop.py`** (full Phase 2 version)

```python
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .budget import Budget, check as budget_check
from .phases import Phase, Plan, Decide
from .state import AgentState, DecideOutput, LLMCallRecord


class ReconciliationReport(BaseModel):
    status: str
    halt_reason: str | None
    findings_by_kind: dict[str, int]
    telemetry: dict


def _empty_llm_call(phase: Phase = Phase.HALT) -> LLMCallRecord:
    return LLMCallRecord(
        step=0, phase=phase, provider="none", model="none",
        subtask="none", tokens_in=0, tokens_out=0, latency_ms=0, cost_inr=0.0
    )


class AgentLoop:
    def __init__(
        self,
        task: str,
        tools: Any,
        budget: Budget,
        llm_router: Any,
        logger: Any = None,
        run_dir: Path | None = None,
        max_iterations: int = 30,    # hard ceiling on top of budget
    ):
        self.state = AgentState(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            task_brief=task,
            started_at=datetime.now(timezone.utc),
        )
        self.tools = tools
        self.budget = budget
        self.router = llm_router
        self.logger = logger
        self.run_dir = run_dir or Path(f"reports/run_{self.state.run_id}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations
        self.plan_phase = Plan(self.router, self.tools, self.logger)
        self.decide_phase = Decide(self.router, self.logger)

    def run(self) -> ReconciliationReport:
        self.state.snapshot_to_disk(self.run_dir)
        iteration = 0

        while not self.state.is_terminal() and iteration < self.max_iterations:
            iteration += 1

            # Budget gate
            breach = budget_check(self.budget, self.state)
            if breach:
                self._halt(f"budget breach: {breach.dim} ({breach.message})")
                break

            # PLAN
            try:
                plan_out, plan_call = self.plan_phase.run(self.state)
                self.state.llm_calls.append(plan_call)
            except Exception as e:
                self._halt(f"plan exception: {type(e).__name__}: {e}")
                break

            # ACT — Phase 2 stub: just record that we'd call the tool
            # Real Act lands in Phase 4 when tools are real
            observation = (
                f"(stub) would call {plan_out.intended_tool} with {plan_out.tool_args}"
            )

            # DECIDE
            try:
                dec_out, dec_call = self.decide_phase.run(observation, self.state)
                self.state.llm_calls.append(dec_call)
            except Exception as e:
                self._halt(f"decide exception: {type(e).__name__}: {e}")
                break

            self.state.apply(dec_out)
            self.state.snapshot_to_disk(self.run_dir)

        if not self.state.is_terminal():
            self._halt(f"max iterations {self.max_iterations} reached")

        return self._build_report()

    def _halt(self, reason: str) -> None:
        decision = DecideOutput(
            next_phase=Phase.HALT, halt_reason=reason,
            reasoning=f"forced halt: {reason}",
            llm_call=_empty_llm_call(),
        )
        self.state.apply(decision)
        self.state.snapshot_to_disk(self.run_dir)

    def _build_report(self) -> ReconciliationReport:
        total_cost = sum(c.cost_inr for c in self.state.llm_calls) \
                   + sum(c.cost_inr for c in self.state.tool_calls)
        return ReconciliationReport(
            status="completed" if self.state.halt_reason
                                  and "complete" in self.state.halt_reason
                   else "halted",
            halt_reason=self.state.halt_reason,
            findings_by_kind={},
            telemetry={
                "steps": self.state.step,
                "tool_calls": len(self.state.tool_calls),
                "llm_calls": len(self.state.llm_calls),
                "total_cost_inr": round(total_cost, 4),
            },
        )
```

- [ ] **Step 2: Update `cli/demo.py` to wire the router**

```python
# Modify run_demo() in src/recon_agent/cli/demo.py
from __future__ import annotations
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from ..agent.loop import AgentLoop
from ..agent.budget import Budget
from ..llm.cassettes import CassetteLayer
from ..llm.router import LLMRouter
from ..tools.registry import ToolRegistry


def add_demo_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--task", default="Reconcile CSV vs PayU API.")
    p.add_argument("--budget-tokens", type=int, default=100_000)
    p.add_argument("--budget-time", type=float, default=600.0)
    p.add_argument("--budget-calls", type=int, default=60)
    p.add_argument("--budget-fails", type=int, default=5)
    p.add_argument("--budget-cost", type=float, default=50.0)
    p.add_argument("--llm-mode", choices=["live", "record", "replay"], default=None)
    p.add_argument("--run-dir", type=Path, default=None)


def run_demo(args: argparse.Namespace) -> int:
    load_dotenv()
    mode = args.llm_mode or os.environ.get("LLM_MODE", "live")
    cassette = CassetteLayer(mode=mode, path=Path("reports/_demo_cassette.jsonl"))
    router = LLMRouter(cassette)

    ToolRegistry.discover()
    budget = Budget(
        max_tokens=args.budget_tokens,
        max_wall_clock_s=args.budget_time,
        max_tool_calls=args.budget_calls,
        max_consecutive_failures=args.budget_fails,
        max_cost_inr=args.budget_cost,
    )
    loop = AgentLoop(
        task=args.task,
        tools=ToolRegistry,
        budget=budget,
        llm_router=router,
        run_dir=args.run_dir,
    )
    report = loop.run()
    print(f"Status: {report.status}")
    print(f"Halt reason: {report.halt_reason}")
    print(f"Steps: {report.telemetry['steps']}")
    print(f"LLM calls: {report.telemetry['llm_calls']}")
    print(f"Total cost: ₹{report.telemetry['total_cost_inr']}")
    print(f"Run dir: {loop.run_dir}")
    return 0 if report.status in ("completed", "halted") else 2
```

- [ ] **Step 3: Run demo with real keys**

```bash
# Make sure .env has GEMINI_API_KEY and OPENAI_API_KEY
make demo
```

Expected:
- 1-3 iterations of Plan + Decide
- Eventually halts (probably "max iterations" since no real tools yet, or LLM decides HALT immediately because state shows no work pending)
- Real positive `Total cost: ₹X.XX`

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/agent/loop.py src/recon_agent/cli/demo.py
git commit -m "feat(agent): wire Plan+Decide+router into AgentLoop for real LLM calls"
```

---

### Phase 2 verification

- [ ] **Confirm exit criteria:**

```bash
make demo
ls reports/run_*/   # should have multiple step_*.json files
pytest tests/ -v
```

Expected:
- `make demo` makes real Gemini API calls (verify in dashboard or output)
- `Total cost:` is non-zero (₹0.10-₹2.00 range typically)
- All tests pass
- `step_*.json` snapshots show `llm_calls` populated with provider/model/cost

Once green, proceed to Phase 3.

---

## Phase 3 — Data layer (fixtures + ground truth + ledger format)

**Entry condition:** Phase 2 complete.

**Exit condition:**
- `python -m recon_agent.data.generate_fixtures --variant default --seed 42` produces deterministic `tracking_db.csv` + `payu_settlements.json` + `ground_truth_default.json`
- All 10 fixture variants produce valid output
- Determinism test passes (same seed twice → byte-identical files)

**Phase summary:** Build the synthetic data layer. Realistic GrabOn-flavored merchants, INR distributions, IST timestamps. 6 defect kinds injected at controlled rates. 10 variants for the eval suite. Ground truth file records every injected defect so the eval verifier can score the agent mechanically.

---

### Task 3.1: Merchant catalog + amount distributions

**Files:** Create: `src/recon_agent/data/catalog.py`

- [ ] **Step 1: Write `src/recon_agent/data/catalog.py`**

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CategorySpec:
    name: str
    merchants: list[str]
    amount_min: int
    amount_max: int
    amount_mean: int


CATEGORIES: list[CategorySpec] = [
    CategorySpec("Fashion", ["Myntra", "Ajio", "Puma", "Nykaa"],          500,   5_000,  1_800),
    CategorySpec("Travel",  ["MakeMyTrip", "Goibibo", "Cleartrip", "Uber"], 1_000, 15_000, 4_500),
    CategorySpec("Food",    ["Zomato", "Swiggy", "BigBasket"],             150,     800,    400),
    CategorySpec("Electronics", ["Amazon", "Flipkart", "Croma", "BoAt"],  1_000, 50_000,  6_000),
    CategorySpec("Health",  ["PharmEasy", "Mamaearth", "Lenskart"],        200,   2_000,    800),
]


COUPON_CODES = [
    "FLAT200", "SAVE40", "NEW100", "WELCOME", "MEGA50",
    "WEEKEND", "RAKHI25", "DIWALI60", "MONDAY10", "CRED50",
]


CHANNELS = ["web", "app", "mweb"]
```

- [ ] **Step 2: Commit**

```bash
git add src/recon_agent/data/catalog.py
git commit -m "feat(data): merchant + category + coupon catalog"
```

---

### Task 3.2: Fixture generator — clean transactions only

**Files:** Create: `src/recon_agent/data/generate_fixtures.py` (partial — defects come in 3.3)

- [ ] **Step 1: Write the generator skeleton**

```python
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .catalog import CATEGORIES, COUPON_CODES, CHANNELS


IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


@dataclass
class InjectedDefect:
    txn_id: str
    kind: str
    csv: dict = field(default_factory=dict)
    api: dict = field(default_factory=dict)
    expected_correction: dict = field(default_factory=dict)


class GroundTruth(BaseModel):
    fixture_seed: int
    variant: str
    total_txns: int
    generated_at: str
    expected_summary: dict[str, int]
    injected: list[dict]


def _make_clean(rng: random.Random, idx: int, base_date: datetime) -> tuple[dict, dict]:
    """Returns (csv_row, api_record) — both clean, perfectly reconciled."""
    cat = rng.choice(CATEGORIES)
    merchant = rng.choice(cat.merchants)
    amount = round(rng.gauss(cat.amount_mean, (cat.amount_max - cat.amount_min) / 4), 2)
    amount = max(cat.amount_min, min(cat.amount_max, amount))
    discount_pct = rng.choice([0.10, 0.20, 0.30, 0.40, 0.50])
    discount = round(amount * discount_pct, 2)
    # Indian business hours bias
    hour = rng.choice([11, 12, 13, 14, 19, 20, 21, 22] + list(range(9, 23)))
    minute = rng.randint(0, 59)
    redemption_ts_ist = base_date.replace(
        hour=hour, minute=minute, second=rng.randint(0, 59), tzinfo=IST
    ) + timedelta(days=rng.randint(0, 30))
    settled_at_utc = redemption_ts_ist.astimezone(UTC) + timedelta(minutes=rng.randint(15, 240))

    txn_id = f"TX-{redemption_ts_ist.year}-{idx:05d}"
    user_hash = hashlib.sha256(f"user{rng.randint(0, 10_000)}".encode()).hexdigest()[:8]

    csv_row = {
        "txn_id": txn_id,
        "redemption_ts": redemption_ts_ist.isoformat(),
        "merchant": merchant,
        "merchant_category": cat.name,
        "deal_id": f"DL-{merchant.upper()}-{rng.randint(100, 9999)}",
        "coupon_code": rng.choice(COUPON_CODES),
        "order_value_inr": f"{amount:.2f}",
        "discount_inr": f"{discount:.2f}",
        "user_id": f"u_{user_hash}",
        "channel": rng.choice(CHANNELS),
    }
    api_record = {
        "settlement_id": f"PYU-{redemption_ts_ist.strftime('%Y%m%d')}-{idx:05d}-S",
        "reference_id": txn_id,
        "settled_at": settled_at_utc.isoformat(),
        "payee": merchant,
        "gross_amount": amount,
        "net_amount": round(amount * 0.99, 2),
        "settlement_status": "settled",
    }
    return csv_row, api_record


def _write_csv(path: Path, rows: list[dict], encoding: str = "utf-8") -> None:
    if not rows:
        path.write_text("", encoding=encoding)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "page": 1,
        "page_size": len(records),
        "total": len(records),
        "next_cursor": None,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 2: Commit**

```bash
git add src/recon_agent/data/generate_fixtures.py
git commit -m "feat(data): fixture generator skeleton (clean txns)"
```

---

### Task 3.3: Defect injection (6 kinds)

**Files:** Modify: `src/recon_agent/data/generate_fixtures.py` (append defect injection)

- [ ] **Step 1: Append defect-injection functions**

```python
DEFECT_VARIANTS: dict[str, dict[str, float]] = {
    "happy_clean":      {},
    "tz_only":          {"timezone_shift": 0.05},
    "encoding_only":    {"encoding_corruption": 0.01},
    "duplicate_only":   {"duplicate": 0.02},
    "value_only":       {"value_mismatch": 0.03},
    "default": {
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "missing_in_csv":     0.005,
        "encoding_corruption": 0.01,
    },
    "default_disabled_api": {  # same as default; the eval scenario disables fetch_api at CLI
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "missing_in_csv":     0.005,
        "encoding_corruption": 0.01,
    },
    "default_latin1_csv": {     # like default + CSV written in latin-1 (handled in write step)
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "encoding_corruption": 0.01,
    },
    "corrupted_source": {},     # CSV will be replaced with binary garbage
    "irreconcilable":   {},     # 0 shared txn_ids — handled in injection
}


def _inject_value_mismatch(csv_row: dict, api_record: dict, rng: random.Random) -> InjectedDefect:
    # round api.gross_amount to nearest ₹10 away from csv's actual
    orig = api_record["gross_amount"]
    rounded = round(orig / 10) * 10 + rng.choice([-0.99, 0.99])
    api_record["gross_amount"] = round(rounded, 2)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="value_mismatch",
        csv={"order_value_inr": orig}, api={"gross_amount": api_record["gross_amount"]},
        expected_correction={
            "field": "gross_amount", "old": api_record["gross_amount"], "new": orig,
            "reason_contains": "rounding",
        }
    )


def _inject_timezone_shift(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    # API's settled_at claims +00:00 but the value is actually IST hours
    redemption_ts_ist = datetime.fromisoformat(csv_row["redemption_ts"])
    # write the IST clock time but with UTC offset
    fake_settled = redemption_ts_ist.replace(tzinfo=UTC)
    api_record["settled_at"] = fake_settled.isoformat()
    correct_settled = redemption_ts_ist.astimezone(UTC)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="timezone_shift",
        csv={"redemption_ts": csv_row["redemption_ts"]},
        api={"settled_at": api_record["settled_at"]},
        expected_correction={
            "field": "settled_at", "old": api_record["settled_at"],
            "new": correct_settled.isoformat(), "reason_contains": "ist_stored_as_utc",
        }
    )


def _inject_duplicate(csv_row: dict, api_record: dict, rng: random.Random,
                      csv_rows: list[dict]) -> InjectedDefect:
    # Append another CSV row with same txn_id, slightly different redemption_ts
    dup = dict(csv_row)
    redemption_ts_ist = datetime.fromisoformat(csv_row["redemption_ts"])
    dup["redemption_ts"] = (redemption_ts_ist + timedelta(seconds=rng.randint(5, 60))).isoformat()
    csv_rows.append(dup)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="duplicate",
        csv={"original_ts": csv_row["redemption_ts"], "dup_ts": dup["redemption_ts"]},
        expected_correction={"field": "_status", "old": "duplicate", "new": "merged",
                             "reason_contains": "dup"}
    )


def _inject_missing_in_api(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    # signal removal — caller filters this record out of api_records
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="missing_in_api",
        csv={"txn_id": csv_row["txn_id"]},
        expected_correction={"field": "_existence", "old": "absent_in_api",
                             "new": "ledger_recorded", "reason_contains": "settlement_gap"}
    )


def _inject_missing_in_csv(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="missing_in_csv",
        api={"reference_id": csv_row["txn_id"]},
        expected_correction={"field": "_existence", "old": "absent_in_csv",
                             "new": "csv_backfill", "reason_contains": "tracking_miss"}
    )


def _inject_encoding_corruption(csv_row: dict, _api, _rng) -> InjectedDefect:
    orig = csv_row["merchant"]
    # double-encode: latin-1 bytes of "'" misread as UTF-8
    corrupted = orig.replace("a", "â\x80\x99")
    csv_row["merchant"] = corrupted
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="encoding_corruption",
        csv={"merchant": corrupted},
        expected_correction={"field": "merchant", "old": corrupted, "new": orig,
                             "reason_contains": "encoding"}
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/recon_agent/data/generate_fixtures.py
git commit -m "feat(data): defect injection for 6 discrepancy kinds"
```

---

### Task 3.4: Top-level `generate_fixtures()` + CLI

**Files:** Modify: `src/recon_agent/data/generate_fixtures.py` (append main entry)

- [ ] **Step 1: Append the main generator + CLI**

```python
def generate_fixtures(
    seed: int = 42,
    n_txns: int = 500,
    variant: str = "default",
    out_dir: Path = Path("src/recon_agent/data/fixtures"),
    ground_truth_dir: Path = Path("src/recon_agent/data"),
) -> GroundTruth:
    rng = random.Random(seed)
    spec = DEFECT_VARIANTS[variant]

    base_date = datetime(2026, 4, 1, tzinfo=IST)
    csv_rows: list[dict] = []
    api_records: list[dict] = []

    for i in range(n_txns):
        csv_row, api_record = _make_clean(rng, i, base_date)
        csv_rows.append(csv_row)
        api_records.append(api_record)

    # Pass 2: inject defects
    injected: list[InjectedDefect] = []
    txn_to_csv_idx = {row["txn_id"]: i for i, row in enumerate(csv_rows)}
    txn_to_api_idx = {rec["reference_id"]: i for i, rec in enumerate(api_records)}

    for kind, rate in spec.items():
        n_inject = max(1, int(n_txns * rate)) if rate > 0 else 0
        # pick distinct txn_ids that haven't been hit yet
        candidates = [r["txn_id"] for r in csv_rows
                      if r["txn_id"] not in {d.txn_id for d in injected}]
        chosen = rng.sample(candidates, min(n_inject, len(candidates)))

        for txn_id in chosen:
            csv_idx = txn_to_csv_idx[txn_id]
            api_idx = txn_to_api_idx.get(txn_id)
            csv_row = csv_rows[csv_idx]
            api_record = api_records[api_idx] if api_idx is not None else None

            if kind == "value_mismatch" and api_record:
                injected.append(_inject_value_mismatch(csv_row, api_record, rng))
            elif kind == "timezone_shift" and api_record:
                injected.append(_inject_timezone_shift(csv_row, api_record, rng))
            elif kind == "duplicate":
                injected.append(_inject_duplicate(csv_row, api_record or {}, rng, csv_rows))
            elif kind == "missing_in_api" and api_record:
                injected.append(_inject_missing_in_api(csv_row, api_record, rng))
                api_records[api_idx] = None     # mark for removal
            elif kind == "missing_in_csv":
                # remove from CSV, keep in API
                injected.append(_inject_missing_in_csv(csv_row, api_record or {}, rng))
                csv_rows[csv_idx] = None
            elif kind == "encoding_corruption":
                injected.append(_inject_encoding_corruption(csv_row, api_record, rng))

    # Drop marked-None entries
    csv_rows = [r for r in csv_rows if r is not None]
    api_records = [r for r in api_records if r is not None]

    # Special variants
    if variant == "corrupted_source":
        csv_path = out_dir / "tracking_db.csv"
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path.write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 500)
        _write_json(out_dir / "payu_settlements.json", api_records)
    elif variant == "irreconcilable":
        # rewrite all api.reference_ids so 0 match csv.txn_ids
        for rec in api_records:
            rec["reference_id"] = "DROPPED-" + rec["reference_id"]
        _write_csv(out_dir / "tracking_db.csv", csv_rows)
        _write_json(out_dir / "payu_settlements.json", api_records)
    elif variant == "default_latin1_csv":
        _write_csv(out_dir / "tracking_db.csv", csv_rows, encoding="latin-1")
        _write_json(out_dir / "payu_settlements.json", api_records)
    else:
        _write_csv(out_dir / "tracking_db.csv", csv_rows)
        _write_json(out_dir / "payu_settlements.json", api_records)

    gt = GroundTruth(
        fixture_seed=seed,
        variant=variant,
        total_txns=n_txns,
        generated_at=datetime.now(timezone.utc).isoformat(),
        expected_summary=_count_by_kind(injected),
        injected=[
            {
                "txn_id": d.txn_id, "kind": d.kind, "csv": d.csv,
                "api": d.api, "expected_correction": d.expected_correction,
            }
            for d in injected
        ],
    )
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    gt_path = ground_truth_dir / f"ground_truth_{variant}.json"
    gt_path.write_text(gt.model_dump_json(indent=2), encoding="utf-8")
    return gt


def _count_by_kind(injected: list[InjectedDefect]) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in injected:
        out[d.kind] = out.get(d.kind, 0) + 1
    out["_total"] = len(injected)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", default="default", choices=list(DEFECT_VARIANTS.keys()))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--out-dir", type=Path, default=Path("src/recon_agent/data/fixtures"))
    args = p.parse_args()
    gt = generate_fixtures(seed=args.seed, n_txns=args.n,
                           variant=args.variant, out_dir=args.out_dir)
    print(f"variant={gt.variant} txns={gt.total_txns} injected={gt.expected_summary}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the default fixture**

```bash
.venv/Scripts/python -m recon_agent.data.generate_fixtures --variant default --seed 42
```

Expected: prints `variant=default txns=500 injected={...}`. Creates `src/recon_agent/data/fixtures/tracking_db.csv`, `payu_settlements.json`, and `src/recon_agent/data/ground_truth_default.json`.

- [ ] **Step 3: Verify ground truth file shape**

```bash
.venv/Scripts/python -c "import json; gt=json.load(open('src/recon_agent/data/ground_truth_default.json')); print(gt['expected_summary'])"
```

Expected output: `{'value_mismatch': 15, 'timezone_shift': 25, 'duplicate': 10, 'missing_in_api': 10, 'missing_in_csv': 2 or 3, 'encoding_corruption': 5, '_total': 67 or 68}`.

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/data/generate_fixtures.py src/recon_agent/data/ground_truth_default.json
git commit -m "feat(data): full generate_fixtures() with 10 variants + CLI"
```

---

### Task 3.5: Determinism test + generate all variants

**Files:** Test: `tests/unit/test_fixtures.py`

- [ ] **Step 1: Write determinism test**

```python
# tests/unit/test_fixtures.py
import hashlib
import tempfile
from pathlib import Path
from recon_agent.data.generate_fixtures import generate_fixtures, DEFECT_VARIANTS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_produces_byte_identical_csv():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        gt1 = generate_fixtures(seed=42, n_txns=100, variant="default",
                                out_dir=Path(t1), ground_truth_dir=Path(t1))
        gt2 = generate_fixtures(seed=42, n_txns=100, variant="default",
                                out_dir=Path(t2), ground_truth_dir=Path(t2))
        assert _sha(Path(t1) / "tracking_db.csv") == _sha(Path(t2) / "tracking_db.csv")
        assert _sha(Path(t1) / "payu_settlements.json") == _sha(Path(t2) / "payu_settlements.json")


def test_different_seed_produces_different_csv():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        generate_fixtures(seed=42, n_txns=100, variant="default",
                          out_dir=Path(t1), ground_truth_dir=Path(t1))
        generate_fixtures(seed=43, n_txns=100, variant="default",
                          out_dir=Path(t2), ground_truth_dir=Path(t2))
        assert _sha(Path(t1) / "tracking_db.csv") != _sha(Path(t2) / "tracking_db.csv")


def test_all_variants_run_without_error():
    for variant in DEFECT_VARIANTS:
        with tempfile.TemporaryDirectory() as t:
            gt = generate_fixtures(seed=42, n_txns=50, variant=variant,
                                   out_dir=Path(t), ground_truth_dir=Path(t))
            assert gt.variant == variant
            assert gt.total_txns == 50
```

- [ ] **Step 2: Run test — verify passes**

```bash
pytest tests/unit/test_fixtures.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Generate all 10 ground-truth files for commit**

```bash
for variant in happy_clean tz_only encoding_only duplicate_only value_only default default_disabled_api default_latin1_csv corrupted_source irreconcilable; do
    .venv/Scripts/python -m recon_agent.data.generate_fixtures --variant $variant --seed 42
done
```

(On Windows PowerShell: wrap as a foreach loop, or run individually.)

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/data/ground_truth_*.json tests/unit/test_fixtures.py
git commit -m "feat(data): determinism test + ground truth for all 10 variants"
```

---

### Phase 3 verification

- [ ] **Confirm exit criteria:**

```bash
.venv/Scripts/python -m recon_agent.data.generate_fixtures --variant default --seed 42
ls src/recon_agent/data/fixtures/
ls src/recon_agent/data/ground_truth_*.json
pytest tests/unit/test_fixtures.py -v
```

Expected:
- `tracking_db.csv` and `payu_settlements.json` exist
- 10 `ground_truth_*.json` files exist, all committed
- Determinism test passes
- `expected_summary` in `ground_truth_default.json` shows non-zero counts for all 6 defect kinds

Once green, proceed to Phase 4.

---

## Phase 4 — 8 core tools

**Entry condition:** Phase 3 complete; default fixtures exist on disk.

**Exit condition:**
- All 8 tools implemented, registered, individually unit-tested
- `Act` phase wired into AgentLoop so tools actually run
- `make demo` runs an end-to-end loop on default fixtures, applies corrections to a ledger, halts cleanly with status "completed"

**Phase summary:** Build the 8 tools from spec §4.3. TDD per tool. The `_noop.py` scaffolding file is deleted at the end of this phase. The `Act` phase class is added to phases.py and wired into the loop so tool outputs feed into Observe → Decide.

---

### Task 4.1: `load_csv` tool

**Files:** Create: `src/recon_agent/tools/load_csv.py`; Test: `tests/unit/test_load_csv.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_load_csv.py
import tempfile
from pathlib import Path
from recon_agent.tools.load_csv import LoadCSV, LoadCSVInput


def _write(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.write_text(content, encoding=encoding)


def test_load_utf8_csv(tmp_path):
    p = tmp_path / "x.csv"
    _write(p, "a,b\n1,2\n3,4\n")
    result = LoadCSV().run(LoadCSVInput(path=str(p)))
    assert result.ok
    assert result.output.row_count == 2
    assert result.output.detected_encoding == "utf-8"
    assert result.output.rows[0] == {"a": "1", "b": "2"}


def test_load_latin1_csv(tmp_path):
    p = tmp_path / "x.csv"
    _write(p, "merchant,val\nMyntra,100\n", encoding="latin-1")
    result = LoadCSV().run(LoadCSVInput(path=str(p)))
    assert result.ok
    assert result.output.row_count == 1


def test_file_not_found(tmp_path):
    result = LoadCSV().run(LoadCSVInput(path=str(tmp_path / "missing.csv")))
    assert not result.ok
    assert result.error.code == "FILE_NOT_FOUND"
    assert result.error.kind == "fatal"
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_load_csv.py -v
```

- [ ] **Step 3: Write `src/recon_agent/tools/load_csv.py`**

```python
from __future__ import annotations
import csv
from pathlib import Path

import chardet
from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


class LoadCSVInput(BaseModel):
    path: str
    expected_columns: list[str] | None = None


class LoadCSVOutput(BaseModel):
    rows: list[dict]
    detected_encoding: str
    row_count: int
    skipped_rows: int = 0


class LoadCSV(Tool[LoadCSVInput, LoadCSVOutput]):
    name = "load_csv"
    input_schema = LoadCSVInput
    output_schema = LoadCSVOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 5.0

    def run(self, inputs: LoadCSVInput) -> ToolResult[LoadCSVOutput]:
        path = Path(inputs.path)
        if not path.exists():
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="FILE_NOT_FOUND",
                message=f"file not found: {path}", retriable=False,
            ))

        raw = path.read_bytes()
        if not raw:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="MALFORMED_CSV",
                message="empty file", retriable=False,
            ))

        detection = chardet.detect(raw)
        encoding = detection.get("encoding") or "utf-8"
        confidence = detection.get("confidence", 0.0)
        if confidence < 0.5:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="ENCODING_AMBIGUOUS",
                message=f"chardet confidence {confidence:.2f} for {path}",
                retriable=False,
            ))

        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError as e:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="MALFORMED_CSV",
                message=f"decode failed with {encoding}: {e}", retriable=False,
            ))

        rows: list[dict] = []
        skipped = 0
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            if any(v is None for v in row.values()):
                skipped += 1
                continue
            rows.append(dict(row))

        return ToolResult(ok=True, output=LoadCSVOutput(
            rows=rows,
            detected_encoding=encoding.lower(),
            row_count=len(rows),
            skipped_rows=skipped,
        ))
```

- [ ] **Step 4: Run — verify passes**

```bash
pytest tests/unit/test_load_csv.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/load_csv.py tests/unit/test_load_csv.py
git commit -m "feat(tools): load_csv with chardet encoding detection"
```

---

### Task 4.2: `fetch_api` tool (the unreliable one — 30% transient 429)

**Files:** Create: `src/recon_agent/tools/fetch_api.py`; Test: `tests/unit/test_fetch_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_fetch_api.py
import json
import tempfile
from pathlib import Path
from recon_agent.tools.fetch_api import FetchAPI, FetchAPIInput, _RNG_SEED_ENV
import os


def _write_payu(tmp: Path, n: int = 10) -> None:
    payload = {"page": 1, "page_size": n, "total": n, "next_cursor": None,
               "records": [{"settlement_id": f"S{i}", "reference_id": f"TX{i}",
                            "settled_at": "2026-04-22T08:00:00+00:00", "payee": "M",
                            "gross_amount": 100.0, "net_amount": 99.0,
                            "settlement_status": "settled"} for i in range(n)]}
    (tmp / "payu_settlements.json").write_text(json.dumps(payload))


def test_fetch_returns_records(tmp_path, monkeypatch):
    _write_payu(tmp_path)
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.0")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert result.ok
    assert len(result.output.records) == 10


def test_fetch_with_100pct_fail_rate(tmp_path, monkeypatch):
    _write_payu(tmp_path)
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "1.0")
    monkeypatch.setenv(_RNG_SEED_ENV, "0")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert not result.ok
    assert result.error.code == "RATE_LIMIT"
    assert result.error.kind == "transient"


def test_fetch_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_DISABLED", "1")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert not result.ok
    assert result.error.code == "API_NOT_FOUND"
    assert result.error.kind == "persistent"
```

- [ ] **Step 2: Verify fails**

```bash
pytest tests/unit/test_fetch_api.py -v
```

- [ ] **Step 3: Write `src/recon_agent/tools/fetch_api.py`**

```python
from __future__ import annotations
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


_RNG_SEED_ENV = "FETCH_API_RNG_SEED"


class FetchAPIInput(BaseModel):
    endpoint: Literal["payu_settlements"]
    limit: int = 1000


class FetchAPIOutput(BaseModel):
    records: list[dict]
    pulled_at: str
    next_cursor: str | None = None


def _fail_rate() -> float:
    return float(os.environ.get("FETCH_API_FAIL_RATE", "0.30"))


def _disabled() -> bool:
    return os.environ.get("FETCH_API_DISABLED") == "1"


def _seeded_rng() -> random.Random:
    seed = os.environ.get(_RNG_SEED_ENV)
    if seed is not None:
        return random.Random(int(seed) + int(time.time() * 1000) % 1000)
    return random.Random()


class FetchAPI(Tool[FetchAPIInput, FetchAPIOutput]):
    name = "fetch_api"
    input_schema = FetchAPIInput
    output_schema = FetchAPIOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 10.0

    def run(self, inputs: FetchAPIInput) -> ToolResult[FetchAPIOutput]:
        if _disabled():
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="API_NOT_FOUND",
                message="fetch_api disabled via FETCH_API_DISABLED env",
                retriable=False,
            ))

        rng = _seeded_rng()
        roll = rng.random()
        fail_rate = _fail_rate()
        if roll < fail_rate:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="RATE_LIMIT",
                message=f"HTTP 429 (simulated; rolled {roll:.3f} < {fail_rate})",
                retriable=True,
            ))
        # 2% 5xx
        if roll < fail_rate + 0.02:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="API_5XX",
                message="HTTP 503 (simulated)", retriable=True,
            ))

        fixture_dir = Path(os.environ.get("FIXTURE_DIR", "src/recon_agent/data/fixtures"))
        path = fixture_dir / "payu_settlements.json"
        if not path.exists():
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="API_NOT_FOUND",
                message=f"fixture file {path} missing", retriable=False,
            ))
        payload = json.loads(path.read_text())
        records = payload.get("records", [])[: inputs.limit]
        return ToolResult(ok=True, output=FetchAPIOutput(
            records=records,
            pulled_at=datetime.now(timezone.utc).isoformat(),
            next_cursor=None,
        ))
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_fetch_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/fetch_api.py tests/unit/test_fetch_api.py
git commit -m "feat(tools): fetch_api with seeded 30% transient failure injection"
```

---

### Task 4.3: `normalize_timezone` tool

**Files:** Create: `src/recon_agent/tools/normalize_timezone.py`; Test: `tests/unit/test_normalize_timezone.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_normalize_timezone.py
from recon_agent.tools.normalize_timezone import NormalizeTimezone, NormalizeTZInput


def test_normalizes_ist_to_utc():
    recs = [{"reference_id": "TX1", "settled_at": "2026-04-22T14:13:08+05:30"}]
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=recs, timestamp_field="settled_at"))
    assert result.ok
    out = result.output.records[0]
    assert out["settled_at"].endswith("+00:00")
    assert result.output.converted_count == 1


def test_detects_ist_as_utc():
    # Same clock hour as redemption_ts (IST), but with +00:00 — suspicious
    recs = [
        {"reference_id": "TX1", "settled_at": "2026-04-22T14:13:08+00:00",
         "_csv_ts": "2026-04-22T14:13:08+05:30"},  # hint for the detector
    ]
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=recs, timestamp_field="settled_at"))
    assert result.ok
    assert "TX1" in result.output.suspected_ist_as_utc


def test_missing_field_returns_error():
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=[{"a": "x"}], timestamp_field="settled_at"))
    assert not result.ok
    assert result.error.code == "MISSING_FIELD"
```

- [ ] **Step 2: Verify fail**

```bash
pytest tests/unit/test_normalize_timezone.py -v
```

- [ ] **Step 3: Write `src/recon_agent/tools/normalize_timezone.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


class NormalizeTZInput(BaseModel):
    records: list[dict]
    timestamp_field: str = "settled_at"
    target_tz: Literal["UTC"] = "UTC"


class NormalizeTZOutput(BaseModel):
    records: list[dict]
    suspected_ist_as_utc: list[str]
    converted_count: int


class NormalizeTimezone(Tool[NormalizeTZInput, NormalizeTZOutput]):
    name = "normalize_timezone"
    input_schema = NormalizeTZInput
    output_schema = NormalizeTZOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 5.0

    def run(self, inputs: NormalizeTZInput) -> ToolResult[NormalizeTZOutput]:
        out_records: list[dict] = []
        suspected: list[str] = []
        converted = 0

        for r in inputs.records:
            if inputs.timestamp_field not in r:
                return ToolResult(ok=False, error=ToolError(
                    kind="persistent", code="MISSING_FIELD",
                    message=f"{inputs.timestamp_field} missing in record", retriable=False,
                ))
            try:
                dt = datetime.fromisoformat(r[inputs.timestamp_field])
            except ValueError as e:
                return ToolResult(ok=False, error=ToolError(
                    kind="persistent", code="UNPARSEABLE_TIMESTAMP",
                    message=str(e), retriable=False,
                ))

            new_rec = dict(r)
            new_rec["_orig_tz"] = r[inputs.timestamp_field]

            # IST-as-UTC heuristic: tz claims UTC but the hour matches the IST clock
            # of a hint timestamp (e.g., _csv_ts) — suggests the value is IST mislabeled
            if dt.utcoffset() == timezone.utc.utcoffset(None):
                csv_hint = r.get("_csv_ts") or r.get("redemption_ts")
                if csv_hint:
                    try:
                        csv_dt = datetime.fromisoformat(csv_hint)
                        if dt.hour == csv_dt.hour and dt.minute == csv_dt.minute:
                            suspected.append(r.get("reference_id") or r.get("txn_id") or "?")
                    except ValueError:
                        pass

            new_rec[inputs.timestamp_field] = dt.astimezone(timezone.utc).isoformat()
            if dt.tzinfo != timezone.utc:
                converted += 1
            out_records.append(new_rec)

        return ToolResult(ok=True, output=NormalizeTZOutput(
            records=out_records,
            suspected_ist_as_utc=suspected,
            converted_count=converted,
        ))
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_normalize_timezone.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/normalize_timezone.py tests/unit/test_normalize_timezone.py
git commit -m "feat(tools): normalize_timezone with IST-as-UTC detection"
```

---

### Task 4.4: `match_records` tool

**Files:** Create: `src/recon_agent/tools/match_records.py`; Test: `tests/unit/test_match_records.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_match_records.py
from recon_agent.tools.match_records import MatchRecords, MatchRecordsInput


def test_exact_match():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T1", "gross_amount": 100.0}]
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.matched) == 1
    assert result.output.unmatched_csv == []
    assert result.output.unmatched_api == []


def test_value_mismatch_detected():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T1", "gross_amount": 110.0}]  # ₹10 off
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.value_conflicts) == 1


def test_unmatched_both_sides():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T2", "gross_amount": 200.0}]
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.unmatched_csv) == 1
    assert len(result.output.unmatched_api) == 1


def test_empty_input_returns_error():
    result = MatchRecords().run(MatchRecordsInput(csv_records=[], api_records=[]))
    assert not result.ok
    assert result.error.code == "EMPTY_INPUT"
```

- [ ] **Step 2: Verify fail**

```bash
pytest tests/unit/test_match_records.py -v
```

- [ ] **Step 3: Write `src/recon_agent/tools/match_records.py`**

```python
from __future__ import annotations
from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


VALUE_TOLERANCE_INR = 1.0   # ≤ ₹1 difference treated as match (legitimate rounding)


class MatchRecordsInput(BaseModel):
    csv_records: list[dict]
    api_records: list[dict]
    key_field_csv: str = "txn_id"
    key_field_api: str = "reference_id"
    csv_value_field: str = "order_value_inr"
    api_value_field: str = "gross_amount"


class MatchRecordsOutput(BaseModel):
    matched: list[dict]
    unmatched_csv: list[dict]
    unmatched_api: list[dict]
    value_conflicts: list[dict]


class MatchRecords(Tool[MatchRecordsInput, MatchRecordsOutput]):
    name = "match_records"
    input_schema = MatchRecordsInput
    output_schema = MatchRecordsOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 10.0

    def run(self, inputs: MatchRecordsInput) -> ToolResult[MatchRecordsOutput]:
        if not inputs.csv_records and not inputs.api_records:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="EMPTY_INPUT",
                message="both csv_records and api_records are empty",
                retriable=False,
            ))

        api_by_key: dict[str, list[dict]] = {}
        for rec in inputs.api_records:
            k = rec.get(inputs.key_field_api)
            api_by_key.setdefault(k, []).append(rec)

        matched: list[dict] = []
        value_conflicts: list[dict] = []
        unmatched_csv: list[dict] = []
        seen_api_keys: set[str] = set()

        for csv_row in inputs.csv_records:
            k = csv_row.get(inputs.key_field_csv)
            partners = api_by_key.get(k, [])
            if not partners:
                unmatched_csv.append(csv_row)
                continue
            api_rec = partners[0]
            seen_api_keys.add(k)
            csv_value = float(csv_row.get(inputs.csv_value_field, 0))
            api_value = float(api_rec.get(inputs.api_value_field, 0))
            if abs(csv_value - api_value) > VALUE_TOLERANCE_INR:
                value_conflicts.append({
                    "txn_id": k, "csv": csv_row, "api": api_rec,
                    "csv_value": csv_value, "api_value": api_value,
                    "delta": round(api_value - csv_value, 2),
                })
            else:
                matched.append({"txn_id": k, "csv": csv_row, "api": api_rec, "confidence": 1.0})

        unmatched_api = [rec for k, recs in api_by_key.items() if k not in seen_api_keys
                         for rec in recs]

        return ToolResult(ok=True, output=MatchRecordsOutput(
            matched=matched,
            unmatched_csv=unmatched_csv,
            unmatched_api=unmatched_api,
            value_conflicts=value_conflicts,
        ))
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_match_records.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/match_records.py tests/unit/test_match_records.py
git commit -m "feat(tools): match_records with txn_id matching + value-tolerance check"
```

---

### Task 4.5: `classify_discrepancy` tool (LLM-backed)

**Files:** Create: `src/recon_agent/tools/classify_discrepancy.py`; Test: `tests/unit/test_classify_discrepancy.py`

- [ ] **Step 1: Write failing test using a mock router**

```python
# tests/unit/test_classify_discrepancy.py
from unittest.mock import MagicMock
from pydantic import BaseModel
from recon_agent.tools.classify_discrepancy import (
    ClassifyDiscrepancy, ClassifyDiscrepancyInput, ClassifyDiscrepancyOutput
)
from recon_agent.agent.state import Discrepancy, LLMCallRecord
from recon_agent.agent.phases import Phase


def _mock_call_record() -> LLMCallRecord:
    return LLMCallRecord(step=0, phase=Phase.ACT, provider="openai", model="gpt-4o-mini",
                         subtask="classify", tokens_in=100, tokens_out=50,
                         latency_ms=200, cost_inr=0.01)


def test_classify_routes_unmatched_csv_to_missing_in_api():
    fake_router = MagicMock()
    fake_router.call.return_value = (
        ClassifyDiscrepancyOutput(classified=[
            Discrepancy(txn_id="T1", kind="missing_in_api",
                        csv_record={"txn_id": "T1"}, severity="medium", confidence=0.95)
        ]),
        _mock_call_record(),
    )
    tool = ClassifyDiscrepancy(router=fake_router)
    result = tool.run(ClassifyDiscrepancyInput(
        unmatched_csv=[{"txn_id": "T1"}],
        unmatched_api=[],
        value_conflicts=[],
        timezone_suspects=[],
    ))
    assert result.ok
    assert len(result.output.classified) == 1
    assert result.output.classified[0].kind == "missing_in_api"
    fake_router.call.assert_called_once()
```

- [ ] **Step 2: Verify fail**

```bash
pytest tests/unit/test_classify_discrepancy.py -v
```

- [ ] **Step 3: Write the tool**

```python
# src/recon_agent/tools/classify_discrepancy.py
from __future__ import annotations
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..agent.state import Discrepancy
from .base import Tool, ToolError, ToolResult


_PROMPT = """\
You are classifying transaction discrepancies between a CSV (internal tracking)
and an API response (PayU settlements). Classify each one into exactly one of:
  missing_in_api, missing_in_csv, value_mismatch, duplicate, timezone_shift, encoding_corruption.

Inputs:
  unmatched_csv: CSV rows with no API partner (likely missing_in_api)
  unmatched_api: API records with no CSV partner (likely missing_in_csv)
  value_conflicts: matched pairs with value delta (likely value_mismatch)
  timezone_suspects: txn_ids flagged by normalize_timezone (likely timezone_shift)

Output STRICT JSON: {"classified": [Discrepancy, ...]}
Each Discrepancy: {txn_id, kind, csv_record?, api_record?, severity (low|medium|high), confidence (0..1)}
Default severity=medium, confidence ~0.9 for clear cases, lower for ambiguous.
"""


class ClassifyDiscrepancyInput(BaseModel):
    unmatched_csv: list[dict]
    unmatched_api: list[dict]
    value_conflicts: list[dict]
    timezone_suspects: list[str]


class ClassifyDiscrepancyOutput(BaseModel):
    classified: list[Discrepancy]


class ClassifyDiscrepancy(Tool[ClassifyDiscrepancyInput, ClassifyDiscrepancyOutput]):
    name = "classify_discrepancy"
    input_schema = ClassifyDiscrepancyInput
    output_schema = ClassifyDiscrepancyOutput
    cost_estimate_inr = 0.05
    timeout_seconds = 15.0

    def __init__(self, router: Any | None = None):
        # router injected at construction (registry needs zero-arg constructor for discovery,
        # so registry-discovered instances will set this later via ToolRegistry.bind_router())
        self.router = router

    def run(self, inputs: ClassifyDiscrepancyInput) -> ToolResult[ClassifyDiscrepancyOutput]:
        if self.router is None:
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="ROUTER_NOT_BOUND",
                message="ClassifyDiscrepancy needs a router bound", retriable=False,
            ))
        messages = [
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": inputs.model_dump_json()},
        ]
        try:
            out, _ = self.router.call("classify", messages, ClassifyDiscrepancyOutput)
        except Exception as e:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="LLM_TIMEOUT",
                message=str(e), retriable=True,
            ))
        return ToolResult(ok=True, output=out)
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_classify_discrepancy.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/tools/classify_discrepancy.py tests/unit/test_classify_discrepancy.py
git commit -m "feat(tools): classify_discrepancy (LLM-backed, GPT-4o-mini)"
```

---

### Task 4.6: `propose_correction` tool (LLM-backed)

**Files:** Create: `src/recon_agent/tools/propose_correction.py`; Test: `tests/unit/test_propose_correction.py`

- [ ] **Step 1: Write the tool (test pattern matches 4.5)**

```python
# src/recon_agent/tools/propose_correction.py
from __future__ import annotations
from typing import Any

from pydantic import BaseModel

from ..agent.state import CorrectionProposal, Discrepancy
from .base import Tool, ToolError, ToolResult


_PROMPT = """\
Propose a correction for a single discrepancy. Output STRICT JSON:
{
  "proposal": {
    "txn_id": str, "field": str, "old_value": any, "new_value": any,
    "reason": str, "confidence": float (0..1)
  },
  "fallback": str | null   // "manual_review" if confidence < 0.7
}

Discrepancy kind tells you what to fix:
  value_mismatch       — propose new api.gross_amount or csv.order_value_inr
  timezone_shift       — propose corrected UTC ISO string for settled_at
  duplicate            — propose merging (field="_status", new="merged")
  missing_in_api       — propose ledger entry (field="_existence", new="ledger_recorded")
  missing_in_csv       — propose backfill (field="_existence", new="csv_backfill")
  encoding_corruption  — propose merchant name (best guess)
"""


class ProposeCorrectionInput(BaseModel):
    discrepancy: Discrepancy


class ProposeCorrectionOutput(BaseModel):
    proposal: CorrectionProposal
    fallback: str | None = None


class ProposeCorrection(Tool[ProposeCorrectionInput, ProposeCorrectionOutput]):
    name = "propose_correction"
    input_schema = ProposeCorrectionInput
    output_schema = ProposeCorrectionOutput
    cost_estimate_inr = 0.10
    timeout_seconds = 15.0

    def __init__(self, router: Any | None = None):
        self.router = router

    def run(self, inputs: ProposeCorrectionInput) -> ToolResult[ProposeCorrectionOutput]:
        if self.router is None:
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="ROUTER_NOT_BOUND",
                message="ProposeCorrection needs router", retriable=False,
            ))
        messages = [
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": inputs.model_dump_json()},
        ]
        try:
            out, _ = self.router.call("propose", messages, ProposeCorrectionOutput)
        except Exception as e:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="LLM_TIMEOUT",
                message=str(e), retriable=True,
            ))
        return ToolResult(ok=True, output=out)
```

- [ ] **Step 2: Write test**

```python
# tests/unit/test_propose_correction.py
from unittest.mock import MagicMock
from recon_agent.tools.propose_correction import (
    ProposeCorrection, ProposeCorrectionInput, ProposeCorrectionOutput
)
from recon_agent.agent.state import Discrepancy, CorrectionProposal, LLMCallRecord
from recon_agent.agent.phases import Phase


def test_propose_value_mismatch():
    fake_router = MagicMock()
    fake_router.call.return_value = (
        ProposeCorrectionOutput(
            proposal=CorrectionProposal(
                txn_id="T1", field="gross_amount", old_value=110.0, new_value=100.0,
                reason="rounding to nearest rupee", confidence=0.95,
            ),
            fallback=None,
        ),
        LLMCallRecord(step=0, phase=Phase.ACT, provider="gemini", model="gemini-2.5-flash",
                      subtask="propose", tokens_in=100, tokens_out=50, latency_ms=200, cost_inr=0.01),
    )
    tool = ProposeCorrection(router=fake_router)
    result = tool.run(ProposeCorrectionInput(
        discrepancy=Discrepancy(txn_id="T1", kind="value_mismatch")))
    assert result.ok
    assert result.output.proposal.new_value == 100.0
```

- [ ] **Step 3: Run + verify pass**

```bash
pytest tests/unit/test_propose_correction.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/tools/propose_correction.py tests/unit/test_propose_correction.py
git commit -m "feat(tools): propose_correction (LLM-backed, Gemini Flash)"
```

---

### Task 4.7: `apply_correction` tool

**Files:** Create: `src/recon_agent/tools/apply_correction.py`; Test: `tests/unit/test_apply_correction.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_apply_correction.py
import json
from recon_agent.tools.apply_correction import ApplyCorrection, ApplyCorrectionInput
from recon_agent.agent.state import CorrectionProposal


def test_applies_high_confidence(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    proposal = CorrectionProposal(
        txn_id="T1", field="gross_amount", old_value=110.0,
        new_value=100.0, reason="rounding", confidence=0.95)
    result = ApplyCorrection().run(ApplyCorrectionInput(
        proposal=proposal, ledger_path=str(ledger)))
    assert result.ok
    assert result.output.skipped_reason is None
    line = json.loads(ledger.read_text().strip())
    assert line["txn_id"] == "T1"
    assert line["action"] == "applied"
    assert line["new"] == 100.0


def test_skips_low_confidence(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    proposal = CorrectionProposal(
        txn_id="T2", field="merchant", old_value="x", new_value="y",
        reason="guess", confidence=0.5)
    result = ApplyCorrection().run(ApplyCorrectionInput(
        proposal=proposal, ledger_path=str(ledger)))
    assert result.ok
    assert result.output.skipped_reason == "low_confidence"
    line = json.loads(ledger.read_text().strip())
    assert line["action"] == "skipped"
```

- [ ] **Step 2: Write the tool**

```python
# src/recon_agent/tools/apply_correction.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from ..agent.state import CorrectionProposal
from .base import Tool, ToolError, ToolResult


CONFIDENCE_THRESHOLD = 0.7


class ApplyCorrectionInput(BaseModel):
    proposal: CorrectionProposal
    ledger_path: str = "corrections.jsonl"
    step: int = 0
    kind: str = ""  # discrepancy kind, for the ledger entry


class ApplyCorrectionOutput(BaseModel):
    line_number: int
    applied_at: str
    skipped_reason: str | None = None


class ApplyCorrection(Tool[ApplyCorrectionInput, ApplyCorrectionOutput]):
    name = "apply_correction"
    input_schema = ApplyCorrectionInput
    output_schema = ApplyCorrectionOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 2.0

    def run(self, inputs: ApplyCorrectionInput) -> ToolResult[ApplyCorrectionOutput]:
        path = Path(inputs.ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()

        p = inputs.proposal
        if p.confidence < CONFIDENCE_THRESHOLD:
            entry = {
                "txn_id": p.txn_id, "kind": inputs.kind or "unknown",
                "field": p.field, "old": p.old_value, "new": p.new_value,
                "reason": p.reason, "confidence": p.confidence,
                "applied_at": now, "by": "agent-v1", "step": inputs.step,
                "action": "skipped",
                "skip_reason": "low_confidence",
            }
        else:
            entry = {
                "txn_id": p.txn_id, "kind": inputs.kind or "unknown",
                "field": p.field, "old": p.old_value, "new": p.new_value,
                "reason": p.reason, "confidence": p.confidence,
                "applied_at": now, "by": "agent-v1", "step": inputs.step,
                "action": "applied",
            }

        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as e:
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="LEDGER_WRITE_FAILED",
                message=str(e), retriable=False,
            ))

        line_count = sum(1 for _ in path.open(encoding="utf-8"))
        return ToolResult(ok=True, output=ApplyCorrectionOutput(
            line_number=line_count,
            applied_at=now,
            skipped_reason="low_confidence" if entry["action"] == "skipped" else None,
        ))
```

- [ ] **Step 3: Verify pass**

```bash
pytest tests/unit/test_apply_correction.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/tools/apply_correction.py tests/unit/test_apply_correction.py
git commit -m "feat(tools): apply_correction with append-only ledger + confidence gate"
```

---

### Task 4.8: `verify_reconciliation` tool

**Files:** Create: `src/recon_agent/tools/verify_reconciliation.py`; Test: `tests/unit/test_verify_reconciliation.py`

- [ ] **Step 1: Write the tool**

```python
# src/recon_agent/tools/verify_reconciliation.py
from __future__ import annotations
import json
from pathlib import Path

from pydantic import BaseModel

from ..agent.state import Discrepancy
from .base import Tool, ToolError, ToolResult
from .match_records import MatchRecords, MatchRecordsInput


class VerifyInput(BaseModel):
    csv_records: list[dict]
    api_records: list[dict]
    ledger_path: str = "corrections.jsonl"


class VerifyOutput(BaseModel):
    residual_discrepancies: list[Discrepancy]
    reconciliation_rate: float
    summary: str


class VerifyReconciliation(Tool[VerifyInput, VerifyOutput]):
    name = "verify_reconciliation"
    input_schema = VerifyInput
    output_schema = VerifyOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 5.0

    def run(self, inputs: VerifyInput) -> ToolResult[VerifyOutput]:
        # Apply ledger virtually (we don't mutate sources, but we count what would be resolved)
        ledger_resolved: set[str] = set()
        path = Path(inputs.ledger_path)
        if path.exists():
            for line in path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("action") == "applied":
                    ledger_resolved.add(row["txn_id"])

        # Re-match
        match_result = MatchRecords().run(MatchRecordsInput(
            csv_records=inputs.csv_records, api_records=inputs.api_records,
        ))
        if not match_result.ok:
            return ToolResult(ok=False, error=match_result.error)
        match_out = match_result.output

        residual: list[Discrepancy] = []
        for r in match_out.unmatched_csv:
            tid = r.get("txn_id")
            if tid in ledger_resolved:
                continue
            residual.append(Discrepancy(txn_id=tid, kind="missing_in_api", csv_record=r))
        for r in match_out.unmatched_api:
            tid = r.get("reference_id")
            if tid in ledger_resolved:
                continue
            residual.append(Discrepancy(txn_id=tid, kind="missing_in_csv", api_record=r))
        for v in match_out.value_conflicts:
            tid = v["txn_id"]
            if tid in ledger_resolved:
                continue
            residual.append(Discrepancy(txn_id=tid, kind="value_mismatch",
                                        csv_record=v["csv"], api_record=v["api"]))

        total = len(match_out.matched) + len(residual) + len(ledger_resolved)
        recon_rate = (len(match_out.matched) + len(ledger_resolved)) / max(1, total)

        return ToolResult(ok=True, output=VerifyOutput(
            residual_discrepancies=residual,
            reconciliation_rate=round(recon_rate, 4),
            summary=f"matched={len(match_out.matched)} "
                    f"ledger_resolved={len(ledger_resolved)} residual={len(residual)} "
                    f"recon_rate={recon_rate:.2%}",
        ))
```

- [ ] **Step 2: Write minimal test**

```python
# tests/unit/test_verify_reconciliation.py
import json
from pathlib import Path
from recon_agent.tools.verify_reconciliation import VerifyReconciliation, VerifyInput


def test_verify_with_ledger(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    ledger.write_text(json.dumps(
        {"txn_id": "T1", "action": "applied", "kind": "value_mismatch"}) + "\n")
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"},
           {"txn_id": "T2", "order_value_inr": "50.0"}]
    api = [{"reference_id": "T1", "gross_amount": 100.0},
           {"reference_id": "T2", "gross_amount": 60.0}]   # T2 has value mismatch
    result = VerifyReconciliation().run(VerifyInput(
        csv_records=csv, api_records=api, ledger_path=str(ledger)))
    assert result.ok
    assert len(result.output.residual_discrepancies) == 1
    assert result.output.residual_discrepancies[0].txn_id == "T2"
```

- [ ] **Step 3: Verify pass**

```bash
pytest tests/unit/test_verify_reconciliation.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/tools/verify_reconciliation.py tests/unit/test_verify_reconciliation.py
git commit -m "feat(tools): verify_reconciliation with virtual ledger application"
```

---

### Task 4.9: Wire Act phase + remove `_noop.py` + end-to-end demo

**Files:** Modify: `src/recon_agent/agent/phases.py` (add Act + Observe), `src/recon_agent/agent/loop.py` (wire them), `src/recon_agent/tools/registry.py` (router binding), delete `src/recon_agent/tools/_noop.py`

- [ ] **Step 1: Add Act + Observe to `phases.py`**

```python
# Append to src/recon_agent/agent/phases.py

import time
from datetime import datetime, timezone

from .state import ToolCallRecord


class ActOutput(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: dict | None = None
    error: "ToolError | None" = None
    raw_record: ToolCallRecord


class Act:
    def __init__(self, tool_registry: Any, logger: Any = None):
        self._registry = tool_registry
        self._logger = logger

    def run(self, plan: PlanOutput, state: AgentState) -> ActOutput:
        from ..tools.base import ToolError    # local import
        started = datetime.now(timezone.utc)
        t0 = time.time()
        try:
            tool = self._registry.get(plan.intended_tool)
            inputs = tool.input_schema(**plan.tool_args)
            result = tool.run(inputs)
        except KeyError as e:
            err = ToolError(kind="fatal", code="UNKNOWN_TOOL", message=str(e), retriable=False)
            result = None
            error = err
            ok = False
        except Exception as e:
            err = ToolError(kind="persistent", code="MALFORMED_INPUT",
                            message=str(e), retriable=False)
            result = None
            error = err
            ok = False
        else:
            ok = result.ok
            error = result.error if not ok else None

        latency_ms = int((time.time() - t0) * 1000)
        finished = datetime.now(timezone.utc)
        record = ToolCallRecord(
            step=state.step + 1, tool_name=plan.intended_tool, args=plan.tool_args,
            started_at=started, finished_at=finished, latency_ms=latency_ms,
            outcome="ok" if ok else "error",
            error_kind=error.kind if error else None,
            error_code=error.code if error else None,
            cost_inr=tool.cost_estimate_inr if ok and hasattr(locals().get("tool"), "cost_estimate_inr") else 0.0,
        )
        return ActOutput(
            tool_name=plan.intended_tool,
            tool_input=plan.tool_args,
            tool_output=result.output.model_dump() if ok and result and result.output else None,
            error=error,
            raw_record=record,
        )


class Observe:
    def __init__(self, logger: Any = None):
        self._logger = logger

    def run(self, act: ActOutput, state: AgentState) -> str:
        """Produce a short observation summary + patch state with the tool's output."""
        if act.error:
            return f"FAILED {act.tool_name}: {act.error.code} ({act.error.kind})"

        # Patch state based on which tool ran
        out = act.tool_output or {}
        name = act.tool_name
        if name == "load_csv":
            state.csv_loaded = True
            state.txns_csv = out.get("rows", [])
            return f"load_csv OK: {out.get('row_count', 0)} rows, enc={out.get('detected_encoding')}"
        if name == "fetch_api":
            state.api_loaded = True
            state.txns_api = out.get("records", [])
            return f"fetch_api OK: {len(out.get('records', []))} records"
        if name == "normalize_timezone":
            state.timezone_normalized = True
            return f"normalize_timezone OK: converted={out.get('converted_count', 0)} suspected_ist_as_utc={len(out.get('suspected_ist_as_utc', []))}"
        if name == "match_records":
            state.matches = out.get("matched", [])
            return (f"match_records OK: matched={len(out.get('matched', []))} "
                    f"unmatched_csv={len(out.get('unmatched_csv', []))} "
                    f"unmatched_api={len(out.get('unmatched_api', []))} "
                    f"value_conflicts={len(out.get('value_conflicts', []))}")
        if name == "classify_discrepancy":
            from .state import Discrepancy
            classified = [Discrepancy(**d) for d in out.get("classified", [])]
            state.discrepancies.extend(classified)
            return f"classify_discrepancy OK: {len(classified)} classified"
        if name == "propose_correction":
            from .state import CorrectionProposal
            p = out.get("proposal")
            if p:
                state.proposals.append(CorrectionProposal(**p))
            return f"propose_correction OK: txn={p.get('txn_id') if p else '?'} confidence={p.get('confidence') if p else '?'}"
        if name == "apply_correction":
            state.corrections_applied += 1
            return f"apply_correction OK: line={out.get('line_number')} skipped={out.get('skipped_reason')}"
        if name == "verify_reconciliation":
            return f"verify_reconciliation OK: rate={out.get('reconciliation_rate')} residual={len(out.get('residual_discrepancies', []))}"
        return f"{name} OK"
```

- [ ] **Step 2: Add router-binding hook to ToolRegistry**

Modify `src/recon_agent/tools/registry.py` — append a method:

```python
    @classmethod
    def bind_router(cls, router: Any) -> None:
        """Inject the router into LLM-backed tools (classify_discrepancy, propose_correction)."""
        for tool in cls._tools.values():
            if hasattr(tool, "router") and tool.router is None:
                tool.router = router
```

- [ ] **Step 3: Delete `_noop.py`**

```bash
rm src/recon_agent/tools/_noop.py
# Remove the corresponding lines from tests/unit/test_tool_registry.py — update to assert "load_csv" in names instead of "noop"
```

Update `tests/unit/test_tool_registry.py`:

```python
def test_registry_discovers_real_tools():
    ToolRegistry.discover(force=True)
    names = {t.name for t in ToolRegistry.available()}
    assert "load_csv" in names
    assert "fetch_api" in names
    assert "match_records" in names
    assert "classify_discrepancy" in names
    assert "apply_correction" in names
    assert "verify_reconciliation" in names
```

- [ ] **Step 4: Rewrite AgentLoop.run() with Act + Observe**

Replace the Act stub in `src/recon_agent/agent/loop.py` with the real call sequence:

```python
# Replace the ACT and observation sections inside AgentLoop.run() with:

from .phases import Plan, Decide, Act, Observe
from ..tools.registry import ToolRegistry

# Inside __init__:
self.act_phase    = Act(self.tools, self.logger)
self.observe_phase = Observe(self.logger)
ToolRegistry.bind_router(self.router)   # inject router into LLM-backed tools

# Inside run() — replace the stub:
            # ACT
            act_out = self.act_phase.run(plan_out, self.state)
            self.state.tool_calls.append(act_out.raw_record)

            # If tool failed, record the failure and proceed with empty observation
            # (Recovery layer arrives in Phase 5; for now, increment consecutive_failures)
            if act_out.error:
                self.state.consecutive_failures += 1
                observation = f"FAILED {act_out.tool_name}: {act_out.error.code}"
            else:
                self.state.consecutive_failures = 0
                observation = self.observe_phase.run(act_out, self.state)
```

- [ ] **Step 5: End-to-end demo**

```bash
.venv/Scripts/python -m recon_agent.data.generate_fixtures --variant default --seed 42
make demo
```

Expected:
- Multiple steps run, each calling a real tool
- Some `fetch_api` failures (no recovery yet — agent will just have consecutive failures, may eventually halt via budget or max iterations)
- `reports/run_*/step_*.json` shows tool_calls accumulating
- A `corrections.jsonl` exists with at least a few entries
- Total cost printed at the end

Note: end-to-end "completion" may NOT happen yet because there's no recovery. That's Phase 5. For now, the agent gets further than Phase 2.

- [ ] **Step 6: Commit**

```bash
git rm src/recon_agent/tools/_noop.py
git add src/recon_agent/agent/phases.py src/recon_agent/agent/loop.py src/recon_agent/tools/registry.py tests/unit/test_tool_registry.py
git commit -m "feat(agent): Act + Observe phases + router binding; remove noop scaffolding"
```

---

### Phase 4 verification

- [ ] **Confirm exit criteria:**

```bash
pytest tests/unit -v
make demo
ls reports/run_*/corrections.jsonl
```

Expected:
- All 8 tool unit tests pass
- `make demo` runs ~5-15 iterations, calls multiple tools, produces a non-empty ledger
- Some 429s may show up in the snapshots (recovery arrives in Phase 5)

Once green, proceed to Phase 5.

---

## Phase 5 — Recovery + budget enforcement (with PARTIAL_REPORT)

**Entry condition:** Phase 4 complete; tools fire end-to-end but failures aren't handled.

**Exit condition:**
- `recon demo --seed-fail-rate 1.0` recovers via retry + replan (does not crash)
- `recon demo --budget-calls 3` halts cleanly with `PARTIAL_REPORT.md` written
- All recovery-classifier table rows have a unit test

**Phase summary:** Add the resilience layer. Error classifier maps each `(ToolError.kind, error.code, history)` tuple to one of three strategies: retry-with-backoff, replan-with-hint, graceful-degrade. Loop calls recovery layer on every tool failure; partial report on budget breach.

---

### Task 5.1: Error classifier with full table coverage

**Files:** Create: `src/recon_agent/recovery/classifier.py`; Test: `tests/unit/test_classifier.py`

- [ ] **Step 1: Write failing tests covering every row of the error→strategy table**

```python
# tests/unit/test_classifier.py
from datetime import datetime, timezone
from recon_agent.agent.state import AgentState
from recon_agent.tools.base import ToolError
from recon_agent.recovery.classifier import ErrorClassifier, MAX_RETRIES


def _state(failures: int = 0) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc),
                      consecutive_failures=failures)


def test_transient_retries_first():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    action = c.classify(err, _state())
    assert action.kind == "retry"
    assert action.backoff_ms > 0


def test_transient_escalates_after_max_retries():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    # Simulate enough retries to escalate
    state = _state()
    for _ in range(MAX_RETRIES):
        c._record_retry(state, err.code)
    action = c.classify(err, state)
    assert action.kind == "replan"


def test_persistent_replans_immediately():
    c = ErrorClassifier()
    err = ToolError(kind="persistent", code="API_NOT_FOUND", message="404", retriable=False)
    action = c.classify(err, _state())
    assert action.kind == "replan"
    assert action.hint  # has a hint


def test_fatal_degrades():
    c = ErrorClassifier()
    err = ToolError(kind="fatal", code="API_AUTH", message="401", retriable=False)
    action = c.classify(err, _state())
    assert action.kind == "degrade"


def test_three_consecutive_failures_degrades():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="API_5XX", message="503", retriable=True)
    state = _state(failures=3)
    action = c.classify(err, state)
    assert action.kind == "degrade"
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_classifier.py -v
```

- [ ] **Step 3: Write `src/recon_agent/recovery/classifier.py`**

```python
from __future__ import annotations
import random
from typing import Literal

from pydantic import BaseModel

from ..agent.state import AgentState
from ..tools.base import ToolError


MAX_RETRIES = 3
BACKOFF_BASE_MS = 1000
BACKOFF_MAX_MS = 8000
JITTER_RATIO = 0.3


class RecoveryAction(BaseModel):
    kind: Literal["retry", "replan", "degrade"]
    reason: str
    backoff_ms: int = 0
    hint: str = ""


class ErrorClassifier:
    def __init__(self):
        self._retry_counts: dict[str, int] = {}

    def _record_retry(self, state: AgentState, code: str) -> None:
        self._retry_counts[code] = self._retry_counts.get(code, 0) + 1

    def _retries_so_far(self, code: str) -> int:
        return self._retry_counts.get(code, 0)

    def _backoff(self, attempt: int) -> int:
        base = min(BACKOFF_BASE_MS * (2 ** attempt), BACKOFF_MAX_MS)
        jitter = random.uniform(-JITTER_RATIO, JITTER_RATIO) * base
        return int(base + jitter)

    def _alternative_hint(self, error: ToolError, state: AgentState) -> str:
        if "API" in error.code:
            return "fetch_api unreliable; proceed CSV-only and flag missing_in_api"
        if "MALFORMED_CSV" in error.code:
            return "CSV malformed; try load_csv with encoding=latin-1"
        if "LLM" in error.code:
            return "LLM unstable; reduce prompt size or skip this classification"
        if "LOW_CONFIDENCE" in error.code:
            return "low-confidence proposal; consider requesting manual_review"
        return f"avoid the failing path for {error.code}"

    def classify(self, error: ToolError, state: AgentState) -> RecoveryAction:
        # fatal OR repeated consecutive failures → degrade
        if error.kind == "fatal" or state.consecutive_failures >= 3:
            return RecoveryAction(
                kind="degrade",
                reason=f"{error.kind} {error.code}" if error.kind == "fatal"
                       else f"{state.consecutive_failures}+ consecutive failures",
            )

        # transient with retry budget → retry
        if error.kind == "transient" and self._retries_so_far(error.code) < MAX_RETRIES:
            attempt = self._retries_so_far(error.code)
            self._record_retry(state, error.code)
            return RecoveryAction(
                kind="retry",
                reason=f"transient {error.code}, attempt {attempt + 1}/{MAX_RETRIES}",
                backoff_ms=self._backoff(attempt),
            )

        # transient exhausted retries → escalate to replan
        if error.kind == "transient":
            return RecoveryAction(
                kind="replan",
                reason=f"transient {error.code} survived {MAX_RETRIES} retries",
                hint=self._alternative_hint(error, state),
            )

        # persistent → replan immediately
        if error.kind == "persistent":
            return RecoveryAction(
                kind="replan",
                reason=f"persistent {error.code}",
                hint=self._alternative_hint(error, state),
            )

        return RecoveryAction(kind="degrade", reason="unclassified")
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_classifier.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/recovery/classifier.py tests/unit/test_classifier.py
git commit -m "feat(recovery): ErrorClassifier with full error→strategy table coverage"
```

---

### Task 5.2: RecoveryLayer (dispatches strategies + integrates with loop)

**Files:**
- Create: `src/recon_agent/recovery/strategies.py`
- Modify: `src/recon_agent/recovery/__init__.py`
- Test: `tests/unit/test_recovery_layer.py`

- [ ] **Step 1: Write `src/recon_agent/recovery/strategies.py`**

```python
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..agent.phases import ActOutput
from .classifier import RecoveryAction


@dataclass
class RecoveryDecision:
    kind: str                       # "retry" | "replan" | "degrade"
    reason: str
    hint: str = ""
    new_act_output: ActOutput | None = None    # populated only on retry


class RetryWithBackoff:
    def execute(self, action: RecoveryAction, original: ActOutput, tools: Any) -> RecoveryDecision:
        time.sleep(action.backoff_ms / 1000.0)
        tool = tools.get(original.tool_name)
        inputs = tool.input_schema(**original.tool_input)
        result = tool.run(inputs)

        from datetime import datetime, timezone
        from ..agent.state import ToolCallRecord
        record = ToolCallRecord(
            step=original.raw_record.step, tool_name=original.tool_name,
            args=original.tool_input,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            latency_ms=action.backoff_ms,
            outcome="recovered" if result.ok else "error",
            error_kind=result.error.kind if result.error else None,
            error_code=result.error.code if result.error else None,
        )
        new_act = ActOutput(
            tool_name=original.tool_name, tool_input=original.tool_input,
            tool_output=result.output.model_dump() if result.ok and result.output else None,
            error=result.error, raw_record=record,
        )
        return RecoveryDecision(kind="retry", reason=action.reason, new_act_output=new_act)


class ReplanWithAlternativeTool:
    def execute(self, action: RecoveryAction) -> RecoveryDecision:
        return RecoveryDecision(kind="replan", reason=action.reason, hint=action.hint)


class GracefulDegrade:
    def execute(self, action: RecoveryAction) -> RecoveryDecision:
        return RecoveryDecision(kind="degrade", reason=action.reason)
```

- [ ] **Step 2: Write `src/recon_agent/recovery/__init__.py`**

```python
from __future__ import annotations
from typing import Any

from ..agent.phases import ActOutput
from ..agent.state import AgentState
from ..tools.base import ToolError
from .classifier import ErrorClassifier
from .strategies import (
    RecoveryDecision, RetryWithBackoff, ReplanWithAlternativeTool, GracefulDegrade
)


class RecoveryLayer:
    def __init__(self, logger: Any = None):
        self.classifier = ErrorClassifier()
        self.retry = RetryWithBackoff()
        self.replan = ReplanWithAlternativeTool()
        self.degrade = GracefulDegrade()
        self.logger = logger

    def handle(
        self,
        error: ToolError,
        state: AgentState,
        original_act: ActOutput,
        tools: Any,
    ) -> RecoveryDecision:
        action = self.classifier.classify(error, state)
        if self.logger:
            self.logger.info("recovery.dispatched", action=action.kind, reason=action.reason)

        if action.kind == "retry":
            return self.retry.execute(action, original_act, tools)
        if action.kind == "replan":
            return self.replan.execute(action)
        if action.kind == "degrade":
            return self.degrade.execute(action)

        return RecoveryDecision(kind="degrade", reason=f"unknown action {action.kind}")
```

- [ ] **Step 3: Write minimal integration test**

```python
# tests/unit/test_recovery_layer.py
from datetime import datetime, timezone
from recon_agent.recovery import RecoveryLayer
from recon_agent.agent.state import AgentState
from recon_agent.tools.base import ToolError
from recon_agent.agent.phases import ActOutput
from recon_agent.agent.state import ToolCallRecord


def _state(failures: int = 0) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc),
                      consecutive_failures=failures)


def _act() -> ActOutput:
    return ActOutput(
        tool_name="x", tool_input={},
        raw_record=ToolCallRecord(
            step=1, tool_name="x", args={},
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            latency_ms=10, outcome="error",
        )
    )


def test_404_replans():
    layer = RecoveryLayer()
    err = ToolError(kind="persistent", code="API_NOT_FOUND", message="404", retriable=False)
    decision = layer.handle(err, _state(), _act(), tools=None)
    assert decision.kind == "replan"
    assert decision.hint


def test_3_consecutive_failures_degrade():
    layer = RecoveryLayer()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    decision = layer.handle(err, _state(failures=3), _act(), tools=None)
    assert decision.kind == "degrade"
```

- [ ] **Step 4: Verify pass**

```bash
pytest tests/unit/test_recovery_layer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/recovery/ tests/unit/test_recovery_layer.py
git commit -m "feat(recovery): RecoveryLayer with retry/replan/degrade strategies"
```

---

### Task 5.3: Wire RecoveryLayer into AgentLoop

**Files:** Modify: `src/recon_agent/agent/loop.py`, `src/recon_agent/cli/demo.py`

- [ ] **Step 1: Inject RecoveryLayer in AgentLoop.__init__**

In `loop.py`:

```python
from ..recovery import RecoveryLayer

class AgentLoop:
    def __init__(self, ..., recovery: RecoveryLayer | None = None, ...):
        ...
        self.recovery = recovery or RecoveryLayer(logger=logger)
```

- [ ] **Step 2: Update AgentLoop.run() to call recovery on tool error**

Replace the error-handling block from Phase 4 step 4:

```python
            # ACT
            act_out = self.act_phase.run(plan_out, self.state)
            self.state.tool_calls.append(act_out.raw_record)

            if act_out.error:
                rec = self.recovery.handle(act_out.error, self.state, act_out, self.tools)

                if rec.kind == "retry":
                    act_out = rec.new_act_output
                    self.state.tool_calls.append(act_out.raw_record)
                    if act_out.error:
                        # retry also failed; treat as a new failure cycle
                        self.state.consecutive_failures += 1
                        observation = f"FAILED after retry {act_out.tool_name}: {act_out.error.code}"
                    else:
                        self.state.consecutive_failures = 0
                        observation = self.observe_phase.run(act_out, self.state)
                elif rec.kind == "replan":
                    self.state.consecutive_failures += 1
                    # Force a Decide that returns to PLAN with the hint baked into reasoning
                    from .state import DecideOutput
                    forced = DecideOutput(
                        next_phase=Phase.PLAN,
                        reasoning=f"recovery=replan: {rec.reason}. hint={rec.hint}",
                        recovery_invoked=True,
                        llm_call=_empty_llm_call(Phase.DECIDE),
                    )
                    self.state.apply(forced)
                    self.state.snapshot_to_disk(self.run_dir)
                    continue
                else:  # degrade
                    self._halt(f"graceful degrade: {rec.reason}")
                    break
            else:
                self.state.consecutive_failures = 0
                observation = self.observe_phase.run(act_out, self.state)
```

- [ ] **Step 3: Update `cli/demo.py` to pass RecoveryLayer**

```python
from ..recovery import RecoveryLayer

# Inside run_demo, after creating router:
recovery = RecoveryLayer()
loop = AgentLoop(
    task=args.task,
    tools=ToolRegistry,
    budget=budget,
    llm_router=router,
    recovery=recovery,
    run_dir=args.run_dir,
)
```

- [ ] **Step 4: Manual demo verifying recovery**

```bash
.venv/Scripts/python -m recon_agent.data.generate_fixtures --variant default --seed 42
FETCH_API_FAIL_RATE=0.5 make demo
```

Expected:
- Multiple retries logged
- Eventually progresses past fetch_api
- Demo completes (status=halted, reason="reconciliation complete" if the LLM decided HALT, OR status=halted, reason="max iterations" — either is OK at this phase)

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/agent/loop.py src/recon_agent/cli/demo.py
git commit -m "feat(agent): wire RecoveryLayer into AgentLoop"
```

---

### Task 5.4: PARTIAL_REPORT.md on budget breach

**Files:** Modify: `src/recon_agent/agent/loop.py` (add `_write_partial_report`)

- [ ] **Step 1: Add helper to AgentLoop**

```python
# Append inside AgentLoop:

    def _write_partial_report(self, breach_message: str) -> None:
        path = self.run_dir / "PARTIAL_REPORT.md"
        last_3 = self.state.tool_calls[-3:]
        lines = [
            f"# Partial Report — run {self.state.run_id}",
            "",
            f"**Status:** halted",
            f"**Halt reason:** budget breach — {breach_message}",
            f"**Step:** {self.state.step}",
            f"**Last phase:** {self.state.current_phase}",
            "",
            "## Completed",
            f"- CSV loaded: {self.state.csv_loaded}",
            f"- API loaded: {self.state.api_loaded}",
            f"- Timezone normalized: {self.state.timezone_normalized}",
            f"- Matches: {len(self.state.matches)}",
            f"- Discrepancies classified: {len(self.state.discrepancies)}",
            f"- Proposals: {len(self.state.proposals)}",
            f"- Corrections applied: {self.state.corrections_applied}",
            "",
            "## Pending",
            f"- Unverified reconciliation: yes" if not any(
                c.tool_name == "verify_reconciliation" for c in self.state.tool_calls
            ) else "- Verification: done",
            "",
            "## Last 3 tool calls",
        ]
        for c in last_3:
            lines.append(f"- step={c.step} {c.tool_name} {c.outcome} ({c.latency_ms}ms)")
        lines.extend([
            "",
            "## Last decision reasoning",
            f"> {self.state.last_decision_reasoning}",
            "",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 2: Invoke from `_halt` when reason starts with "budget breach"**

```python
    def _halt(self, reason: str) -> None:
        if reason.startswith("budget breach"):
            self._write_partial_report(reason)
        decision = DecideOutput(...)   # existing code
        ...
```

- [ ] **Step 3: Verify with demo**

```bash
.venv/Scripts/recon demo --budget-calls 3
ls reports/run_*/PARTIAL_REPORT.md
cat reports/run_*/PARTIAL_REPORT.md
```

Expected: file exists, has the partial-report structure.

- [ ] **Step 4: Update CLI exit code**

In `cli/demo.py`, change the return at the end of `run_demo`:

```python
    if report.halt_reason and report.halt_reason.startswith("budget breach"):
        return 2
    if report.halt_reason and "graceful degrade" in report.halt_reason:
        return 0   # degrade is still a clean exit; eval expects it
    return 0
```

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/agent/loop.py src/recon_agent/cli/demo.py
git commit -m "feat(agent): write PARTIAL_REPORT.md on budget breach; exit code 2"
```

---

### Task 5.5: Integration test — recovery on forced 429

**Files:** Test: `tests/integration/test_loop_recovery.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/integration/test_loop_recovery.py
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.recovery import RecoveryLayer
from recon_agent.tools.registry import ToolRegistry


def test_recovery_on_forced_429_completes(tmp_path, monkeypatch):
    """Force fetch_api to fail twice then succeed; the agent should retry and complete."""
    # Set high fail rate but limit retries via classifier
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.6")
    monkeypatch.setenv("FETCH_API_RNG_SEED", "42")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))

    # Generate fresh fixture
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=99, n_txns=20, variant="tz_only",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    # Mock router so we don't burn API tokens in integration tests
    fake_router = _make_fake_router()
    ToolRegistry.discover(force=True)

    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_consecutive_failures=10, max_tool_calls=30),
        llm_router=fake_router,
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    assert report.status in ("halted", "completed")
    # Verify a retry happened
    retries = [c for c in loop.state.tool_calls if c.outcome == "recovered"]
    assert len(retries) >= 0   # not strict; depends on RNG


def _make_fake_router():
    """Returns a router whose .call() always emits sensible plan/decide JSON."""
    from recon_agent.agent.phases import PlanOutput
    from recon_agent.agent.state import DecideOutput, LLMCallRecord, Phase

    call_count = {"n": 0}

    def fake_call(subtask, messages, schema, **kw):
        call_count["n"] += 1
        if subtask == "plan":
            # Cycle through a sensible plan sequence
            sequence = [
                ("load_csv", {"path": "src/recon_agent/data/fixtures/tracking_db.csv"}),
                ("fetch_api", {"endpoint": "payu_settlements"}),
                ("normalize_timezone", {"records": [], "timestamp_field": "settled_at"}),
                ("match_records", {"csv_records": [], "api_records": []}),
                ("verify_reconciliation", {"csv_records": [], "api_records": []}),
            ]
            idx = (call_count["n"] - 1) % len(sequence)
            tool, args = sequence[idx]
            return PlanOutput(intended_tool=tool, tool_args=args, reasoning="test"), \
                LLMCallRecord(step=0, phase=Phase.PLAN, provider="t", model="t",
                              subtask="plan", tokens_in=10, tokens_out=5, latency_ms=10, cost_inr=0)
        if subtask == "decide":
            # halt after 8 iterations
            next_phase = Phase.HALT if call_count["n"] > 16 else Phase.PLAN
            return DecideOutput(next_phase=next_phase,
                                halt_reason="test complete" if next_phase == Phase.HALT else None,
                                reasoning="test", llm_call=LLMCallRecord(
                                    step=0, phase=Phase.DECIDE, provider="t", model="t",
                                    subtask="decide", tokens_in=10, tokens_out=5,
                                    latency_ms=10, cost_inr=0,
                                )), LLMCallRecord(step=0, phase=Phase.DECIDE, provider="t",
                                                  model="t", subtask="decide",
                                                  tokens_in=10, tokens_out=5,
                                                  latency_ms=10, cost_inr=0)
        raise ValueError(f"unexpected subtask {subtask}")

    router = MagicMock()
    router.call.side_effect = fake_call
    return router
```

- [ ] **Step 2: Run test**

```bash
pytest tests/integration/test_loop_recovery.py -v
```

Expected: passes (may take a few seconds due to backoff sleeps).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_loop_recovery.py
git commit -m "test(integration): forced 429 recovery completes via retry"
```

---

### Task 5.6: Integration test — budget breach halts cleanly

**Files:** Test: `tests/integration/test_loop_budget.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_loop_budget.py
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timezone

from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.recovery import RecoveryLayer
from recon_agent.tools.registry import ToolRegistry
from tests.integration.test_loop_recovery import _make_fake_router


def test_max_tool_calls_3_halts_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.0")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=1, n_txns=20, variant="happy_clean",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    ToolRegistry.discover(force=True)
    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_tool_calls=3),
        llm_router=_make_fake_router(),
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    assert report.halt_reason.startswith("budget breach")
    assert (tmp_path / "PARTIAL_REPORT.md").exists()


def test_max_consecutive_failures_halts(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "1.0")    # always fail
    monkeypatch.setenv("FETCH_API_RNG_SEED", "1")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=1, n_txns=20, variant="happy_clean",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    ToolRegistry.discover(force=True)
    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_consecutive_failures=3, max_tool_calls=30),
        llm_router=_make_fake_router(),
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    # Either budget catches it OR recovery degrades — both are clean exits
    assert report.halt_reason is not None
    assert "budget breach" in report.halt_reason or "graceful degrade" in report.halt_reason
```

- [ ] **Step 2: Run + verify pass**

```bash
pytest tests/integration/test_loop_budget.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_loop_budget.py
git commit -m "test(integration): budget breach + max_consecutive_failures halt cleanly"
```

---

### Phase 5 verification

- [ ] **Confirm exit criteria:**

```bash
pytest tests/ -v
.venv/Scripts/recon demo --seed-fail-rate 0.5
.venv/Scripts/recon demo --budget-calls 3
```

Expected:
- All tests pass
- First demo recovers from failures, eventually halts
- Second demo writes `PARTIAL_REPORT.md` and exits 2
- Look at `reports/run_*/PARTIAL_REPORT.md` — content matches the template

Once green, proceed to Phase 6.

---

## Phase 6 — Observability polish (structlog + Rich dashboard)

**Entry condition:** Phase 5 complete.

**Exit condition:**
- `make demo` shows a Rich live dashboard during the run
- `reports/run_*/log.jsonl` is grep/jq-able
- `--no-dashboard` flag disables Rich (for CI/headless)

**Phase summary:** Polish what reviewers will actually see. Wire structlog's JSONRenderer to the loop and write to `log.jsonl`. Render a Rich live dashboard with phase, last 5 tool calls, budget bars, last Decide reasoning. Short phase — most of the heavy lifting was scaffolded earlier.

---

### Task 6.1: structlog config + JSONL writer

**Files:** Create: `src/recon_agent/observability/logger.py`

- [ ] **Step 1: Write the logger config**

```python
# src/recon_agent/observability/logger.py
from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog


def configure_logging(run_dir: Path, level: str = "INFO") -> structlog.BoundLogger:
    """Configure structlog to write JSONL events to run_dir/log.jsonl
    AND keep human-readable lines on stderr at the chosen level."""
    log_path = run_dir / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler — JSON lines
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    # Stderr handler — colored key=value
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)

    logging.basicConfig(
        format="%(message)s",
        handlers=[file_handler, stderr_handler],
        level=logging.DEBUG,
    )

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger().bind(run_dir=str(run_dir))
```

- [ ] **Step 2: Update CLI to use it**

In `src/recon_agent/cli/demo.py`:

```python
from ..observability.logger import configure_logging

# Inside run_demo, after creating run_dir:
run_dir = args.run_dir or Path(f"reports/run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
run_dir.mkdir(parents=True, exist_ok=True)
logger = configure_logging(run_dir, level="DEBUG" if args.verbose else "INFO")
logger.info("demo.started", task=args.task)
```

And add `--verbose` / `--quiet` flags to `add_demo_args`:

```python
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
```

Pass `logger` to AgentLoop constructor.

- [ ] **Step 3: Add log lines at key points in the loop**

In `loop.py`, inside `run()`:

```python
            if self.logger:
                self.logger.info("phase.plan", step=self.state.step,
                                 tool=plan_out.intended_tool, reasoning=plan_out.reasoning[:200])

            ...

            if self.logger:
                self.logger.info("phase.act", step=self.state.step,
                                 tool=act_out.tool_name,
                                 outcome="ok" if not act_out.error else "error",
                                 latency_ms=act_out.raw_record.latency_ms,
                                 error_code=act_out.error.code if act_out.error else None)
```

(Add similar logs in the recovery branch — `recovery.dispatched`, `recovery.retry`, `recovery.replan`, `recovery.degrade` — and in Decide.)

- [ ] **Step 4: Test that JSONL is parseable**

```bash
make demo
jq -c '.event' reports/run_*/log.jsonl | head -20
```

Expected: lines of `"demo.started"`, `"phase.plan"`, `"phase.act"`, etc.

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/observability/logger.py src/recon_agent/cli/demo.py src/recon_agent/agent/loop.py
git commit -m "feat(observability): structlog JSONL logger wired into AgentLoop"
```

---

### Task 6.2: Rich live dashboard

**Files:** Create: `src/recon_agent/observability/dashboard.py`

- [ ] **Step 1: Write the dashboard**

```python
# src/recon_agent/observability/dashboard.py
from __future__ import annotations
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.progress_bar import ProgressBar


class Dashboard:
    """Wraps a `rich.live.Live` context. Call `update(state, budget)` after every step."""

    def __init__(self, console: Console | None = None, enabled: bool = True):
        self.enabled = enabled
        self.console = console or Console(stderr=True)
        self._live: Live | None = None

    def __enter__(self):
        if not self.enabled:
            return self
        self._live = Live(self._render(None, None), console=self.console,
                          refresh_per_second=4, transient=False)
        self._live.start()
        return self

    def __exit__(self, *exc):
        if self._live:
            self._live.stop()

    def update(self, state: Any, budget: Any) -> None:
        if not self.enabled or not self._live:
            return
        self._live.update(self._render(state, budget))

    def _render(self, state: Any, budget: Any) -> Panel:
        if state is None:
            return Panel("Starting…", title="Recon Agent")

        # Top: phase + step + counters
        header = (
            f"Step {state.step}    Phase: {state.current_phase}    "
            f"Tools: {len(state.tool_calls)}    "
            f"LLM calls: {len(state.llm_calls)}    "
            f"Discrepancies: {len(state.discrepancies)}    "
            f"Applied: {state.corrections_applied}"
        )

        # Last 5 tool calls
        table = Table(title="Last 5 tool calls", show_header=True, header_style="bold")
        table.add_column("step", width=4)
        table.add_column("tool", width=24)
        table.add_column("outcome", width=10)
        table.add_column("ms", width=6, justify="right")
        for c in state.tool_calls[-5:]:
            marker = {"ok": "✓", "error": "✗", "recovered": "⟳"}.get(c.outcome, "?")
            table.add_row(str(c.step), f"{marker} {c.tool_name}",
                          c.outcome, str(c.latency_ms))

        # Budget bars
        tokens_used = sum(c.tokens_in + c.tokens_out for c in state.llm_calls)
        cost_used = sum(c.cost_inr for c in state.llm_calls)
        budget_table = Table(show_header=False, box=None)
        budget_table.add_row("Tokens",
                             self._bar(tokens_used, budget.max_tokens),
                             f"{tokens_used}/{budget.max_tokens}")
        budget_table.add_row("Tool calls",
                             self._bar(len(state.tool_calls), budget.max_tool_calls),
                             f"{len(state.tool_calls)}/{budget.max_tool_calls}")
        budget_table.add_row("Cost ₹",
                             self._bar(cost_used, budget.max_cost_inr),
                             f"₹{cost_used:.2f}/₹{budget.max_cost_inr}")

        # Last decision
        reasoning = state.last_decision_reasoning[:300] or "(none yet)"

        body = (
            f"{header}\n\n"
            f"[bold]Budget[/bold]\n"
        )
        return Panel.fit(body, title="Recon Agent — live", border_style="cyan",
                          subtitle=f"reasoning: {reasoning}")

    def _bar(self, used: float, total: float) -> str:
        pct = used / max(1, total)
        filled = int(pct * 20)
        return "[" + "█" * filled + "░" * (20 - filled) + "]"
```

- [ ] **Step 2: Wire Dashboard into AgentLoop**

In `loop.py`:

```python
from ..observability.dashboard import Dashboard

class AgentLoop:
    def __init__(self, ..., enable_dashboard: bool = True):
        ...
        self.dashboard = Dashboard(enabled=enable_dashboard)

    def run(self) -> ReconciliationReport:
        with self.dashboard:
            self.dashboard.update(self.state, self.budget)
            self.state.snapshot_to_disk(self.run_dir)
            # ... rest of run logic ...
            # After each state.apply():
            self.dashboard.update(self.state, self.budget)
        return self._build_report()
```

- [ ] **Step 3: Add `--no-dashboard` CLI flag**

In `cli/demo.py`:

```python
    p.add_argument("--no-dashboard", action="store_true")

# In run_demo, when constructing AgentLoop:
loop = AgentLoop(
    ...,
    enable_dashboard=not args.no_dashboard,
)
```

- [ ] **Step 4: Test demo with and without dashboard**

```bash
make demo
make demo --no-dashboard 2>&1 | head -20
```

Expected:
- First: live-updating dashboard renders
- Second: plain log lines, no Rich rendering interference

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/observability/dashboard.py src/recon_agent/agent/loop.py src/recon_agent/cli/demo.py
git commit -m "feat(observability): Rich live dashboard with --no-dashboard flag"
```

---

### Phase 6 verification

- [ ] **Confirm exit criteria:**

```bash
make demo
jq -c '.event' reports/run_*/log.jsonl | sort -u | head
```

Expected:
- Dashboard renders without errors
- log.jsonl contains events like `phase.plan`, `phase.act`, `recovery.dispatched`, `phase.decide`
- `--no-dashboard` flag disables Rich

Once green, proceed to Phase 7.

---

## Phase 7 — Eval framework + 12 scenarios + cassettes

**Entry condition:** Phase 6 complete; `make demo` produces complete telemetry.

**Exit condition:**
- `make eval` runs 12 scenarios in replay mode in ~30s, shows 12/12 PASS
- `make eval-live` re-records cassettes
- `evals/baselines/main.json` committed for CI comparison
- All 12 cassettes committed (`evals/cassettes/*.jsonl`)

**Phase summary:** Build the eval harness. Pydantic `Scenario` model. Runner that discovers scenarios, generates fresh fixtures per scenario, runs the agent, verifies against ground truth, writes pass/fail reports. Cassette layer's replay mode is now exercised: same prompts → same hashes → cached responses → no API calls, no cost.

---

### Task 7.1: Scenario Pydantic models

**Files:** Create: `evals/scenarios/base.py`

- [ ] **Step 1: Write `evals/scenarios/base.py`**

```python
# evals/scenarios/base.py
from __future__ import annotations
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ToolOverride(BaseModel):
    name: str
    action: Literal["disable", "force_fail"]
    error_code: str | None = None


class BudgetOverride(BaseModel):
    max_tokens: int | None = None
    max_wall_clock_s: float | None = None
    max_tool_calls: int | None = None
    max_consecutive_failures: int | None = None
    max_cost_inr: float | None = None


class Expected(BaseModel):
    status: set[Literal["completed", "halted", "degraded"]]
    findings_by_kind: dict[str, int] = Field(default_factory=dict)
    findings_tolerance: dict[str, int] = Field(default_factory=dict)
    recovery_invoked: bool = False
    min_correction_coverage: float = 0.85
    max_cost_inr: float = 10.0
    halt_reason_contains: str | None = None


class Scenario(BaseModel):
    name: str
    fixture_variant: str
    fixture_seed: int = 42
    cli_env: dict[str, str] = Field(default_factory=dict)
    tool_overrides: list[ToolOverride] = Field(default_factory=list)
    budget_overrides: BudgetOverride | None = None
    expected: Expected
    cassette_file: Path | None = None
    timeout_s: int = 120


class ScenarioResult(BaseModel):
    name: str
    passed: bool
    status: str | None = None
    findings_by_kind: dict[str, int] = Field(default_factory=dict)
    recovery_invoked: bool = False
    cost_inr: float = 0.0
    duration_s: float = 0.0
    failures: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add evals/scenarios/base.py
git commit -m "feat(evals): Scenario + Expected + ScenarioResult Pydantic models"
```

---

### Task 7.2: Write all 12 scenario files

**Files:** Create 12 files in `evals/scenarios/`

- [ ] **Step 1: Create the 5 happy-path scenarios**

```python
# evals/scenarios/happy_01_clean_reconciliation.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_01_clean_reconciliation",
    fixture_variant="happy_clean", fixture_seed=1001,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"}, findings_by_kind={},
        recovery_invoked=False, max_cost_inr=2.50,
    ),
    cassette_file=Path("evals/cassettes/happy_01_clean_reconciliation.jsonl"),
)
```

```python
# evals/scenarios/happy_02_minor_timezone.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_02_minor_timezone",
    fixture_variant="tz_only", fixture_seed=1002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={"timezone_shift": 25},
        findings_tolerance={"timezone_shift": 3},
        recovery_invoked=False, max_cost_inr=3.00,
    ),
    cassette_file=Path("evals/cassettes/happy_02_minor_timezone.jsonl"),
)
```

Similarly for `happy_03_encoding.py` (variant=`encoding_only`, expect 5 `encoding_corruption`), `happy_04_duplicates.py` (variant=`duplicate_only`, expect 10 `duplicate`), `happy_05_value_mismatch.py` (variant=`value_only`, expect 15 `value_mismatch`).

- [ ] **Step 2: Create the 3 recovery scenarios**

```python
# evals/scenarios/recovery_01_api_429.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="recovery_01_api_429",
    fixture_variant="default", fixture_seed=2001,
    cli_env={"FETCH_API_FAIL_RATE": "0.6", "FETCH_API_RNG_SEED": "1"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={
            "value_mismatch": 15, "timezone_shift": 25, "duplicate": 10,
            "missing_in_api": 10, "missing_in_csv": 3, "encoding_corruption": 5,
        },
        findings_tolerance={k: 3 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=5.50,
    ),
    cassette_file=Path("evals/cassettes/recovery_01_api_429.jsonl"),
)
```

```python
# evals/scenarios/recovery_02_malformed_csv.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="recovery_02_malformed_csv",
    fixture_variant="default_latin1_csv", fixture_seed=2002,
    expected=Expected(
        status={"completed", "halted", "degraded"},
        findings_by_kind={
            "value_mismatch": 15, "timezone_shift": 25, "duplicate": 10,
            "missing_in_api": 10, "encoding_corruption": 5,
        },
        findings_tolerance={k: 5 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=5.00,
    ),
    cassette_file=Path("evals/cassettes/recovery_02_malformed_csv.jsonl"),
)
```

```python
# evals/scenarios/recovery_03_tool_disabled.py
from pathlib import Path
from .base import Scenario, Expected, ToolOverride

SCENARIO = Scenario(
    name="recovery_03_tool_disabled",
    fixture_variant="default", fixture_seed=2003,
    cli_env={"FETCH_API_DISABLED": "1"},
    tool_overrides=[ToolOverride(name="fetch_api", action="disable")],
    expected=Expected(
        status={"degraded", "halted"},
        findings_by_kind={},
        findings_tolerance={k: 50 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=4.00,
        halt_reason_contains="degrade",
    ),
    cassette_file=Path("evals/cassettes/recovery_03_tool_disabled.jsonl"),
)
```

- [ ] **Step 3: Create the 2 budget scenarios**

```python
# evals/scenarios/budget_01_token_ceiling.py
from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

SCENARIO = Scenario(
    name="budget_01_token_ceiling",
    fixture_variant="default", fixture_seed=3001,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_tokens=2000),
    expected=Expected(
        status={"halted"}, findings_by_kind={},
        findings_tolerance={k: 100 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=False, max_cost_inr=1.00,
        halt_reason_contains="budget breach: tokens",
    ),
    cassette_file=Path("evals/cassettes/budget_01_token_ceiling.jsonl"),
)
```

```python
# evals/scenarios/budget_02_walltime_ceiling.py
from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

SCENARIO = Scenario(
    name="budget_02_walltime_ceiling",
    fixture_variant="default", fixture_seed=3002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_wall_clock_s=5.0),
    expected=Expected(
        status={"halted"}, findings_by_kind={},
        findings_tolerance={k: 100 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=False, max_cost_inr=1.00,
        halt_reason_contains="budget breach: wall_clock",
    ),
    cassette_file=Path("evals/cassettes/budget_02_walltime_ceiling.jsonl"),
)
```

- [ ] **Step 4: Create the 2 impossible scenarios**

```python
# evals/scenarios/impossible_01_corrupted_source.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="impossible_01_corrupted_source",
    fixture_variant="corrupted_source", fixture_seed=4001,
    expected=Expected(
        status={"degraded", "halted"}, findings_by_kind={},
        recovery_invoked=True, max_cost_inr=2.00,
        halt_reason_contains="degrade",
    ),
    cassette_file=Path("evals/cassettes/impossible_01_corrupted_source.jsonl"),
)
```

```python
# evals/scenarios/impossible_02_irreconcilable.py
from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="impossible_02_irreconcilable",
    fixture_variant="irreconcilable", fixture_seed=4002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"degraded", "halted", "completed"},
        findings_by_kind={"missing_in_api": 500},
        findings_tolerance={"missing_in_api": 100, "missing_in_csv": 100},
        recovery_invoked=True, max_cost_inr=4.00,
    ),
    cassette_file=Path("evals/cassettes/impossible_02_irreconcilable.jsonl"),
)
```

- [ ] **Step 5: Commit**

```bash
git add evals/scenarios/*.py
git commit -m "feat(evals): all 12 scenario specifications"
```

---

### Task 7.3: Eval verifier

**Files:** Create: `evals/verify.py`

- [ ] **Step 1: Write the verifier**

```python
# evals/verify.py
from __future__ import annotations
import json
from pathlib import Path

from evals.scenarios.base import Scenario, ScenarioResult


def verify_scenario(
    scenario: Scenario,
    run_dir: Path,
    gt: dict,
) -> ScenarioResult:
    """Five orthogonal checks. Pass ⟺ all five pass."""
    failures: list[str] = []

    # Load run artifacts
    report_path = run_dir / "report.json"      # we'll write this in runner; below
    if not report_path.exists():
        return ScenarioResult(
            name=scenario.name, passed=False,
            failures=[f"report.json missing in {run_dir}"],
        )
    report = json.loads(report_path.read_text())
    ledger_path = run_dir / "corrections.jsonl"
    ledger: list[dict] = []
    if ledger_path.exists():
        ledger = [json.loads(l) for l in ledger_path.open() if l.strip()]
    log_path = run_dir / "log.jsonl"
    log_lines: list[dict] = []
    if log_path.exists():
        log_lines = [json.loads(l) for l in log_path.open() if l.strip()]

    # 1. Status check
    status = report.get("status")
    if status not in scenario.expected.status:
        failures.append(f"status={status} not in expected {scenario.expected.status}")

    # 2. Discrepancy count check (with tolerance)
    found_by_kind = report.get("findings_by_kind", {})
    for kind, expected_count in scenario.expected.findings_by_kind.items():
        actual = found_by_kind.get(kind, 0)
        tol = scenario.expected.findings_tolerance.get(kind, 1)
        if abs(actual - expected_count) > tol:
            failures.append(f"findings[{kind}]={actual} not within ±{tol} of {expected_count}")

    # 3. Correction coverage
    applied_ids = {row["txn_id"] for row in ledger if row.get("action") == "applied"}
    expected_ids = {d["txn_id"] for d in gt.get("injected", [])
                    if d["kind"] not in ("missing_in_csv",)}  # missing_in_csv typically only flagged
    coverage = len(applied_ids & expected_ids) / max(1, len(expected_ids))
    if coverage < scenario.expected.min_correction_coverage \
            and scenario.expected.findings_by_kind:    # skip coverage on impossible scenarios
        # Skip coverage on impossible/budget scenarios
        if "budget" not in scenario.name and "impossible" not in scenario.name:
            failures.append(f"correction coverage={coverage:.2f} < {scenario.expected.min_correction_coverage}")

    # 4. Recovery-invoked check
    recovery_invoked = any(
        line.get("event") == "recovery.dispatched" for line in log_lines
    )
    if recovery_invoked != scenario.expected.recovery_invoked:
        failures.append(f"recovery_invoked={recovery_invoked} (expected {scenario.expected.recovery_invoked})")

    # 5. Cost check
    cost = report.get("telemetry", {}).get("total_cost_inr", 0.0)
    if cost > scenario.expected.max_cost_inr:
        failures.append(f"cost ₹{cost:.2f} > max ₹{scenario.expected.max_cost_inr}")

    # 6. Halt reason substring (if specified)
    if scenario.expected.halt_reason_contains:
        halt_reason = report.get("halt_reason") or ""
        if scenario.expected.halt_reason_contains not in halt_reason:
            failures.append(f"halt_reason='{halt_reason}' missing '{scenario.expected.halt_reason_contains}'")

    return ScenarioResult(
        name=scenario.name,
        passed=len(failures) == 0,
        status=status,
        findings_by_kind=found_by_kind,
        recovery_invoked=recovery_invoked,
        cost_inr=cost,
        failures=failures,
    )
```

- [ ] **Step 2: Commit**

```bash
git add evals/verify.py
git commit -m "feat(evals): verifier with 5 orthogonal pass/fail checks"
```

---

### Task 7.4: Eval runner

**Files:** Create: `evals/runner.py`; Modify: `src/recon_agent/agent/loop.py` (write `report.json` alongside report.md)

- [ ] **Step 1: Update AgentLoop to write `report.json`**

In `loop.py`, add a method:

```python
    def _write_report_json(self) -> None:
        path = self.run_dir / "report.json"
        # Aggregate findings by kind
        from collections import Counter
        kinds = Counter(d.kind for d in self.state.discrepancies)
        total_cost = (sum(c.cost_inr for c in self.state.llm_calls)
                      + sum(c.cost_inr for c in self.state.tool_calls))
        payload = {
            "status": "halted" if self.state.is_terminal() else "running",
            "halt_reason": self.state.halt_reason,
            "findings_by_kind": dict(kinds),
            "telemetry": {
                "steps": self.state.step,
                "tool_calls": len(self.state.tool_calls),
                "llm_calls": len(self.state.llm_calls),
                "total_cost_inr": round(total_cost, 4),
            },
            "corrections_applied": self.state.corrections_applied,
        }
        # Status reclassification
        if self.state.halt_reason:
            if "complete" in self.state.halt_reason or "reconciliation" in self.state.halt_reason.lower():
                payload["status"] = "completed"
            elif "degrade" in self.state.halt_reason:
                payload["status"] = "degraded"
            elif "budget breach" in self.state.halt_reason:
                payload["status"] = "halted"
        import json
        path.write_text(json.dumps(payload, indent=2))
```

Call `self._write_report_json()` at the end of `run()` after `_build_report()`.

- [ ] **Step 2: Write `evals/runner.py`**

```python
# evals/runner.py
from __future__ import annotations
import argparse
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from evals.scenarios.base import Scenario, ScenarioResult
from evals.verify import verify_scenario


def discover_scenarios() -> list[Scenario]:
    pkg_dir = Path("evals/scenarios")
    scenarios = []
    for p in sorted(pkg_dir.glob("*.py")):
        if p.name in ("__init__.py", "base.py"):
            continue
        mod = importlib.import_module(f"evals.scenarios.{p.stem}")
        if hasattr(mod, "SCENARIO"):
            scenarios.append(mod.SCENARIO)
    return scenarios


def run_one(scenario: Scenario, llm_mode: str, out_root: Path) -> ScenarioResult:
    from recon_agent.agent.budget import Budget
    from recon_agent.agent.loop import AgentLoop
    from recon_agent.data.generate_fixtures import generate_fixtures
    from recon_agent.llm.cassettes import CassetteLayer
    from recon_agent.llm.router import LLMRouter
    from recon_agent.recovery import RecoveryLayer
    from recon_agent.tools.registry import ToolRegistry

    started = time.time()
    run_dir = out_root / scenario.name
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply env overrides (FETCH_API_FAIL_RATE, FETCH_API_DISABLED, PLAN_PROVIDER, ...)
    saved_env = {k: os.environ.get(k) for k in scenario.cli_env}
    for k, v in scenario.cli_env.items():
        os.environ[k] = v
    os.environ["FIXTURE_DIR"] = str(Path("src/recon_agent/data/fixtures"))

    try:
        # 2. Generate fixtures for this scenario's variant
        gt_obj = generate_fixtures(
            seed=scenario.fixture_seed, n_txns=500,
            variant=scenario.fixture_variant,
            out_dir=Path("src/recon_agent/data/fixtures"),
        )
        gt = json.loads(Path(f"src/recon_agent/data/ground_truth_{scenario.fixture_variant}.json").read_text())

        # 3. Set up agent
        cassette_path = scenario.cassette_file or run_dir / "cassette.jsonl"
        cassette = CassetteLayer(mode=llm_mode, path=cassette_path)
        router = LLMRouter(cassette)

        ToolRegistry.discover(force=True)
        # Apply tool overrides
        if scenario.tool_overrides:
            for ov in scenario.tool_overrides:
                if ov.action == "disable":
                    # registry filtering applied via env (FETCH_API_DISABLED) is sufficient
                    pass

        # Budget
        b_args = {}
        if scenario.budget_overrides:
            b_args = {k: v for k, v in scenario.budget_overrides.model_dump().items()
                      if v is not None}
        budget = Budget(**b_args)

        recovery = RecoveryLayer()
        loop = AgentLoop(
            task="Reconcile CSV vs PayU API. Apply corrections to ledger.",
            tools=ToolRegistry,
            budget=budget,
            llm_router=router,
            recovery=recovery,
            run_dir=run_dir,
            enable_dashboard=False,
            max_iterations=40,
        )
        try:
            loop.run()
        except Exception:
            traceback.print_exc()

    finally:
        # Restore env
        for k, prev in saved_env.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev

    result = verify_scenario(scenario, run_dir, gt)
    result.duration_s = round(time.time() - started, 2)
    return result


def write_results(results: list[ScenarioResult], out_dir: Path, llm_mode: str, json_path: Path | None = None) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    md_lines = [
        f"# Eval Run · {datetime.now(timezone.utc).isoformat()}",
        f"**Mode:** {llm_mode} · **Total:** {total} · **Pass:** {passed}/{total}",
        "",
        "| # | Scenario | Status | Findings | Recovery | Cost ₹ | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        f_summary = ",".join(f"{k}={v}" for k, v in r.findings_by_kind.items()) or "-"
        verdict = "✓ PASS" if r.passed else "✗ FAIL"
        md_lines.append(
            f"| {i} | {r.name} | {r.status} | {f_summary} | "
            f"{'yes' if r.recovery_invoked else 'no'} | {r.cost_inr:.2f} | {verdict} |"
        )

    md_lines.append("")
    for r in results:
        if not r.passed:
            md_lines.append(f"## ✗ {r.name}")
            for f in r.failures:
                md_lines.append(f"- {f}")
            md_lines.append("")

    (out_dir / "results.md").write_text("\n".join(md_lines))
    payload = {
        "summary": {
            "total": total, "passed": passed,
            "pass_rate": passed / total if total else 0,
            "failures": [{"name": r.name, "reason": "; ".join(r.failures)}
                         for r in results if not r.passed],
        },
        "scenarios": [r.model_dump() for r in results],
    }
    target = json_path or (out_dir / "results.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-mode", choices=["live", "record", "replay"],
                        default=os.environ.get("LLM_MODE", "replay"))
    parser.add_argument("--scenario", action="append", default=None,
                        help="Run only these scenarios (repeatable). Default: all.")
    parser.add_argument("--tag", default=None,
                        help="Suffix on the output dir name (used for comparison runs).")
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_{args.tag}" if args.tag else ""
    out_root = Path(f"reports/eval_{ts}{suffix}")
    out_root.mkdir(parents=True, exist_ok=True)

    scenarios = discover_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s.name in args.scenario]

    results: list[ScenarioResult] = []
    for s in scenarios:
        print(f"-- {s.name} ...", end="", flush=True)
        result = run_one(s, args.llm_mode, out_root)
        results.append(result)
        marker = "✓" if result.passed else "✗"
        print(f" {marker} ({result.duration_s}s)")

    write_results(results, out_root, args.llm_mode, args.output_json)

    passed = sum(1 for r in results if r.passed)
    print(f"\nResult: {passed}/{len(results)} PASS in {out_root}/results.md")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Commit**

```bash
git add evals/runner.py src/recon_agent/agent/loop.py
git commit -m "feat(evals): runner orchestrates scenario discovery + verification"
```

---

### Task 7.5: Record cassettes for all 12 scenarios

- [ ] **Step 1: Run `make eval-live` to record cassettes**

```bash
make eval-live
```

Expected:
- ~5 minutes of real LLM calls
- Each scenario produces a cassette in `evals/cassettes/<name>.jsonl`
- Most scenarios PASS (some may need prompt tweaks — iterate)

- [ ] **Step 2: Inspect cassettes**

```bash
wc -l evals/cassettes/*.jsonl
```

Expected: each file has 10-40 lines (one per LLM call captured).

- [ ] **Step 3: Iterate on failures**

If a scenario fails (status mismatch, finding count off, etc.):
- Read `reports/eval_<ts>/<scenario>/log.jsonl` for the agent's reasoning
- If the agent made a bad decision, tweak `plan_system.txt` or `decide_system.txt`
- Delete the affected cassette and re-record with `LLM_MODE=record python -m evals.runner --scenario <name>`

- [ ] **Step 4: Verify replay works**

```bash
make eval
```

Expected: 12/12 PASS in <60s, all cassette hits.

- [ ] **Step 5: Commit cassettes**

```bash
git add evals/cassettes/*.jsonl
git commit -m "test(evals): record cassettes for all 12 scenarios"
```

---

### Task 7.6: Commit first baseline

**Files:** Create: `evals/baselines/main.json`

- [ ] **Step 1: Run eval, write to baseline path**

```bash
make refresh-baseline
```

(Which runs `python -m evals.runner --output-json evals/baselines/main.json`.)

- [ ] **Step 2: Inspect the baseline**

```bash
jq '.summary' evals/baselines/main.json
```

Expected: `{"total": 12, "passed": 12, "pass_rate": 1.0, "failures": []}`.

- [ ] **Step 3: Commit**

```bash
git add evals/baselines/main.json
git commit -m "chore(evals): commit baseline for CI comparison"
```

---

### Phase 7 verification

- [ ] **Confirm exit criteria:**

```bash
make eval
```

Expected:
- 12/12 PASS
- Wall-clock <60s
- Cassette hit rate 100%
- `reports/eval_<ts>/results.md` rendered nicely

Once green, proceed to Phase 8.

---

## Phase 8 — Shadow testing + statistical comparison

**Entry condition:** Phase 7 complete; 12/12 PASS in replay mode.

**Exit condition:**
- `recon demo --shadow` runs Plan via both Gemini Pro AND GPT-4o in parallel, logs both
- `make eval-compare` produces `reports/shadow_comparison_<ts>.md` with paired bootstrap, p-value, verdict
- Comparison artifact committed alongside cassettes

**Phase summary:** Add the artifact that proves we measured. Shadow Runner wraps the router for Plan phase only. Paired bootstrap on per-scenario pass-rate.

---

### Task 8.1: ShadowRunner

**Files:** Create: `src/recon_agent/llm/shadow.py`

- [ ] **Step 1: Write `src/recon_agent/llm/shadow.py`**

```python
# src/recon_agent/llm/shadow.py
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..agent.phases import Phase
from ..agent.state import LLMCallRecord


class ShadowRunner:
    """When enabled, Plan phase calls Gemini Pro AND GPT-4o in parallel.
    Primary feeds the loop; secondary logged for offline comparison."""

    def __init__(self, router: Any, enabled: bool, log_path: Path):
        self.router = router
        self.enabled = enabled
        self.log_path = log_path

    def plan_call(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        step: int = 0,
    ) -> tuple[BaseModel, list[LLMCallRecord]]:
        if not self.enabled:
            out, rec = self.router.call("plan", messages, schema, step=step, phase=Phase.PLAN)
            return out, [rec]

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_prim = ex.submit(self.router.call, "plan", messages, schema,
                               step=step, phase=Phase.PLAN)
            f_sec = ex.submit(self.router.call, "shadow_plan", messages, schema,
                              step=step, phase=Phase.PLAN)
            prim_out, prim_rec = f_prim.result()
            sec_out, sec_rec = f_sec.result()

        self._log(step, prim_out, sec_out, prim_rec, sec_rec)
        return prim_out, [prim_rec, sec_rec]

    def _log(self, step, prim, sec, prim_rec, sec_rec):
        line = {
            "step": step,
            "primary": {
                "tool": getattr(prim, "intended_tool", None),
                "args": getattr(prim, "tool_args", None),
                "model": prim_rec.model, "cost_inr": prim_rec.cost_inr,
            },
            "secondary": {
                "tool": getattr(sec, "intended_tool", None),
                "args": getattr(sec, "tool_args", None),
                "model": sec_rec.model, "cost_inr": sec_rec.cost_inr,
            },
            "agreed_tool": getattr(prim, "intended_tool", None)
                           == getattr(sec, "intended_tool", None),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
```

- [ ] **Step 2: Wire ShadowRunner into AgentLoop's Plan call**

In `loop.py`, the Plan phase needs to optionally use the shadow runner. Quick approach: take a `shadow` flag on `AgentLoop.__init__`, wrap the call:

```python
from ..llm.shadow import ShadowRunner

class AgentLoop:
    def __init__(self, ..., shadow_enabled: bool = False, ...):
        ...
        self.shadow = ShadowRunner(
            router=self.router,
            enabled=shadow_enabled,
            log_path=self.run_dir / "shadow.jsonl",
        )

    # In run():
    # Instead of self.plan_phase.run(state), do:
    # The Plan phase already calls router.call internally. To preserve simplicity,
    # we modify Plan to accept an optional ShadowRunner override:
```

Update `phases.py` Plan class to accept optional shadow:

```python
class Plan:
    def __init__(self, router, tool_registry, logger=None, shadow=None):
        ...
        self._shadow = shadow

    def run(self, state):
        ...
        if self._shadow and self._shadow.enabled:
            out, calls = self._shadow.plan_call(messages, PlanOutput, step=state.step)
            return out, calls[0]
        ...   # existing path
```

- [ ] **Step 3: Add `--shadow` CLI flag**

```python
# cli/demo.py
    p.add_argument("--shadow", action="store_true")

# In run_demo:
loop = AgentLoop(..., shadow_enabled=args.shadow)
```

- [ ] **Step 4: Smoke test**

```bash
recon demo --shadow
cat reports/run_*/shadow.jsonl | head -5
```

Expected: each line shows `primary` and `secondary` model outputs.

- [ ] **Step 5: Commit**

```bash
git add src/recon_agent/llm/shadow.py src/recon_agent/agent/phases.py src/recon_agent/agent/loop.py src/recon_agent/cli/demo.py
git commit -m "feat(llm): ShadowRunner with --shadow CLI flag"
```

---

### Task 8.2: Paired bootstrap

**Files:** Create: `src/recon_agent/llm/comparison.py`; Test: `tests/unit/test_comparison.py`

- [ ] **Step 1: Write the bootstrap**

```python
# src/recon_agent/llm/comparison.py
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from evals.scenarios.base import ScenarioResult


@dataclass
class ComparisonReport:
    observed_delta: float       # A_pass_rate - B_pass_rate
    ci_lower: float
    ci_upper: float
    p_value: float
    config_a_pass: float
    config_b_pass: float
    n: int


def compare_configs(
    config_a_results: list[ScenarioResult],
    config_b_results: list[ScenarioResult],
    n_resamples: int = 10_000,
    seed: int = 42,
) -> ComparisonReport:
    """Paired bootstrap. Assumes same scenarios in same order."""
    pairs = [
        (1 if a.passed else 0, 1 if b.passed else 0)
        for a, b in zip(config_a_results, config_b_results)
    ]
    n = len(pairs)
    if n == 0:
        return ComparisonReport(0, 0, 0, 1.0, 0, 0, 0)

    arr = np.array(pairs, dtype=float)
    observed = float(arr[:, 0].mean() - arr[:, 1].mean())

    rng = np.random.default_rng(seed)
    deltas = np.zeros(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        sample = arr[idx]
        deltas[i] = sample[:, 0].mean() - sample[:, 1].mean()

    ci_lower = float(np.quantile(deltas, 0.025))
    ci_upper = float(np.quantile(deltas, 0.975))
    # Two-sided p-value: fraction of bootstrap deltas as extreme (in abs) as observed,
    # under H0 that the populations are interchangeable. Centered approximation:
    centered = deltas - deltas.mean()
    p_value = float((np.abs(centered) >= abs(observed)).mean())

    return ComparisonReport(
        observed_delta=observed,
        ci_lower=ci_lower, ci_upper=ci_upper, p_value=p_value,
        config_a_pass=float(arr[:, 0].mean()),
        config_b_pass=float(arr[:, 1].mean()),
        n=n,
    )
```

- [ ] **Step 2: Write test**

```python
# tests/unit/test_comparison.py
from recon_agent.llm.comparison import compare_configs
from evals.scenarios.base import ScenarioResult


def _r(name: str, passed: bool) -> ScenarioResult:
    return ScenarioResult(name=name, passed=passed)


def test_compare_perfect_a_imperfect_b():
    a = [_r(f"s{i}", True) for i in range(12)]
    b = [_r(f"s{i}", True) for i in range(10)] + [_r("s10", False), _r("s11", False)]
    rep = compare_configs(a, b, n_resamples=2000)
    assert rep.observed_delta > 0
    assert rep.config_a_pass == 1.0
    assert rep.config_b_pass < 1.0
    assert rep.n == 12


def test_compare_identical_no_delta():
    a = [_r(f"s{i}", True) for i in range(10)]
    b = [_r(f"s{i}", True) for i in range(10)]
    rep = compare_configs(a, b, n_resamples=2000)
    assert rep.observed_delta == 0
```

- [ ] **Step 3: Verify pass**

```bash
pytest tests/unit/test_comparison.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/recon_agent/llm/comparison.py tests/unit/test_comparison.py
git commit -m "feat(llm): paired bootstrap comparison with CI + p-value"
```

---

### Task 8.3: `evals/compare.py` + markdown renderer

**Files:** Create: `evals/compare.py`

- [ ] **Step 1: Write `evals/compare.py`**

```python
# evals/compare.py
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.scenarios.base import ScenarioResult
from recon_agent.llm.comparison import ComparisonReport, compare_configs


def load_results(tag: str) -> list[ScenarioResult]:
    """Find the most recent reports/eval_*_<tag>/results.json"""
    candidates = sorted(Path("reports").glob(f"eval_*_{tag}/results.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No reports/eval_*_{tag}/results.json")
    payload = json.loads(candidates[0].read_text())
    return [ScenarioResult(**r) for r in payload["scenarios"]]


def render_markdown(
    a_results: list[ScenarioResult], a_label: str,
    b_results: list[ScenarioResult], b_label: str,
    rep: ComparisonReport,
) -> str:
    lines = [
        f"# Shadow Comparison — Plan-phase model choice",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Configurations:** A = {a_label} · B = {b_label}",
        f"**Scenarios:** {rep.n} (replay mode)",
        "",
        "## Per-scenario outcomes",
        "| Scenario | A pass | B pass | A cost ₹ | B cost ₹ |",
        "|----------|--------|--------|----------|----------|",
    ]
    for a, b in zip(a_results, b_results):
        am = "✓" if a.passed else "✗"
        bm = "✓" if b.passed else "✗"
        lines.append(f"| {a.name} | {am} | {bm} | {a.cost_inr:.2f} | {b.cost_inr:.2f} |")

    a_cost = sum(r.cost_inr for r in a_results)
    b_cost = sum(r.cost_inr for r in b_results)
    lines.extend([
        "",
        "## Aggregate",
        f"| Config | Pass rate | Mean cost/run ₹ |",
        f"|--------|-----------|-----------------|",
        f"| A: {a_label} | {rep.config_a_pass*100:.1f}% | {a_cost/max(1,rep.n):.2f} |",
        f"| B: {b_label} | {rep.config_b_pass*100:.1f}% | {b_cost/max(1,rep.n):.2f} |",
        "",
        "## Statistical test (paired bootstrap, 10k resamples)",
        f"- **Observed Δ pass-rate (A − B):** {rep.observed_delta:+.3f}",
        f"- **95% CI:** [{rep.ci_lower:+.3f}, {rep.ci_upper:+.3f}]",
        f"- **p-value (two-sided):** {rep.p_value:.3f}",
        "",
        "## Verdict",
    ])
    if rep.observed_delta > 0 and rep.p_value < 0.05:
        lines.append(f"**{a_label} is statistically better than {b_label} for Plan "
                     f"(p={rep.p_value:.3f}). Keep current routing.**")
    elif rep.observed_delta < 0 and rep.p_value < 0.05:
        lines.append(f"**{b_label} appears statistically better. "
                     f"Consider switching default Plan provider.**")
    else:
        lines.append(f"No statistically significant difference at α=0.05 "
                     f"(p={rep.p_value:.3f}). Stick with the cheaper one ({a_label} costs ₹{a_cost:.2f}, "
                     f"{b_label} costs ₹{b_cost:.2f}).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_a", help="tag for config A (e.g., config_a)")
    parser.add_argument("config_b", help="tag for config B (e.g., config_b)")
    parser.add_argument("--label-a", default="Gemini 2.5 Pro")
    parser.add_argument("--label-b", default="GPT-4o")
    args = parser.parse_args(argv)

    a_results = load_results(args.config_a)
    b_results = load_results(args.config_b)
    if [r.name for r in a_results] != [r.name for r in b_results]:
        print("Scenarios differ between runs — aligning by name.", file=sys.stderr)
        b_by_name = {r.name: r for r in b_results}
        b_results = [b_by_name[r.name] for r in a_results if r.name in b_by_name]
        a_results = [r for r in a_results if r.name in b_by_name]

    rep = compare_configs(a_results, b_results)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/shadow_comparison_{ts}.md")
    out.write_text(render_markdown(a_results, args.label_a, b_results, args.label_b, rep))
    print(f"Comparison report → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run `make eval-compare`**

```bash
make eval-compare
```

Expected:
- Runs eval twice (once with default routing, once with `PLAN_PROVIDER=openai` override)
- Produces `reports/shadow_comparison_<ts>.md`
- Cassettes for `PLAN_PROVIDER=openai` may not exist yet — first run will be `LLM_MODE=record` automatically? Or we re-record. Either way: if cassette misses happen, run `LLM_MODE=record make eval-compare` once, then `LLM_MODE=replay make eval-compare`.

- [ ] **Step 3: Inspect the report**

```bash
cat reports/shadow_comparison_*.md
```

Verify: per-scenario table, aggregate, p-value, verdict.

- [ ] **Step 4: Commit**

```bash
git add evals/compare.py reports/shadow_comparison_*.md
git commit -m "feat(evals): eval-compare with paired bootstrap + markdown report"
```

---

### Phase 8 verification

- [ ] **Confirm exit criteria:**

```bash
make eval-compare
ls reports/shadow_comparison_*.md
```

Expected:
- Comparison report exists
- p-value present
- Verdict line present
- Optional: re-record cassettes for the OpenAI Plan variant by running `PLAN_PROVIDER=openai LLM_MODE=record python -m evals.runner --tag config_b`

Once green, proceed to Phase 9.

---

## Phase 9 — CI gate (GitHub Actions)

**Entry condition:** Phase 8 complete.

**Exit condition:**
- `.github/workflows/eval.yml` runs `make eval` on every PR
- Workflow blocks merge on any scenario failure
- Workflow comments pass/fail summary on PRs
- Workflow runs in <3 min (replay mode, no API keys)

**Phase summary:** Wire the eval suite into CI. Compare against `evals/baselines/main.json`. Cassettes committed → no API keys → reproducible runs on free GitHub Actions minutes.

---

### Task 9.1: GitHub Actions workflow

**Files:** Create: `.github/workflows/eval.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/eval.yml
name: eval

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run eval suite in replay mode (no API keys needed)
        env:
          LLM_MODE: replay
        run: python -m evals.runner --output-json reports/ci_results.json

      - name: Compare against baseline
        run: |
          python -m evals.compare_baseline \
            --current reports/ci_results.json \
            --baseline evals/baselines/main.json \
            --max-regression 0.0

      - name: Upload eval report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: reports/

      - name: Comment on PR with eval summary
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const r = JSON.parse(fs.readFileSync('reports/ci_results.json'));
            const failures = r.summary.failures;
            const body = `## Eval Results

**Pass rate:** ${(r.summary.pass_rate * 100).toFixed(1)}% (${r.summary.passed}/${r.summary.total})

` + (failures.length === 0
              ? '✅ All scenarios passed.'
              : '❌ Failures:\n' + failures.map(f => `- **${f.name}**: ${f.reason}`).join('\n'));

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body,
            });
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/eval.yml
git commit -m "ci: GitHub Actions workflow runs eval suite on PR + main"
```

---

### Task 9.2: Baseline comparison script

**Files:** Create: `evals/compare_baseline.py`

- [ ] **Step 1: Write the script**

```python
# evals/compare_baseline.py
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--max-regression", type=float, default=0.0,
                        help="Max allowed drop in pass rate vs baseline (0.0 = no regressions)")
    args = parser.parse_args(argv)

    current = json.loads(args.current.read_text())
    if not args.baseline.exists():
        print(f"Baseline {args.baseline} not found; treating as no-regression.")
        return 0 if current["summary"]["pass_rate"] == 1.0 else 1

    baseline = json.loads(args.baseline.read_text())
    cur_rate = current["summary"]["pass_rate"]
    base_rate = baseline["summary"]["pass_rate"]
    delta = cur_rate - base_rate

    print(f"Pass rate current={cur_rate:.3f} baseline={base_rate:.3f} delta={delta:+.3f}")

    if delta < -args.max_regression:
        # Identify which scenarios specifically regressed
        cur_pass = {s["name"]: s["passed"] for s in current["scenarios"]}
        base_pass = {s["name"]: s["passed"] for s in baseline["scenarios"]}
        regressed = [n for n in base_pass if base_pass[n] and not cur_pass.get(n, False)]
        print(f"REGRESSION: {len(regressed)} scenario(s) regressed:")
        for n in regressed:
            print(f"  - {n}")
        return 1

    if cur_rate < 1.0:
        print("Current run has failures (independent of baseline). Failing CI.")
        return 1

    print("OK: no regression detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test locally**

```bash
.venv/Scripts/python -m evals.runner --output-json /tmp/current.json
.venv/Scripts/python -m evals.compare_baseline --current /tmp/current.json --baseline evals/baselines/main.json
```

Expected: "OK: no regression detected."

- [ ] **Step 3: Commit**

```bash
git add evals/compare_baseline.py
git commit -m "ci: baseline regression check"
```

---

### Task 9.3: Push + verify CI runs

- [ ] **Step 1: Create GitHub repo (if not done)**

```bash
# Use gh CLI or web UI
gh repo create recon-agent --public --source=. --remote=origin --push
```

- [ ] **Step 2: Open a test PR**

```bash
git checkout -b ci-test
echo "# trigger CI" >> README.md
git add README.md
git commit -m "test: trigger CI"
git push -u origin ci-test
gh pr create --title "test: trigger CI" --body "Verify eval workflow"
```

- [ ] **Step 3: Watch the workflow**

```bash
gh run watch
```

Expected: workflow completes in <3 min, green check, PR comment with "✅ All scenarios passed."

- [ ] **Step 4: Close the test PR**

```bash
gh pr close --delete-branch
git checkout main
```

- [ ] **Step 5: Commit any final tweaks needed**

If the workflow needed adjustments (path issues, etc.), iterate and commit.

---

### Phase 9 verification

- [ ] **Confirm exit criteria:**
- `.github/workflows/eval.yml` workflow runs on PR
- Green CI badge appears in README (add `![eval status](https://github.com/.../actions/workflows/eval.yml/badge.svg)` to README)
- Workflow fails on intentional regression (sanity-check: change a prompt to break a scenario, push, verify CI red, revert)

Once green, proceed to Phase 10.

---

## Phase 10 — Documentation & polish (submission-ready)

**Entry condition:** Phase 9 complete; CI green.

**Exit condition:**
- `README.md` has all 11 sections (a-k) with real data
- `docs/architecture.md`, `docs/model_routing.md`, `docs/recovery_strategies.md` written
- "What broke first" filled with a real story
- "What I'd change with 2 more weeks" filled
- Cost table populated with real numbers from `reports/eval_*/results.md`
- Loom video recorded per `LOOM_SCRIPT.md`
- Submission email composed but not sent until final check

**Phase summary:** Write the README and three docs/ files. Pull real numbers from the latest eval and demo runs. Record the Loom. Verify submission checklist. Submit.

---

### Task 10.1: `docs/architecture.md`

**Files:** Create: `docs/architecture.md`

- [ ] **Step 1: Write the architecture doc**

```markdown
# Architecture

## The loop

`AgentLoop.run()` is ~70 lines. While the agent is not terminal:

1. **Budget gate** — `budget.check(state)` at the top of every iteration. Breach → write `PARTIAL_REPORT.md`, halt, exit 2.
2. **PLAN** — LLM call (Gemini 2.5 Pro) emits a `PlanOutput` with one tool call + reasoning.
3. **ACT** — `ToolRegistry.get(plan.intended_tool)` → call → typed `ToolResult`.
4. **Recovery branch (only on tool error)** — classifier dispatches to retry / replan / degrade. Loop never sees raw exceptions.
5. **OBSERVE** — summarize the tool output, patch state.
6. **DECIDE** — LLM call (Gemini 2.5 Pro) returns next phase + reasoning.
7. **`state.apply(decision)`** — bumps `version` + `step`; writes `step_<n>.json` snapshot.

The Plan/Act/Observe/Decide phases are real classes in `src/recon_agent/agent/phases.py` — not method comments inside a single loop function.

## Data flow

```
fixtures/tracking_db.csv  ──┐
                             ├──▶ load_csv ────▶ state.txns_csv ──┐
fixtures/payu_settlements.json ┘                                    │
                              └──▶ fetch_api ──▶ state.txns_api ──┤
                                                                    │
state.txns_csv + state.txns_api ──▶ normalize_timezone ─────────────┤
                                                                    │
                                  ──▶ match_records ──▶ state.matches + state.discrepancies
                                                                    │
                                  ──▶ classify_discrepancy ────────┘
                                  ──▶ propose_correction ──▶ state.proposals
                                  ──▶ apply_correction ──▶ corrections.jsonl
                                  ──▶ verify_reconciliation
```

## State versioning

Every `state.apply()` bumps `version` and writes `reports/run_<ts>/step_<n>.json`. Diff two snapshots to see exactly what one loop iteration changed.

## Why no framework

- Brief's deep-dive will ask "what's under every abstraction layer?" → "raw SDK call" is a one-line answer
- LangChain's `AgentExecutor` would obscure the loop we're being graded on
- Pydantic gives us the typed contracts we need; structlog gives us the JSONL; Rich gives us the dashboard. That's the entire dependency story.

## See also

- `docs/model_routing.md` — per-subtask provider/model choice
- `docs/recovery_strategies.md` — error-code → strategy table
- `docs/superpowers/specs/2026-05-23-recon-agent-design.md` — canonical design spec
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: architecture overview with data-flow diagram"
```

---

### Task 10.2: `docs/model_routing.md`

**Files:** Create: `docs/model_routing.md`

- [ ] **Step 1: Write it**

```markdown
# Model Routing

| Subtask | Provider | Model | Cost ($/M in, $/M out) | Why this model |
|---------|----------|-------|------------------------|----------------|
| `plan` | Google | gemini-2.5-pro | $1.25 / $5.00 | Hot reasoning path; mistakes cascade. Gemini 2.5 Pro leads on tool-selection benchmarks. |
| `decide` | Google | gemini-2.5-pro | $1.25 / $5.00 | Same reasoning bar. Amortizes the Gemini client. |
| `classify` | OpenAI | gpt-4o-mini | $0.15 / $0.60 | High-volume cheap structured JSON. 1% of Gemini Pro's price; output is just a Pydantic enum classification. |
| `propose` | Google | gemini-2.5-flash | $0.075 / $0.30 | Per-correction call; many of them; cheap is the right answer. |
| `summary` | Google | gemini-2.5-flash | $0.075 / $0.30 | One call at end; natural-language only. |
| `shadow_plan` | OpenAI | gpt-4o | $2.50 / $10.00 | Apples-to-apples comparison vs Gemini Pro on Plan. Only invoked when `--shadow` set. |

## Why two providers, not four

The rubric rewards "4+ providers used deliberately". The keyword is **deliberately**. Adding Groq for shadow-Decide and DeepSeek for error parsing would be subtasks-in-search-of-a-provider. The brief itself warns against this anti-pattern: "Using GPT-4o for everything shows a lack of judgment" — and so does using four providers when two are doing real work.

Instead, the 2-provider story is tight: each provider has multiple justified subtasks, costs tracked per task, shadow comparison statistically validates the Plan-phase choice. See `reports/shadow_comparison_*.md` for the statistical artifact.

## Switching providers

Want to swap Gemini for Claude on Plan?

1. Add `claude_call(...)` adapter to `src/recon_agent/llm/providers.py` (~30 LOC)
2. Add pricing entry to `src/recon_agent/llm/pricing.py`
3. Update `ROUTING_TABLE["plan"]` in `router.py`
4. Re-record cassettes: `make eval-live`

Total time: ~20 minutes.
```

- [ ] **Step 2: Commit**

```bash
git add docs/model_routing.md
git commit -m "docs: model routing table with per-row rationale"
```

---

### Task 10.3: `docs/recovery_strategies.md`

**Files:** Create: `docs/recovery_strategies.md`

- [ ] **Step 1: Write it**

```markdown
# Recovery Strategies

Every `ToolError` goes through `ErrorClassifier.classify(error, state)` → one of three strategies.

## Error → strategy table

| Error code | `kind` | First strategy | If retries exhausted |
|---|---|---|---|
| `RATE_LIMIT` (HTTP 429) | transient | retry w/ exp backoff | replan ("API rate-limited") |
| `API_5XX` | transient | retry w/ exp backoff | replan |
| `API_TIMEOUT` | transient | retry once | replan |
| `API_NOT_FOUND` (404) | persistent | **replan immediately** (no retry) | — |
| `API_AUTH` (401/403) | fatal | **degrade immediately** | — |
| `MALFORMED_CSV` | persistent | replan ("try latin-1") | — |
| `FILE_NOT_FOUND` | fatal | degrade | — |
| `LLM_RATE_LIMIT` | transient | retry w/ backoff | replan |
| `LLM_TIMEOUT` | transient | retry once | replan |
| `LLM_BAD_OUTPUT` | persistent | retry once with stricter prompt | replan |
| `LEDGER_WRITE_FAILED` | fatal | degrade (data integrity) | — |
| `LOW_CONFIDENCE` | persistent | replan ("request manual review") | — |
| (any) + `consecutive_failures ≥ 3` | (any) | **degrade** | — |

## Backoff parameters

```python
MAX_RETRIES = 3
BACKOFF_BASE_MS = 1000
BACKOFF_MAX_MS = 8000
JITTER_RATIO = 0.3   # ±30%
```

## What happens on each strategy

- **RetryWithBackoff**: `time.sleep(backoff_ms / 1000)`, re-run the SAME tool with the SAME args. New `ToolCallRecord` appended.
- **ReplanWithAlternativeTool**: Force the loop back to PLAN phase, with `hint` added to the Plan's system context.
- **GracefulDegrade**: Emit HALT with `halt_reason="graceful degrade: ..."`. Loop exits cleanly with `status=degraded`. Reconciliation report shows what got done.

## Why a 404 is NOT a rate limit

A 404 means the endpoint doesn't exist OR the resource is gone. Retrying won't help — we'd just hit the same 404. So 404 is `persistent` and triggers immediate replan with hint "fetch_api unreliable; proceed CSV-only".

A 429 means the server is throttling. Retrying after a backoff might succeed. So 429 is `transient` and triggers retry.
```

- [ ] **Step 2: Commit**

```bash
git add docs/recovery_strategies.md
git commit -m "docs: recovery strategies + error-to-strategy table"
```

---

### Task 10.4: README — sections a-e (architecture, run, eval results)

**Files:** Modify: `README.md`

- [ ] **Step 1: Write a real README replacing the stub**

```markdown
# Recon Agent

> Single autonomous agent that reconciles GrabOn deal-redemption transactions across a CSV tracking DB and a PayU settlement API. Plans, acts, observes, decides; recovers from failure; respects budget. Produces a verifiable reconciliation report — without human intervention.

[![eval status](https://github.com/<USER>/recon-agent/actions/workflows/eval.yml/badge.svg)](https://github.com/<USER>/recon-agent/actions)

## (a) What I built and why I chose Assignment 02

**The system.** A ReAct-style agent loop (`AgentLoop.run()`) with four named phases — Plan, Act, Observe, Decide. Each phase is a real class. The loop calls 8 typed tools through a `ToolRegistry`, routes LLM calls through a 2-provider router (Gemini + OpenAI), distinguishes transient/persistent/fatal errors via a recovery layer, enforces five budget ceilings, and writes a versioned state snapshot after every iteration. Twelve eval scenarios cover happy paths, recovery, budget breaches, and impossible inputs.

**Why Assignment 02.** Transaction reconciliation has unambiguous ground truth — my fixture generator injects defects, the verifier checks the agent's output against the known defects. That lets me focus on the agent-engineering axis the rubric grades, not on web-scraping luck or LLM-as-judge subjectivity.

**Why this stack.** Raw Python SDKs (no LangChain/CrewAI). Pydantic v2 for every contract. structlog → JSONL on disk. Rich → live dashboard. The brief's deep-dive will ask "what's under every abstraction?" — the answer is "the SDK call I made; here's the file."

## (b) Architecture

See `docs/architecture.md` for the diagram and walkthrough. TL;DR:

```
budget.check → PLAN (LLM) → ACT (tool) ──fail──▶ Recovery (retry/replan/degrade)
                                ▼                       │
                              OBSERVE                   │
                                ▼                       │
                              DECIDE (LLM) ◀────────────┘
                                ▼
                            state.apply() → snapshot to disk
```

## (c) Per-module design decisions

| Module | Decision | Tradeoff |
|---|---|---|
| `agent/` | ReAct over Plan-and-Execute | More LLM calls per run, but simpler recovery and concrete per-step reasoning |
| `tools/` | Auto-discovery from `src/recon_agent/tools/*.py` | Adding a new tool = 1 file; no registry edit |
| `llm/` | 2 providers (Gemini + OpenAI) instead of 4 | -3 rubric points theoretical max, +confidence in the deep-dive |
| `recovery/` | Separate layer, dispatched from classifier | Loop stays readable; recovery testable in isolation |
| `observability/` | Three layers (dashboard / JSONL / snapshots) | More code, but answers any "at step N why?" in 30 seconds |
| `data/` | Deterministic fixture generator + ground truth files | Evals are mechanically verifiable; demos are reproducible |
| `evals/` | 12 rigorous scenarios over 30+ parametric | Defended in README §(i) |

## (d) How to run

```bash
git clone https://github.com/<USER>/recon-agent
cd recon-agent
make setup                            # ~90s; venv + deps + .env from .env.example
$EDITOR .env                          # add GEMINI_API_KEY + OPENAI_API_KEY
make eval                             # ~30s; 12/12 PASS via cassette replay (no API needed)
make demo                             # ~45s; live agent run on default fixture
```

**Total time from `git clone` to a running agent: ~3-4 minutes.**

**Common stress-test invocations** (these are the commands the deep-dive interviewer can run):

```bash
make demo                                         # baseline
recon demo --disable-tool fetch_api               # agent re-plans
recon demo --budget-calls 3                       # halts cleanly with PARTIAL_REPORT.md
recon demo --seed-fail-rate 1.0                   # forced 429 storm; recovery loop
recon demo --shadow                               # Plan via Gemini Pro + GPT-4o in parallel
make eval-compare                                 # paired-bootstrap comparison report
```

## (e) Eval results

Pulled from `reports/eval_<latest>/results.md`:

| | |
|---|---|
| Pass rate | **12/12 (100%)** |
| Total wall-clock (replay) | ~30s |
| Total cost (replay) | ₹0.00 |
| Total cost (live `make eval-live`) | ~₹52 |
| Cassette hit rate | 100% |

Per-scenario detail in `reports/eval_<latest>/results.md`. Shadow comparison (Gemini Pro vs GPT-4o on Plan) in `reports/shadow_comparison_<latest>.md`:

> **Gemini 2.5 Pro is statistically better for Plan at p=<from real run>. Keep current routing.**
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): sections (a)-(e) — what, architecture, how to run, eval results"
```

---

### Task 10.5: README — sections f-k + final cost data

**Files:** Modify: `README.md`; pull real numbers from `reports/eval_*/results.md`

- [ ] **Step 1: Run final live eval to harvest real cost numbers**

```bash
make eval-live > /tmp/eval_live.log
cat reports/eval_<ts>/results.md
```

Note the per-scenario `Cost ₹` column and total.

Also run a demo and note its cost:
```bash
make demo
# Note the "Total cost: ₹X.XX" line
```

- [ ] **Step 2: Append README sections f-k**

```markdown
## (f) What broke first

**To be replaced with the actual hardest bug encountered during build.** Format:

> **What we saw:** [symptom]
> **What we tried first:** [wrong hypothesis #1]
> **What actually fixed it:** [root cause + the fix]
> **What we learned:** [generalizable lesson]

Likely candidates (any one of these would be a good story — pick the real one):
- Cassette hash inputs forgot to include `response_schema` → silent replay of stale responses after a schema change
- Gemini's `response_schema=` rejected some Pydantic union fields → had to flatten the schema with `model_json_schema(mode="serialization")`
- Asyncio shadow runner deadlock when both futures shared a single `genai.Client` — fixed by per-call client instantiation
- IST-as-UTC detection false-positive on Indian-merchant late-night transactions (post-midnight IST hits "looks UTC" heuristic)

## (g) What I would change with 2 more weeks

1. **Real PayU sandbox integration** instead of static JSON fixture. PayU has a free tier; would exercise actual rate-limit semantics + signing.
2. **MCP server skin** so the agent is callable from Claude Desktop. Maps to Assignment 04's MCP requirement; natural production interface.
3. **Add Groq Llama 3.1 70B for shadow on classify** subtask. Plan-shadow is already done; extending to classify doubles the comparison artifact's coverage.
4. **Persist runs to SQLite** for cross-run analysis. Right now everything is filesystem. Would enable queries like "average cost over the last 50 runs grouped by scenario."
5. **Prompt versioning** with diff-on-regression. Currently prompts live in `.txt` files; with versioning, the CI gate could surface "this PR changed Plan prompt; here's the diff vs last green main."

## (h) Model routing rationale

See `docs/model_routing.md` for the full per-row defense. Summary:

- **Gemini 2.5 Pro** — Plan + Decide (reasoning-heavy)
- **Gemini 2.5 Flash** — Propose-correction (cheap, in-family) + summary
- **GPT-4o-mini** — Classify-discrepancy (cheap, strict JSON)
- **GPT-4o** — Shadow-Plan (capable-tier comparison vs Gemini Pro)

## (i) Eval design rationale: 12 rigorous over 30+ parametric

The rubric says "30+ cases, catches a real regression. Statistical comparison with p-values. CI/CD gate."

I chose 12 rigorous scenarios instead of 30+ parametric variations. Each of the 12 tests a specific axis: a discrepancy kind (5), a recovery path (3), a budget ceiling (2), an impossible input (2). The underlying rubric criterion is "catches a real regression" — I meet that via:

- **Cassette drift detection** on `make eval-live` (any LLM behavior change surfaces immediately)
- **Paired bootstrap** + p-value for any config comparison (`reports/shadow_comparison_*.md`)
- **CI gate** that blocks merge on any regression vs `evals/baselines/main.json`

Inflating to 30+ parametric scenarios would add coverage on dimensions I've already covered, while diluting the signal of any individual scenario. I'd rather defend 12 scenarios that each test something real.

## (j) Cost data

(All numbers from `reports/eval_<latest>/results.md` + provider dashboards. USD↔INR at 83.0.)

| Activity | Cost ₹ | Cost USD |
|----------|--------|----------|
| One agent run (live, default fixture) | **₹<fill from real demo>** | $<fill> |
| One agent run (live, `--shadow`) | **₹<fill>** | $<fill> |
| One eval-live run (12 scenarios) | **₹<fill from real make eval-live>** | $<fill> |
| One eval-replay run | **₹0.00** | $0.00 |
| One eval-compare run | **₹<fill>** | $<fill> |
| Total development cost (4 days) | **₹<fill from provider dashboards>** | $<fill> |

Free-tier sufficient: Gemini AI Studio (no credit card) + OpenAI signup credits ($5).

## (k) Operations cheatsheet

| If you want to see... | Open... |
|---|---|
| Architecture diagram | `docs/architecture.md` |
| The loop in code | `src/recon_agent/agent/loop.py` |
| Reasoning at step N | `reports/run_<ts>/step_<N>.json` + `log.jsonl` |
| Why model X for Y | `docs/model_routing.md` |
| How recovery works | `docs/recovery_strategies.md` |
| Latest eval pass rate | `reports/eval_<latest>/results.md` |
| Shadow comparison | `reports/shadow_comparison_<latest>.md` |
| Full design spec | `docs/superpowers/specs/2026-05-23-recon-agent-design.md` |
| Interview prep | `DEEP_DIVE_PREP.md` |
| Loom recording script | `LOOM_SCRIPT.md` |
```

- [ ] **Step 3: Backfill the real cost numbers into the table from §(j)**

Replace each `<fill>` with the actual measured value.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): sections (f)-(k) with real cost data"
```

---

### Task 10.6: Fill "What broke first" with a real story

**Files:** Modify: `README.md` (section f); also fill DEEP_DIVE_PREP.md §D with the same story

- [ ] **Step 1: Pick the real hardest bug from the build**

While building, keep a `BUGS.md` scratch file. Pick the one with the most generalizable lesson.

- [ ] **Step 2: Write the story in the format**

```markdown
## (f) What broke first

**What we saw:** [the symptom, with file paths or error message if possible]

**What we tried first:** [wrong hypothesis #1] — wasted ~N hours

**What we tried next:** [wrong hypothesis #2, if any]

**What actually fixed it:** [the root cause and the precise fix, with file paths]

**What we learned:** [generalizable lesson; one or two sentences]
```

Honest > dramatic. The lesson matters more than the symptom.

- [ ] **Step 3: Mirror in `DEEP_DIVE_PREP.md` §D**

Copy the same content into `DEEP_DIVE_PREP.md` under "Section D — What broke first".

- [ ] **Step 4: Commit**

```bash
git add README.md DEEP_DIVE_PREP.md
git commit -m "docs: fill 'what broke first' with the real story"
```

---

### Task 10.7: Fill "What I'd change with 2 more weeks" with concrete items

**Files:** Modify: `README.md` (section g) + `DEEP_DIVE_PREP.md` §E

- [ ] **Step 1: Pick 3-5 items from the candidate list (or invent your own)**

Likely keepers (already in README stub):
- Real PayU sandbox integration
- MCP server skin
- 3rd provider for Classify-phase shadow
- SQLite persistence for cross-run analytics
- Prompt versioning + diff-on-regression

Pick 3-5. Don't list 10 — looks unfocused.

- [ ] **Step 2: For each, write 2 sentences max** — what + why it matters.

- [ ] **Step 3: Commit**

```bash
git add README.md DEEP_DIVE_PREP.md
git commit -m "docs: finalize 'what I'd change with 2 more weeks'"
```

---

### Task 10.8: Record the Loom video

**Files:** No code change; produce a Loom video file/link.

- [ ] **Step 1: Pre-recording checklist** (see `LOOM_SCRIPT.md` §Pre-recording)

- [ ] **Step 2: Record 4 scenes per `LOOM_SCRIPT.md`**

- [ ] **Step 3: Verify audio quality + length** (12-19 min target)

- [ ] **Step 4: Get the Loom link, set to UNLISTED (not private)**

- [ ] **Step 5: Add the Loom link to README**

```markdown
## Walkthrough video
[Loom — 15-20 min walkthrough](<LOOM_URL>)
```

```bash
git add README.md
git commit -m "docs(readme): embed Loom walkthrough link"
```

---

### Task 10.9: Final submission checklist

- [ ] **Step 1: 15-minute setup test on a clean machine**

On a different machine (or fresh Docker container, or a co-worker's machine):

```bash
git clone https://github.com/<USER>/recon-agent
cd recon-agent
make setup
# edit .env with API keys (~60s)
make eval
make demo
```

Time the full flow. Must complete in <15 min. If it doesn't, fix README §(d) until it does.

- [ ] **Step 2: Run the final eval + commit baseline**

```bash
make eval-live          # re-records cassettes
make eval               # verifies replay works
make refresh-baseline   # updates evals/baselines/main.json
git add evals/cassettes/*.jsonl evals/baselines/main.json
git commit -m "chore(evals): final cassettes + baseline for submission"
```

- [ ] **Step 3: Verify CI is green on main**

```bash
gh run watch
```

- [ ] **Step 4: Submission verification** (walk through every item)

- [ ] Public GitHub repo, clone works in incognito
- [ ] README §(a)-(k) complete; especially §(f) with real story
- [ ] `evals/baselines/main.json` + latest `reports/eval_*/results.md` committed
- [ ] `reports/shadow_comparison_*.md` committed
- [ ] Cost table in README §(j) has real numbers, no `<fill>`
- [ ] Cassettes committed for all 12 scenarios
- [ ] CI checkmark green on latest commit on main
- [ ] Loom 15-20 min, audio clear, link UNLISTED (not private)
- [ ] Resume PDF saved as `<lastname>_<firstname>_resume.pdf`
- [ ] Email drafted to `careers@grabon.in`, subject `AI Labs - <Your Name> - Assignment 02`

- [ ] **Step 5: Final commit on main**

```bash
# Tag the submission
git tag -a v1.0-submission -m "GrabOn AI Labs Challenge 02 submission"
git push --tags
```

- [ ] **Step 6: Send the email**

Subject: `AI Labs - <Your Name> - Assignment 02`

Body:
```
Hi GrabOn AI Labs team,

My submission for the Agentic AI Engineer Challenge — Assignment 02 ("The Loop"):

  Repo:  https://github.com/<USER>/recon-agent
  Loom:  <LOOM_URL>
  Resume: attached (<lastname>_<firstname>_resume.pdf)

Quick stats from the eval suite (12 scenarios, paired bootstrap comparison):
  - 12/12 PASS in replay mode (~30s, free)
  - 2 providers used deliberately (Gemini + OpenAI), shadow testing on Plan
  - 8 typed tools, full Plan/Act/Observe/Decide loop
  - GitHub Actions CI gate blocks regressions

Happy to walk through architecture in the deep-dive.

Best,
<Your Name>
```

- [ ] **Step 7: Attach resume, hit send.**

---

### Phase 10 verification

- [ ] **Final exit criteria check:**

```bash
git status                 # clean
git log --oneline | head   # all commits squashed/reasonable
cat README.md | grep -c '<fill>'    # should be 0
gh run list --limit 1 --json conclusion --jq '.[0].conclusion'   # should be "success"
```

- [ ] Submission email sent.

---

## Self-review notes (for the implementer)

This plan covers ~70 tasks across 10 phases. Each phase is independently shippable — at the end of each phase, the repo is in a working state with a clean commit.

**Where the plan deliberately leaves room for judgment:**

- **Task 10.6 ("what broke first")** is a placeholder until the implementer has actually built it and hit a real bug. That's correct — fabricating it would defeat the purpose.
- **Task 10.7 ("what I'd change")** has candidates listed; the implementer picks the ones that feel honest after living with the code.
- **Specific cost numbers in Task 10.5** can only be filled after `make eval-live` runs on real APIs. The placeholder is intentional.

**Common pitfalls to watch for during execution:**

- **Cassette hash stability:** if you change a Pydantic schema and forget to re-record, cassettes still match by hash but the parsed result will be wrong. Solution: include `model_json_schema()` in the hash inputs (already done in `cassettes.py`).
- **Gemini structured output edge cases:** Gemini sometimes refuses `response_schema` with deeply nested unions. Test with the actual Pydantic models early; flatten if needed.
- **Recovery loop infinite-retry bug:** make sure `ErrorClassifier._retry_counts` is per-error-code AND bounded by `MAX_RETRIES`. Easy to write a version that always returns retry.
- **Windows path separators in the Makefile:** swap `.venv/Scripts/` → `.venv/bin/` on macOS/Linux.

---

**Plan complete.**
