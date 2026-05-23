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
