import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from recon_agent.agent.budget import Budget
from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.phases import Phase, PlanOutput
from recon_agent.agent.state import DecideOutput, LLMCallRecord
from recon_agent.tools.registry import ToolRegistry


def _fake_llm_call(subtask: str) -> LLMCallRecord:
    return LLMCallRecord(
        step=0, phase=Phase.PLAN, provider="fake", model="fake",
        subtask=subtask, tokens_in=10, tokens_out=5,
        latency_ms=10, cost_inr=0.0
    )


def test_loop_runs_and_halts():
    """AgentLoop with a mock router should plan, attempt tool, and exit cleanly."""
    ToolRegistry.discover(force=True)

    fake_router = MagicMock()
    call_count = {"n": 0}

    def fake_call(subtask, messages, schema, **kw):
        call_count["n"] += 1
        if subtask == "plan":
            return PlanOutput(intended_tool="load_csv",
                              tool_args={"path": "/nonexistent/path.csv"},
                              reasoning="test"), _fake_llm_call("plan")
        if subtask == "decide":
            # halt after 2 iterations
            next_phase = Phase.HALT if call_count["n"] > 4 else Phase.PLAN
            return DecideOutput(next_phase=next_phase,
                                halt_reason="test complete" if next_phase == Phase.HALT else None,
                                reasoning="test",
                                llm_call=_fake_llm_call("decide")), \
                   _fake_llm_call("decide")
        raise ValueError(f"unexpected subtask {subtask}")

    fake_router.call.side_effect = fake_call

    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        loop = AgentLoop(
            task="smoke test",
            tools=ToolRegistry,
            budget=Budget(max_consecutive_failures=10),  # tolerate the FILE_NOT_FOUND errors
            llm_router=fake_router,
            run_dir=run_dir,
        )
        report = loop.run()
        assert report is not None
        assert (run_dir / "step_000.json").exists()
        assert loop.state.is_terminal()
