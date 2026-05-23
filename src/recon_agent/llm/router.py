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
from .providers import RawLLMResponse, gemini_call, openai_call, openrouter_call, LLMError


@dataclass(frozen=True)
class RouteSpec:
    provider: str   # "gemini" | "openai"
    model: str
    rationale: str


# Override via PLAN_PROVIDER=openai for the comparison eval (Phase 8)
PLAN_PROVIDER_OVERRIDE = os.environ.get("PLAN_PROVIDER")

# Allow overriding Gemini model via env var (e.g. to test against gemini-2.5-flash)
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Default OpenRouter free model — override via OPENROUTER_MODEL env var if needed
_OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")

ROUTING_TABLE: dict[str, RouteSpec] = {
    "plan":        RouteSpec("openrouter", _OPENROUTER_MODEL, "gpt-oss-120b via OpenRouter free tier. Native structured-output + function-calling support. 200 req/day free quota sufficient for cassette + demo workload."),
    "decide":      RouteSpec("openrouter", _OPENROUTER_MODEL, "Binary HALT|PLAN meta-decision; same model as plan amortizes the OpenRouter client."),
    "classify":    RouteSpec("openai", "gpt-4o-mini",  "Cheap structured classification via OpenAI's strict json_schema mode. High-volume enum tagging where reliable schema enforcement matters."),
    "summary":     RouteSpec("openrouter", _OPENROUTER_MODEL, "One natural-language summary call at end. In-family with plan/decide."),
    "shadow_plan": RouteSpec("openai", "gpt-4o",       "Capable-tier shadow comparison vs gpt-oss-120b on Plan. Only invoked when --shadow set."),
    "propose":     RouteSpec("openrouter", _OPENROUTER_MODEL, "Per-correction LLM call; in-family with plan/decide; free tier handles per-discrepancy proposals."),
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
        elif route.provider == "openrouter":
            raw = openrouter_call(route.model, messages, response_schema, timeout_s)
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
