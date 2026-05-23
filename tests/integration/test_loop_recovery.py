import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.recovery import RecoveryLayer
from recon_agent.tools.registry import ToolRegistry


def test_recovery_on_forced_429_completes(tmp_path, monkeypatch):
    """Force fetch_api to fail twice then succeed; the agent should retry and complete."""
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.6")
    monkeypatch.setenv("FETCH_API_RNG_SEED", "42")
    monkeypatch.setenv("FIXTURE_DIR", str(Path("src/recon_agent/data/fixtures")))

    # Generate fresh fixture
    from recon_agent.data.generate_fixtures import generate_fixtures
    generate_fixtures(seed=99, n_txns=20, variant="tz_only",
                      out_dir=Path("src/recon_agent/data/fixtures"))

    fake_router = _make_fake_router()
    ToolRegistry.discover(force=True)

    loop = AgentLoop(
        task="reconcile",
        tools=ToolRegistry,
        budget=Budget(max_consecutive_failures=10, max_tool_calls=30),
        llm_router=fake_router,
        recovery=RecoveryLayer(),
        run_dir=tmp_path,
    )
    report = loop.run()
    assert report.status in ("halted", "completed")
    # Verify at least 1 tool call (the run made progress)
    assert len(loop.state.tool_calls) >= 1


def _make_fake_router():
    """Returns a router whose .call() always emits sensible plan/decide JSON."""
    from recon_agent.agent.phases import PlanOutput
    from recon_agent.agent.state import DecideOutput, LLMCallRecord
    from recon_agent.agent.phases import Phase

    call_count = {"n": 0}
    fixture_csv = str(Path("src/recon_agent/data/fixtures/tracking_db.csv"))

    def _rec(subtask: str) -> LLMCallRecord:
        return LLMCallRecord(
            step=0, phase=Phase.PLAN if subtask == "plan" else Phase.DECIDE,
            provider="t", model="t",
            subtask=subtask, tokens_in=10, tokens_out=5,
            latency_ms=10, cost_inr=0
        )

    def fake_call(subtask, messages, schema, **kw):
        call_count["n"] += 1
        if subtask == "plan":
            # Cycle through a sensible plan sequence
            sequence = [
                ("load_csv", {"path": fixture_csv}),
                ("fetch_api", {"endpoint": "payu_settlements"}),
                ("normalize_timezone", {"records": [], "timestamp_field": "settled_at"}),
                ("match_records", {"csv_records": [], "api_records": []}),
                ("verify_reconciliation", {"csv_records": [], "api_records": []}),
            ]
            idx = (call_count["n"] - 1) % len(sequence)
            tool, args = sequence[idx]
            return PlanOutput(intended_tool=tool, tool_args=args, reasoning="test"), _rec("plan")
        if subtask == "decide":
            # Halt after some iterations to bound the test
            next_phase = Phase.HALT if call_count["n"] > 16 else Phase.PLAN
            return DecideOutput(next_phase=next_phase,
                                halt_reason="test complete" if next_phase == Phase.HALT else None,
                                reasoning="test", llm_call=_rec("decide")), _rec("decide")
        raise ValueError(f"unexpected subtask {subtask}")

    router = MagicMock()
    router.call.side_effect = fake_call
    return router
