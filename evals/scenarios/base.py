# evals/scenarios/base.py
from __future__ import annotations
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ToolOverride(BaseModel):
    name: str
    action: Literal["disable", "force_fail"]
    error_code: str | None = None


class BudgetOverride(BaseModel):
    max_tokens: int | None = None
    max_wall_clock_s: float | None = None
    max_tool_calls: int | None = None
    max_consecutive_failures: int | None = None
    max_cost_inr: float | None = None


class Expected(BaseModel):
    status: set[Literal["completed", "halted", "degraded"]]
    findings_by_kind: dict[str, int] = Field(default_factory=dict)
    findings_tolerance: dict[str, int] = Field(default_factory=dict)
    recovery_invoked: bool = False
    min_correction_coverage: float = 0.85
    max_cost_inr: float = 10.0
    halt_reason_contains: str | None = None


class Scenario(BaseModel):
    name: str
    fixture_variant: str
    fixture_seed: int = 42
    cli_env: dict[str, str] = Field(default_factory=dict)
    tool_overrides: list[ToolOverride] = Field(default_factory=list)
    budget_overrides: BudgetOverride | None = None
    expected: Expected
    cassette_file: Path | None = None
    timeout_s: int = 120


class ScenarioResult(BaseModel):
    name: str
    passed: bool
    status: str | None = None
    findings_by_kind: dict[str, int] = Field(default_factory=dict)
    recovery_invoked: bool = False
    cost_inr: float = 0.0
    duration_s: float = 0.0
    failures: list[str] = Field(default_factory=list)
