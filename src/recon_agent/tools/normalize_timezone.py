from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


class NormalizeTZInput(BaseModel):
    records: list[dict]
    timestamp_field: str = "settled_at"
    target_tz: Literal["UTC"] = "UTC"


class NormalizeTZOutput(BaseModel):
    records: list[dict]
    suspected_ist_as_utc: list[str]
    converted_count: int


class NormalizeTimezone(Tool[NormalizeTZInput, NormalizeTZOutput]):
    name = "normalize_timezone"
    input_schema = NormalizeTZInput
    output_schema = NormalizeTZOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 5.0

    def run(self, inputs: NormalizeTZInput) -> ToolResult[NormalizeTZOutput]:
        out_records: list[dict] = []
        suspected: list[str] = []
        converted = 0

        for r in inputs.records:
            if inputs.timestamp_field not in r:
                return ToolResult(ok=False, error=ToolError(
                    kind="persistent", code="MISSING_FIELD",
                    message=f"{inputs.timestamp_field} missing in record", retriable=False,
                ))
            try:
                dt = datetime.fromisoformat(r[inputs.timestamp_field])
            except ValueError as e:
                return ToolResult(ok=False, error=ToolError(
                    kind="persistent", code="UNPARSEABLE_TIMESTAMP",
                    message=str(e), retriable=False,
                ))

            new_rec = dict(r)
            new_rec["_orig_tz"] = r[inputs.timestamp_field]

            # IST-as-UTC heuristic: tz claims UTC but the hour matches the IST clock
            # of a hint timestamp (e.g., _csv_ts or redemption_ts) — suggests value is IST mislabeled
            if dt.utcoffset() is not None and dt.utcoffset().total_seconds() == 0:
                csv_hint = r.get("_csv_ts") or r.get("redemption_ts")
                if csv_hint:
                    try:
                        csv_dt = datetime.fromisoformat(csv_hint)
                        if dt.hour == csv_dt.hour and dt.minute == csv_dt.minute:
                            suspected.append(r.get("reference_id") or r.get("txn_id") or "?")
                    except ValueError:
                        pass

            new_rec[inputs.timestamp_field] = dt.astimezone(timezone.utc).isoformat()
            if dt.tzinfo != timezone.utc and (
                dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0
            ):
                converted += 1
            out_records.append(new_rec)

        return ToolResult(ok=True, output=NormalizeTZOutput(
            records=out_records,
            suspected_ist_as_utc=suspected,
            converted_count=converted,
        ))
