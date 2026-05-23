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
