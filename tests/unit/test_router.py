from __future__ import annotations
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from recon_agent.llm.router import (
    ROUTING_TABLE,
    RouteSpec,
    _route_for,
    LLMRouter,
)
from recon_agent.llm.cassettes import CassetteLayer
from recon_agent.llm.providers import RawLLMResponse
from recon_agent.agent.phases import Phase


# ---------------------------------------------------------------------------
# Routing table contents
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {"plan", "decide", "classify", "summary", "shadow_plan", "propose"}


def test_routing_table_has_all_keys():
    assert set(ROUTING_TABLE.keys()) == EXPECTED_KEYS


def test_routing_table_providers_are_valid():
    for key, spec in ROUTING_TABLE.items():
        assert spec.provider in ("gemini", "openai"), f"{key}: unknown provider {spec.provider}"


def test_routing_table_models_non_empty():
    for key, spec in ROUTING_TABLE.items():
        assert spec.model, f"{key}: model is empty"


def test_plan_uses_gemini_by_default():
    spec = _route_for("plan")
    assert spec.provider == "gemini"
    assert "gemini-2.5-pro" in spec.model


def test_classify_uses_openai_mini():
    spec = _route_for("classify")
    assert spec.provider == "openai"
    assert spec.model == "gpt-4o-mini"


def test_shadow_plan_uses_gpt4o():
    spec = _route_for("shadow_plan")
    assert spec.provider == "openai"
    assert spec.model == "gpt-4o"


# ---------------------------------------------------------------------------
# PLAN_PROVIDER override
# ---------------------------------------------------------------------------

def test_plan_provider_override_switches_to_openai(monkeypatch):
    monkeypatch.setenv("PLAN_PROVIDER", "openai")
    # Reload module so the module-level PLAN_PROVIDER_OVERRIDE re-reads env
    import recon_agent.llm.router as router_mod
    importlib.reload(router_mod)
    try:
        spec = router_mod._route_for("plan")
        assert spec.provider == "openai"
        assert spec.model == "gpt-4o"
    finally:
        monkeypatch.delenv("PLAN_PROVIDER", raising=False)
        importlib.reload(router_mod)


def test_plan_provider_override_does_not_affect_other_subtasks(monkeypatch):
    monkeypatch.setenv("PLAN_PROVIDER", "openai")
    import recon_agent.llm.router as router_mod
    importlib.reload(router_mod)
    try:
        spec = router_mod._route_for("decide")
        assert spec.provider == "gemini"
    finally:
        monkeypatch.delenv("PLAN_PROVIDER", raising=False)
        importlib.reload(router_mod)


# ---------------------------------------------------------------------------
# LLMRouter.call — replay path
# ---------------------------------------------------------------------------

class _Schema(BaseModel):
    value: str


def test_router_call_replay_returns_parsed_and_record(tmp_path):
    """Use 'summary' subtask (gemini/gemini-2.5-flash) — no env-override risk."""
    route_summary = ROUTING_TABLE["summary"]  # gemini / gemini-2.5-flash
    path = tmp_path / "cassette.jsonl"
    # Seed cassette
    rec_layer = CassetteLayer(mode="record", path=path)
    msgs = [{"role": "user", "content": "hello"}]
    raw = RawLLMResponse(text='{"value":"ok"}', tokens_in=5, tokens_out=3, latency_ms=42)
    h = rec_layer.hash(route_summary.provider, route_summary.model, "summary", msgs, _Schema)
    rec_layer.put(h, raw)

    # Replay
    rep_layer = CassetteLayer(mode="replay", path=path)
    router = LLMRouter(cassette=rep_layer)
    parsed, record = router.call("summary", msgs, _Schema, step=1, phase=Phase.PLAN)

    assert parsed.value == "ok"
    assert record.cache_hit is True
    assert record.cost_inr == 0.0
    assert record.tokens_in == 5
    assert record.tokens_out == 3
    assert record.latency_ms == 42
    assert record.provider == route_summary.provider
    assert record.model == route_summary.model
    assert record.step == 1
    assert record.phase == Phase.PLAN


def test_router_call_replay_raises_cassette_miss(tmp_path):
    from recon_agent.llm.cassettes import CassetteMiss
    path = tmp_path / "empty.jsonl"
    rep_layer = CassetteLayer(mode="replay", path=path)
    router = LLMRouter(cassette=rep_layer)
    with pytest.raises(CassetteMiss):
        router.call("summary", [{"role": "user", "content": "x"}], _Schema)


def test_router_call_live_does_not_write_to_cassette(tmp_path):
    """In live mode, put() is never called even if the provider call succeeds.
    Uses 'summary' (gemini) so gemini_call patch works cleanly."""
    path = tmp_path / "live.jsonl"
    live_layer = CassetteLayer(mode="live", path=path)
    router = LLMRouter(cassette=live_layer)

    fake_raw = RawLLMResponse(text='{"value":"live"}', tokens_in=10, tokens_out=4, latency_ms=99)

    with patch("recon_agent.llm.router.gemini_call", return_value=fake_raw):
        parsed, record = router.call("summary", [{"role": "user", "content": "hi"}], _Schema)

    assert parsed.value == "live"
    assert record.cache_hit is False
    assert not path.exists(), "cassette file must NOT be written in live mode"


def test_router_call_record_writes_cassette(tmp_path):
    """Uses 'summary' (gemini) so gemini_call patch works cleanly."""
    path = tmp_path / "record.jsonl"
    rec_layer = CassetteLayer(mode="record", path=path)
    router = LLMRouter(cassette=rec_layer)

    fake_raw = RawLLMResponse(text='{"value":"recorded"}', tokens_in=7, tokens_out=2, latency_ms=55)

    with patch("recon_agent.llm.router.gemini_call", return_value=fake_raw):
        parsed, record = router.call("summary", [{"role": "user", "content": "hi"}], _Schema)

    assert parsed.value == "recorded"
    assert record.cache_hit is False
    assert path.exists(), "cassette file MUST be written in record mode"
