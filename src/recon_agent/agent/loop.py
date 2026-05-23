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
