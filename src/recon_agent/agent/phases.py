from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .state import AgentState, LLMCallRecord


class Phase(str, Enum):
    PLAN    = "PLAN"
    ACT     = "ACT"
    OBSERVE = "OBSERVE"
    DECIDE  = "DECIDE"
    HALT    = "HALT"


class PlanOutput(BaseModel):
    intended_tool: str
    tool_args: dict = Field(default_factory=dict)
    reasoning: str = ""
    estimated_cost_inr: float = 0.0


class Plan:
    """LLM-backed planner: emits the next tool call."""

    PROMPT_PATH = Path(__file__).parent / "prompts" / "plan_system.txt"

    def __init__(self, router: Any, tool_registry: Any, logger: Any = None):
        self._router = router
        self._registry = tool_registry
        self._system = self.PROMPT_PATH.read_text(encoding="utf-8")
        self._logger = logger

    def run(self, state: AgentState) -> tuple[PlanOutput, LLMCallRecord]:
        schemas = self._registry.schemas_for_llm()
        ctx = self._build_context(state)
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content":
                f"Available tools:\n{schemas}\n\nCurrent state:\n{ctx}\n\n"
                "Emit next action."},
        ]
        out, call = self._router.call(
            "plan", messages, PlanOutput, step=state.step, phase=Phase.PLAN
        )
        return out, call

    def _build_context(self, state: AgentState) -> str:
        return (
            f"step={state.step} csv_loaded={state.csv_loaded} "
            f"api_loaded={state.api_loaded} tz_normalized={state.timezone_normalized} "
            f"matches={len(state.matches)} discrepancies={len(state.discrepancies)} "
            f"proposals={len(state.proposals)} applied={state.corrections_applied} "
            f"last_reasoning='{state.last_decision_reasoning[:200]}'"
        )
