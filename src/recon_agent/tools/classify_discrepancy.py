from __future__ import annotations
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
