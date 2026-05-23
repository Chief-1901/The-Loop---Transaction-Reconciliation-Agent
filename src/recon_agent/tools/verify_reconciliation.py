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
