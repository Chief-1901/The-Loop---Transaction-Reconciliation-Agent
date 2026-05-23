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
