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
