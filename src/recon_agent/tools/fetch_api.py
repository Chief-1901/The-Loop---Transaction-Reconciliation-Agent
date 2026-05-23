from __future__ import annotations
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .base import Tool, ToolError, ToolResult


_RNG_SEED_ENV = "FETCH_API_RNG_SEED"


class FetchAPIInput(BaseModel):
    endpoint: Literal["payu_settlements"]
    limit: int = 1000


class FetchAPIOutput(BaseModel):
    records: list[dict]
    pulled_at: str
    next_cursor: str | None = None


def _fail_rate() -> float:
    return float(os.environ.get("FETCH_API_FAIL_RATE", "0.30"))


def _disabled() -> bool:
    return os.environ.get("FETCH_API_DISABLED") == "1"


def _seeded_rng() -> random.Random:
    seed = os.environ.get(_RNG_SEED_ENV)
    if seed is not None:
        return random.Random(int(seed) + int(time.time() * 1000) % 1000)
    return random.Random()


class FetchAPI(Tool[FetchAPIInput, FetchAPIOutput]):
    name = "fetch_api"
    input_schema = FetchAPIInput
    output_schema = FetchAPIOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 10.0

    def run(self, inputs: FetchAPIInput) -> ToolResult[FetchAPIOutput]:
        if _disabled():
            return ToolResult(ok=False, error=ToolError(
                kind="persistent", code="API_NOT_FOUND",
                message="fetch_api disabled via FETCH_API_DISABLED env",
                retriable=False,
            ))

        rng = _seeded_rng()
        roll = rng.random()
        fail_rate = _fail_rate()
        if roll < fail_rate:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="RATE_LIMIT",
                message=f"HTTP 429 (simulated; rolled {roll:.3f} < {fail_rate})",
                retriable=True,
            ))
        # 2% 5xx
        if roll < fail_rate + 0.02:
            return ToolResult(ok=False, error=ToolError(
                kind="transient", code="API_5XX",
                message="HTTP 503 (simulated)", retriable=True,
            ))

        fixture_dir = Path(os.environ.get("FIXTURE_DIR", "src/recon_agent/data/fixtures"))
        path = fixture_dir / "payu_settlements.json"
        if not path.exists():
            return ToolResult(ok=False, error=ToolError(
                kind="fatal", code="API_NOT_FOUND",
                message=f"fixture file {path} missing", retriable=False,
            ))
        payload = json.loads(path.read_text())
        records = payload.get("records", [])[: inputs.limit]
        return ToolResult(ok=True, output=FetchAPIOutput(
            records=records,
            pulled_at=datetime.now(timezone.utc).isoformat(),
            next_cursor=None,
        ))
