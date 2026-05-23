from __future__ import annotations
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .state import AgentState, LLMCallRecord, ToolCallRecord


class Phase(str, Enum):
    PLAN    = "PLAN"
    ACT     = "ACT"
    OBSERVE = "OBSERVE"
    DECIDE  = "DECIDE"
    HALT    = "HALT"


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
                f"Task brief: {state.task_brief}\n\n"
                f"Available tools:\n{schemas}\n\nCurrent state:\n{ctx}\n\n"
                "CRITICAL RULES:\n"
                "1. tool_args MUST be a JSON object with ALL required fields from input_schema.\n"
                "2. NEVER emit tool_args as an empty object {}.\n"
                "3. For load_csv: tool_args = {\"path\": \"<the CSV path from task brief>\"}\n"
                "4. For fetch_api: tool_args = {\"endpoint\": \"payu_settlements\"}\n"
                "Emit the next action."},
        ]
        out, call = self._router.call(
            "plan", messages, PlanOutput, step=state.step, phase=Phase.PLAN
        )
        # Post-process: fill missing required args from task_brief/state if LLM omitted them
        out = self._repair_args(out, state)
        return out, call

    def _repair_args(self, out: PlanOutput, state: AgentState) -> PlanOutput:
        """Fill in missing required tool args from task_brief or state data."""
        import re
        task_brief = state.task_brief
        tool = out.intended_tool
        args = dict(out.tool_args)

        if tool == "load_csv" and not args.get("path"):
            m = re.search(r"CSV file:\s*(.*?\.csv)", task_brief)
            if m:
                args["path"] = m.group(1)

        elif tool == "fetch_api" and not args.get("endpoint"):
            args["endpoint"] = "payu_settlements"

        elif tool == "normalize_timezone" and not args.get("records"):
            # Inject API records from state (or CSV if API not loaded)
            if state.txns_api:
                args["records"] = state.txns_api
            elif state.txns_csv:
                args["records"] = state.txns_csv

        elif tool == "match_records":
            if not args.get("csv_records") and state.txns_csv:
                args["csv_records"] = state.txns_csv
            if not args.get("api_records") and state.txns_api:
                args["api_records"] = state.txns_api

        elif tool == "classify_discrepancy":
            # Inject from state's match results
            if not args.get("unmatched_csv"):
                args["unmatched_csv"] = state.unmatched_csv
            if not args.get("unmatched_api"):
                args["unmatched_api"] = state.unmatched_api
            if not args.get("value_conflicts"):
                args["value_conflicts"] = state.value_conflicts
            if not args.get("timezone_suspects"):
                args["timezone_suspects"] = state.timezone_suspects

        elif tool == "propose_correction":
            if not args.get("discrepancy") and state.discrepancies:
                # Pick the next unproposed discrepancy
                next_idx = len(state.proposals)
                if next_idx < len(state.discrepancies):
                    args["discrepancy"] = state.discrepancies[next_idx].model_dump()

        elif tool == "apply_correction":
            if not args.get("proposal") and state.proposals:
                # Pick the next unapplied proposal
                next_idx = state.corrections_applied
                if next_idx < len(state.proposals):
                    args["proposal"] = state.proposals[next_idx].model_dump()

        elif tool == "verify_reconciliation":
            if not args.get("csv_records") and state.txns_csv:
                args["csv_records"] = state.txns_csv
            if not args.get("api_records") and state.txns_api:
                args["api_records"] = state.txns_api
            if not args.get("discrepancies"):
                args["discrepancies"] = [d.model_dump() for d in state.discrepancies]
            if not args.get("ledger_path"):
                args["ledger_path"] = "corrections.jsonl"

        if args != out.tool_args:
            return PlanOutput(
                intended_tool=out.intended_tool,
                tool_args=args,
                reasoning=out.reasoning,
                estimated_cost_inr=out.estimated_cost_inr,
            )
        return out

    def _build_context(self, state: AgentState) -> str:
        lines = [
            f"task={state.task_brief}",
            f"step={state.step} csv_loaded={state.csv_loaded} "
            f"api_loaded={state.api_loaded} tz_normalized={state.timezone_normalized} "
            f"matches={len(state.matches)} discrepancies={len(state.discrepancies)} "
            f"proposals={len(state.proposals)} applied={state.corrections_applied} "
            f"last_reasoning='{state.last_decision_reasoning[:200]}'",
        ]
        # Tool argument hints: tell the LLM what data is now available in state
        if state.csv_loaded and not state.api_loaded:
            lines.append(f"HINT: csv rows available ({len(state.txns_csv)}). Next: fetch_api(endpoint='payu_settlements').")
        if state.api_loaded and not state.timezone_normalized:
            lines.append(f"HINT: api records available ({len(state.txns_api)}). Next: normalize_timezone with the api records.")
        if state.timezone_normalized and not state.matches and not state.unmatched_csv:
            lines.append(f"HINT: tz_normalized. Next: match_records with csv and api records.")
        if state.unmatched_csv or state.unmatched_api or state.value_conflicts:
            lines.append(f"HINT: unmatched_csv={len(state.unmatched_csv)} unmatched_api={len(state.unmatched_api)} value_conflicts={len(state.value_conflicts)}. Next: classify_discrepancy.")
        if state.discrepancies and len(state.proposals) < len(state.discrepancies):
            next_d = state.discrepancies[len(state.proposals)]
            lines.append(f"HINT: {len(state.discrepancies) - len(state.proposals)} discrepancies need proposals. Next: propose_correction for txn_id={next_d.txn_id} kind={next_d.kind}.")
        if state.proposals and state.corrections_applied < len(state.proposals):
            next_p = state.proposals[state.corrections_applied]
            lines.append(f"HINT: {len(state.proposals) - state.corrections_applied} proposals pending. Next: apply_correction for txn_id={next_p.txn_id} field={next_p.field}.")
        return "\n".join(lines)


class Decide:
    """LLM-backed decider: emits next phase + halt_reason."""

    PROMPT_PATH = Path(__file__).parent / "prompts" / "decide_system.txt"

    def __init__(self, router: Any, logger: Any = None):
        self._router = router
        self._system = self.PROMPT_PATH.read_text(encoding="utf-8")
        self._logger = logger

    def run(self, observation: str, state: AgentState) -> tuple["DecideOutput", LLMCallRecord]:
        from .state import DecideOutput  # local to avoid forward-ref
        # Build a rich pipeline-progress summary so the LLM understands what work remains
        pipeline = (
            f"csv_loaded={state.csv_loaded} api_loaded={state.api_loaded} "
            f"tz_normalized={state.timezone_normalized} "
            f"matches={len(state.matches)} "
            f"unmatched_csv={len(state.unmatched_csv)} unmatched_api={len(state.unmatched_api)} "
            f"value_conflicts={len(state.value_conflicts)} "
            f"discrepancies={len(state.discrepancies)} "
            f"proposals={len(state.proposals)} applied={state.corrections_applied}"
        )
        remaining = []
        if not state.csv_loaded:   remaining.append("load_csv")
        if not state.api_loaded:   remaining.append("fetch_api")
        if state.csv_loaded and state.api_loaded and not state.timezone_normalized:
            remaining.append("normalize_timezone")
        if state.timezone_normalized and not state.matches and not state.unmatched_csv:
            remaining.append("match_records")
        if state.matches is not None and (state.unmatched_csv or state.unmatched_api or state.value_conflicts) and not state.discrepancies:
            remaining.append("classify_discrepancy")
        if state.discrepancies and len(state.proposals) < len(state.discrepancies):
            remaining.append(f"propose_correction ({len(state.discrepancies) - len(state.proposals)} remaining)")
        if state.proposals and state.corrections_applied < len(state.proposals):
            remaining.append(f"apply_correction ({len(state.proposals) - state.corrections_applied} remaining)")
        if state.matches and not remaining:
            remaining.append("verify_reconciliation")
        hint = f"REMAINING STEPS: {', '.join(remaining)}" if remaining else "PIPELINE COMPLETE — can HALT"

        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content":
                f"Observation: {observation}\n\n"
                f"Pipeline: {pipeline}\n"
                f"{hint}\n"
                f"step={state.step} consecutive_failures={state.consecutive_failures}"},
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


class ActOutput(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: dict | None = None
    error: "Any | None" = None
    raw_record: "ToolCallRecord"


class Act:
    def __init__(self, tool_registry: Any, logger: Any = None):
        self._registry = tool_registry
        self._logger = logger

    def run(self, plan: PlanOutput, state: "AgentState") -> ActOutput:
        from ..tools.base import ToolError    # local import
        from .state import ToolCallRecord
        started = datetime.now(timezone.utc)
        t0 = time.time()
        tool = None
        error = None
        result = None
        ok = False
        try:
            tool = self._registry.get(plan.intended_tool)
            inputs = tool.input_schema(**plan.tool_args)
            result = tool.run(inputs)
        except KeyError as e:
            error = ToolError(kind="fatal", code="UNKNOWN_TOOL", message=str(e), retriable=False)
        except Exception as e:
            error = ToolError(kind="persistent", code="MALFORMED_INPUT",
                              message=str(e), retriable=False)
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
            cost_inr=tool.cost_estimate_inr if ok and tool is not None else 0.0,
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

    def run(self, act: ActOutput, state: "AgentState") -> str:
        """Produce a short observation summary + patch state with the tool's output."""
        if act.error:
            return f"FAILED {act.tool_name}: {act.error.code} ({act.error.kind})"

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
            state.txns_api = out.get("records", state.txns_api)  # updated with normalized timestamps
            state.timezone_suspects = out.get("suspected_ist_as_utc", [])
            return f"normalize_timezone OK: converted={out.get('converted_count', 0)} suspected_ist_as_utc={len(state.timezone_suspects)}"
        if name == "match_records":
            state.matches = out.get("matched", [])
            state.unmatched_csv = out.get("unmatched_csv", [])
            state.unmatched_api = out.get("unmatched_api", [])
            state.value_conflicts = out.get("value_conflicts", [])
            return (f"match_records OK: matched={len(state.matches)} "
                    f"unmatched_csv={len(state.unmatched_csv)} "
                    f"unmatched_api={len(state.unmatched_api)} "
                    f"value_conflicts={len(state.value_conflicts)})")
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
