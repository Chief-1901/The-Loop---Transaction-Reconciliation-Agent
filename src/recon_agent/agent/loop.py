from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .budget import Budget, check as budget_check
from .phases import Phase, Plan, Decide, Act, Observe
from .state import AgentState, DecideOutput, LLMCallRecord
from ..recovery import RecoveryLayer
from ..observability.dashboard import Dashboard
from ..llm.shadow import ShadowRunner


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
        recovery: RecoveryLayer | None = None,
        logger: Any = None,
        run_dir: Path | None = None,
        max_iterations: int = 30,    # hard ceiling on top of budget
        enable_dashboard: bool = True,
        shadow_enabled: bool = False,
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
        self.dashboard = Dashboard(enabled=enable_dashboard)
        self.shadow = ShadowRunner(
            router=self.router,
            enabled=shadow_enabled,
            log_path=self.run_dir / "shadow.jsonl",
        )
        self.plan_phase = Plan(self.router, self.tools, self.logger, shadow=self.shadow)
        self.decide_phase = Decide(self.router, self.logger)
        self.act_phase = Act(self.tools, self.logger)
        self.observe_phase = Observe(self.logger)
        self.recovery = recovery or RecoveryLayer(logger=logger)
        # Inject the router into LLM-backed tools (classify_discrepancy, propose_correction)
        from ..tools.registry import ToolRegistry
        if hasattr(self.tools, "bind_router"):
            self.tools.bind_router(self.router)

    def run(self) -> ReconciliationReport:
        with self.dashboard:
            self.state.snapshot_to_disk(self.run_dir)
            if self.logger is not None:
                self.logger.info("loop.started", task_brief=self.state.task_brief[:120])
            self.dashboard.update(self.state, self.budget)
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

                if self.logger is not None:
                    self.logger.info("phase.plan", step=self.state.step,
                                     tool=plan_out.intended_tool, reasoning=plan_out.reasoning[:200])

                # ACT — call the real tool
                act_out = self.act_phase.run(plan_out, self.state)
                self.state.tool_calls.append(act_out.raw_record)

                if self.logger is not None:
                    self.logger.info("phase.act", step=self.state.step,
                                     tool=act_out.tool_name,
                                     outcome="ok" if not act_out.error else "error",
                                     latency_ms=act_out.raw_record.latency_ms,
                                     error_code=act_out.error.code if act_out.error else None)

                if act_out.error:
                    rec = self.recovery.handle(act_out.error, self.state, act_out, self.tools)

                    if self.logger is not None:
                        self.logger.info("recovery.dispatched", kind=rec.kind, reason=rec.reason,
                                         hint=getattr(rec, "hint", ""))

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
                        forced = DecideOutput(
                            next_phase=Phase.PLAN,
                            reasoning=f"recovery=replan: {rec.reason}. hint={rec.hint}",
                            recovery_invoked=True,
                            llm_call=_empty_llm_call(Phase.DECIDE),
                        )
                        self.state.apply(forced)
                        self.state.snapshot_to_disk(self.run_dir)
                        self.dashboard.update(self.state, self.budget)
                        continue
                    else:  # degrade
                        self._halt(f"graceful degrade: {rec.reason}")
                        break
                else:
                    self.state.consecutive_failures = 0
                    observation = self.observe_phase.run(act_out, self.state)

                # DECIDE
                try:
                    dec_out, dec_call = self.decide_phase.run(observation, self.state)
                    self.state.llm_calls.append(dec_call)
                except Exception as e:
                    self._halt(f"decide exception: {type(e).__name__}: {e}")
                    break

                if self.logger is not None:
                    self.logger.info("phase.decide", step=self.state.step,
                                     next_phase=str(dec_out.next_phase),
                                     reasoning=dec_out.reasoning[:200])

                self.state.apply(dec_out)
                self.state.snapshot_to_disk(self.run_dir)
                self.dashboard.update(self.state, self.budget)

            if not self.state.is_terminal():
                self._halt(f"max iterations {self.max_iterations} reached")

            self._write_report_json()
            return self._build_report()

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
            ("- Unverified reconciliation: yes" if not any(
                c.tool_name == "verify_reconciliation" for c in self.state.tool_calls
            ) else "- Verification: done"),
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

    def _halt(self, reason: str) -> None:
        if self.logger is not None:
            self.logger.info("loop.halted", reason=reason)
        if reason.startswith("budget breach"):
            self._write_partial_report(reason)
        decision = DecideOutput(
            next_phase=Phase.HALT, halt_reason=reason,
            reasoning=f"forced halt: {reason}",
            llm_call=_empty_llm_call(),
        )
        self.state.apply(decision)
        self.state.snapshot_to_disk(self.run_dir)

    def _write_report_json(self) -> None:
        from collections import Counter
        kinds = Counter(d.kind for d in self.state.discrepancies)
        total_cost = (sum(c.cost_inr for c in self.state.llm_calls)
                      + sum(c.cost_inr for c in self.state.tool_calls))
        # Status reclassification
        status = "halted"
        if self.state.halt_reason:
            if "complete" in self.state.halt_reason or "reconciliation" in self.state.halt_reason.lower():
                status = "completed"
            elif "degrade" in self.state.halt_reason:
                status = "degraded"
            elif "budget breach" in self.state.halt_reason:
                status = "halted"
        payload = {
            "status": status,
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
        import json
        (self.run_dir / "report.json").write_text(json.dumps(payload, indent=2))

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
