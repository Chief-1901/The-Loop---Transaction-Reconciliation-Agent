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

# Allow overriding Gemini model via env var (e.g. to test against gemini-2.5-flash)
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

ROUTING_TABLE: dict[str, RouteSpec] = {
    "plan":        RouteSpec("gemini", _GEMINI_MODEL, "gemini-2.5-flash-lite: cheapest tier in the Flash family. Generous free-tier quota for high-volume agent workloads. Structured-output reliability is sufficient for ReAct's constrained single-step planning."),
    "decide":      RouteSpec("gemini", _GEMINI_MODEL, "Meta-cognition gated by binary HALT|PLAN schema. flash-lite is sufficient; in-family with plan amortizes the Gemini client."),
    "classify":    RouteSpec("openai", "gpt-4o-mini",  "Cheap structured classification. OpenAI's json_schema strict mode is the most reliable for high-volume enum tagging."),
    "summary":     RouteSpec("gemini", _GEMINI_MODEL, "One call at end of run, natural-language only. In-family with plan/decide."),
    "shadow_plan": RouteSpec("openai", "gpt-4o",       "Capable-tier comparison vs Gemini flash-lite on Plan. Only invoked when --shadow flag is set."),
    "propose":     RouteSpec("gemini", _GEMINI_MODEL, "Per-correction LLM call. flash-lite handles the per-discrepancy proposal schema; in-family with plan/decide."),
}


def _route_for(subtask: str) -> RouteSpec:
    if subtask == "plan" and PLAN_PROVIDER_OVERRIDE == "openai":
        return RouteSpec("openai", "gpt-4o", "PLAN_PROVIDER override for comparison eval")
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
