from __future__ import annotations
import csv
from pathlib import Path

import chardet
from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


class LoadCSVInput(BaseModel):
    path: str
    expected_columns: list[str] | None = None


class LoadCSVOutput(BaseModel):
    rows: list[dict]
    detected_encoding: str
    row_count: int
    skipped_rows: int = 0


class LoadCSV(Tool[LoadCSVInput, LoadCSVOutput]):
    name = "load_csv"
    input_schema = LoadCSVInput
    output_schema = LoadCSVOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 5.0

    def run(self, inputs: LoadCSVInput) -> ToolResult[LoadCSVOutput]:
        path = Path(inputs.path)
        if not path.exists():
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="FILE_NOT_FOUND",
                message=f"file not found: {path}", retriable=False,
            ))

        raw = path.read_bytes()
        if not raw:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="MALFORMED_CSV",
                message="empty file", retriable=False,
            ))

        detection = chardet.detect(raw)
        encoding = detection.get("encoding") or "utf-8"
        confidence = detection.get("confidence", 0.0)

        # Special case: pure ASCII is a strict subset of UTF-8 — always valid
        if encoding and encoding.lower() == "ascii":
            encoding = "utf-8"
            confidence = 1.0

        if confidence < 0.5:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="ENCODING_AMBIGUOUS",
                message=f"chardet confidence {confidence:.2f} for {path}",
                retriable=False,
            ))

        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError as e:
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="MALFORMED_CSV",
                message=f"decode failed with {encoding}: {e}", retriable=False,
            ))

        rows: list[dict] = []
        skipped = 0
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            if any(v is None for v in row.values()):
                skipped += 1
                continue
            rows.append(dict(row))

        return ToolResult(ok=True, output=LoadCSVOutput(
            rows=rows,
            detected_encoding=encoding.lower(),
            row_count=len(rows),
            skipped_rows=skipped,
        ))
