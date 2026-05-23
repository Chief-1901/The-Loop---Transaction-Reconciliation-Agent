import tempfile
from pathlib import Path
from recon_agent.agent.loop import AgentLoop
from recon_agent.agent.budget import Budget
from recon_agent.tools.registry import ToolRegistry


def test_loop_runs_and_halts():
    ToolRegistry.discover()
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        loop = AgentLoop(
            task="smoke test",
            tools=ToolRegistry,
            budget=Budget(),
            llm_router=None,        # placeholder for Phase 1; real router lands in Phase 2
            recovery=None,
            logger=None,
            run_dir=run_dir,
        )
        report = loop.run()
        assert report is not None
        assert (run_dir / "step_000.json").exists()
        assert loop.state.is_terminal()
