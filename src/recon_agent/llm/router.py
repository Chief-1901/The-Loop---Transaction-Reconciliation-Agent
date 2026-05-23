from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..agent.phases import Phase
from ..agent.state import LLMCallRecord
from .cassettes import CassetteLayer
from .pricing import cost_inr
from .providers import RawLLMResponse, gemini_call, openai_call, LLMError


@dataclass(frozen=True)
class RouteSpec:
    provider: str   # "gemini" | "openai"
    model: str
    rationale: str


# Override via PLAN_PROVIDER=openai for the comparison eval (Phase 8)
PLAN_PROVIDER_OVERRIDE = os.environ.get("PLAN_PROVIDER")

# Allow overriding Gemini model via env var (e.g. if gemini-2.5-flash hits daily quota)
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

ROUTING_TABLE: dict[str, RouteSpec] = {
    "plan":        RouteSpec("gemini", _GEMINI_MODEL, "Cost-optimized for free-tier daily quota. Flash handles ReAct-style single-step planning with structured output reliably; Pro reserved for shadow-comparison if needed."),
    "decide":      RouteSpec("gemini", _GEMINI_MODEL, "Meta-cognition gated by structured-output schema (HALT|PLAN binary). Flash is sufficient."),
    "classify":    RouteSpec("openai", "gpt-4o-mini",  "Cheap structured classification."),
    "summary":     RouteSpec("gemini", _GEMINI_MODEL, "One call, NL only, cheap."),
    "shadow_plan": RouteSpec("openai", "gpt-4o",       "Apples-to-apples capable comparison."),
    "propose":     RouteSpec("gemini", _GEMINI_MODEL, "Per-correction LLM call; cheap."),
}


def _route_for(subtask: str) -> RouteSpec:
    if PLAN_PROVIDER_OVERRIDE == "openai":
        if subtask in ("plan", "decide", "propose"):
            return RouteSpec("openai", "gpt-4o-mini", "PLAN_PROVIDER=openai override")
    return ROUTING_TABLE[subtask]


class LLMRouter:
    def __init__(self, cassette: CassetteLayer):
        self._cassette = cassette

    def call(
        self,
        subtask: str,
        messages: list[dict],
        response_schema: type[BaseModel],
        timeout_s: float = 30.0,
        step: int = 0,
        phase: Phase = Phase.PLAN,
    ) -> tuple[BaseModel, LLMCallRecord]:
        route = _route_for(subtask)
        h = self._cassette.hash(route.provider, route.model, subtask, messages, response_schema)

        # Replay path
        if self._cassette.mode == "replay":
            raw = self._cassette.require(h)
            parsed = response_schema.model_validate_json(raw.text)
            return parsed, LLMCallRecord(
                step=step, phase=phase, provider=route.provider, model=route.model,
                subtask=subtask, tokens_in=raw.tokens_in, tokens_out=raw.tokens_out,
                latency_ms=raw.latency_ms, cost_inr=0.0, cache_hit=True,
            )

        # Live or record path
        if route.provider == "gemini":
            raw = gemini_call(route.model, messages, response_schema, timeout_s)
        elif route.provider == "openai":
            raw = openai_call(route.model, messages, response_schema, timeout_s)
        else:
            raise ValueError(f"unknown provider {route.provider}")

        parsed = response_schema.model_validate_json(raw.text)
        c = cost_inr(route.model, raw.tokens_in, raw.tokens_out)

        if self._cassette.mode == "record":
            self._cassette.put(h, raw)

        return parsed, LLMCallRecord(
            step=step, phase=phase, provider=route.provider, model=route.model,
            subtask=subtask, tokens_in=raw.tokens_in, tokens_out=raw.tokens_out,
            latency_ms=raw.latency_ms, cost_inr=c, cache_hit=False,
        )
