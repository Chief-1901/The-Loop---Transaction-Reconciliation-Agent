from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .phases import Phase

SCHEMA_VERSION = 1


class ToolCallRecord(BaseModel):
    step: int
    tool_name: str
    args: dict
    started_at: datetime
    finished_at: datetime
    latency_ms: int
    outcome: Literal["ok", "error", "recovered"]
    error_kind: Literal["transient", "persistent", "fatal"] | None = None
    error_code: str | None = None
    cost_inr: float = 0.0


class LLMCallRecord(BaseModel):
    step: int
    phase: Phase
    provider: str
    model: str
    subtask: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_inr: float
    cache_hit: bool = False


class Discrepancy(BaseModel):
    txn_id: str
    kind: Literal[
        "missing_in_api", "missing_in_csv", "value_mismatch",
        "duplicate", "timezone_shift", "encoding_corruption",
    ]
    csv_record: dict | None = None
    api_record: dict | None = None
    severity: Literal["low", "medium", "high"] = "medium"
    confidence: float = 1.0


class CorrectionProposal(BaseModel):
    txn_id: str
    field: str
    old_value: object | None = None
    new_value: object | None = None
    reason: str
    confidence: float


class DecideOutput(BaseModel):
    next_phase: Phase
    halt_reason: str | None = None
    reasoning: str
    llm_call: "LLMCallRecord"
    recovery_invoked: bool = False


class AgentState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    version: int = 0
    run_id: str
    task_brief: str

    current_phase: Phase = Phase.PLAN
    step: int = 0
    started_at: datetime
    last_decision_reasoning: str = ""

    csv_loaded: bool = False
    api_loaded: bool = False
    txns_csv: list[dict] = Field(default_factory=list)
    txns_api: list[dict] = Field(default_factory=list)
    timezone_normalized: bool = False
    matches: list[dict] = Field(default_factory=list)
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    proposals: list[CorrectionProposal] = Field(default_factory=list)
    corrections_applied: int = 0

    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    consecutive_failures: int = 0
    halt_reason: str | None = None

    def is_terminal(self) -> bool:
        return self.current_phase == Phase.HALT

    def apply(self, decision: DecideOutput) -> None:
        self.version += 1
        self.step += 1
        self.current_phase = decision.next_phase
        self.last_decision_reasoning = decision.reasoning
        if decision.next_phase == Phase.HALT:
            self.halt_reason = decision.halt_reason

    def snapshot_to_disk(self, run_dir: Path) -> None:
        path = run_dir / f"step_{self.step:03d}.json"
        path.write_text(self.model_dump_json(indent=2))
