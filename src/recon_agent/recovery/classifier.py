from __future__ import annotations
import random
from typing import Literal

from pydantic import BaseModel

from ..agent.state import AgentState
from ..tools.base import ToolError


MAX_RETRIES = 3
BACKOFF_BASE_MS = 1000
BACKOFF_MAX_MS = 8000
JITTER_RATIO = 0.3


class RecoveryAction(BaseModel):
    kind: Literal["retry", "replan", "degrade"]
    reason: str
    backoff_ms: int = 0
    hint: str = ""


class ErrorClassifier:
    def __init__(self):
        self._retry_counts: dict[str, int] = {}

    def _record_retry(self, state: AgentState, code: str) -> None:
        self._retry_counts[code] = self._retry_counts.get(code, 0) + 1

    def _retries_so_far(self, code: str) -> int:
        return self._retry_counts.get(code, 0)

    def _backoff(self, attempt: int) -> int:
        base = min(BACKOFF_BASE_MS * (2 ** attempt), BACKOFF_MAX_MS)
        jitter = random.uniform(-JITTER_RATIO, JITTER_RATIO) * base
        return int(base + jitter)

    def _alternative_hint(self, error: ToolError, state: AgentState) -> str:
        if "API" in error.code:
            return "fetch_api unreliable; proceed CSV-only and flag missing_in_api"
        if "MALFORMED_CSV" in error.code:
            return "CSV malformed; try load_csv with encoding=latin-1"
        if "LLM" in error.code:
            return "LLM unstable; reduce prompt size or skip this classification"
        if "LOW_CONFIDENCE" in error.code:
            return "low-confidence proposal; consider requesting manual_review"
        return f"avoid the failing path for {error.code}"

    def classify(self, error: ToolError, state: AgentState) -> RecoveryAction:
        # fatal OR repeated consecutive failures → degrade
        if error.kind == "fatal" or state.consecutive_failures >= 3:
            return RecoveryAction(
                kind="degrade",
                reason=f"{error.kind} {error.code}" if error.kind == "fatal"
                       else f"{state.consecutive_failures}+ consecutive failures",
            )

        # transient with retry budget → retry
        if error.kind == "transient" and self._retries_so_far(error.code) < MAX_RETRIES:
            attempt = self._retries_so_far(error.code)
            self._record_retry(state, error.code)
            return RecoveryAction(
                kind="retry",
                reason=f"transient {error.code}, attempt {attempt + 1}/{MAX_RETRIES}",
                backoff_ms=self._backoff(attempt),
            )

        # transient exhausted retries → escalate to replan
        if error.kind == "transient":
            return RecoveryAction(
                kind="replan",
                reason=f"transient {error.code} survived {MAX_RETRIES} retries",
                hint=self._alternative_hint(error, state),
            )

        # persistent → replan immediately
        if error.kind == "persistent":
            return RecoveryAction(
                kind="replan",
                reason=f"persistent {error.code}",
                hint=self._alternative_hint(error, state),
            )

        return RecoveryAction(kind="degrade", reason="unclassified")
