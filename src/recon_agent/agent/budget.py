from __future__ import annotations
from datetime import datetime, timezone

from pydantic import BaseModel

from .state import AgentState


class Budget(BaseModel):
    max_tokens: int = 100_000
    max_wall_clock_s: float = 600.0
    max_tool_calls: int = 60
    max_consecutive_failures: int = 5
    max_cost_inr: float = 50.0


class Breach(BaseModel):
    dim: str
    observed: float
    limit: float
    message: str


def check(budget: Budget, state: AgentState) -> Breach | None:
    tokens_used = sum(c.tokens_in + c.tokens_out for c in state.llm_calls)
    if tokens_used > budget.max_tokens:
        return Breach(dim="tokens", observed=tokens_used, limit=budget.max_tokens,
                      message=f"{tokens_used} tokens > {budget.max_tokens} ceiling")

    elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
    if elapsed > budget.max_wall_clock_s:
        return Breach(dim="wall_clock", observed=elapsed, limit=budget.max_wall_clock_s,
                      message=f"{elapsed:.1f}s > {budget.max_wall_clock_s}s ceiling")

    if len(state.tool_calls) > budget.max_tool_calls:
        return Breach(dim="tool_calls", observed=len(state.tool_calls),
                      limit=budget.max_tool_calls,
                      message=f"{len(state.tool_calls)} calls > {budget.max_tool_calls}")

    if state.consecutive_failures >= budget.max_consecutive_failures:
        return Breach(dim="consecutive_failures", observed=state.consecutive_failures,
                      limit=budget.max_consecutive_failures,
                      message=f"{state.consecutive_failures} consecutive failures")

    cost = sum(c.cost_inr for c in state.llm_calls) + sum(c.cost_inr for c in state.tool_calls)
    if cost > budget.max_cost_inr:
        return Breach(dim="cost", observed=cost, limit=budget.max_cost_inr,
                      message=f"₹{cost:.2f} > ₹{budget.max_cost_inr} ceiling")

    return None
