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
