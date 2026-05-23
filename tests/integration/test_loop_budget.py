# tests/integration/test_loop_budget.py
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timezone

from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.recovery import RecoveryLayer
from recon_agent.tools.registry import ToolRegistry
from tests.integration.test_loop_recovery import _make_fake_router


def _make_always_fetch_api_router():
    """Router that always plans fetch_api — so 100% fail rate causes consecutive failures."""
    from recon_agent.agent.phases import PlanOutput
    from recon_agent.agent.state import DecideOutput, LLMCallRecord
    from recon_agent.agent.phases import Phase

    def _rec(subtask: str) -> LLMCallRecord:
        return LLMCallRecord(
            step=0, phase=Phase.PLAN if subtask == "plan" else Phase.DECIDE,
            provider="t", model="t",
            subtask=subtask, tokens_in=10, tokens_out=5,
            latency_ms=10, cost_inr=0,
        )

    def fake_call(subtask, messages, schema, **kw):
        if subtask == "plan":
            # Always request fetch_api — this will always fail under FETCH_API_FAIL_RATE=1.0
            return PlanOutput(
                intended_tool="fetch_api",
                tool_args={"endpoint": "payu_settlements"},
                reasoning="test",
            ), _rec("plan")
        if subtask == "decide":
            # Keep going — let budget / recovery stop the loop
            return DecideOutput(
                next_phase=Phase.PLAN,
                halt_reason=None,
                reasoning="continue",
                llm_call=_rec("decide"),
            ), _rec("decide")
        raise ValueError(f"unexpected subtask {subtask}")

    router = MagicMock()
    router.call.side_effect = fake_call
    return router


def test_max_tool_calls_3_halts_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.0")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=1, n_txns=20, variant="happy_clean",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    ToolRegistry.discover(force=True)
    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_tool_calls=3),
        llm_router=_make_fake_router(),
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    assert report.halt_reason.startswith("budget breach")
    assert (tmp_path / "PARTIAL_REPORT.md").exists()


def test_max_consecutive_failures_halts(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "1.0")    # always fail
    monkeypatch.setenv("FETCH_API_RNG_SEED", "1")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=1, n_txns=20, variant="happy_clean",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    ToolRegistry.discover(force=True)
    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_consecutive_failures=3, max_tool_calls=30),
        llm_router=_make_always_fetch_api_router(),
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    # Either budget catches it OR recovery degrades — both are clean exits
    assert report.halt_reason is not None
    assert "budget breach" in report.halt_reason or "graceful degrade" in report.halt_reason
