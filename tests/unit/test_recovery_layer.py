# tests/unit/test_recovery_layer.py
from datetime import datetime, timezone
from recon_agent.recovery import RecoveryLayer
from recon_agent.agent.state import AgentState
from recon_agent.tools.base import ToolError
from recon_agent.agent.phases import ActOutput
from recon_agent.agent.state import ToolCallRecord

# ActOutput uses a forward-reference string annotation for ToolCallRecord
# (imported only under TYPE_CHECKING in phases.py), so we must rebuild the
# model now that the real class is available in the module namespace.
ActOutput.model_rebuild()


def _state(failures: int = 0) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc),
                      consecutive_failures=failures)


def _act() -> ActOutput:
    return ActOutput(
        tool_name="x", tool_input={},
        raw_record=ToolCallRecord(
            step=1, tool_name="x", args={},
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            latency_ms=10, outcome="error",
        )
    )


def test_404_replans():
    layer = RecoveryLayer()
    err = ToolError(kind="persistent", code="API_NOT_FOUND", message="404", retriable=False)
    decision = layer.handle(err, _state(), _act(), tools=None)
    assert decision.kind == "replan"
    assert decision.hint


def test_3_consecutive_failures_degrade():
    layer = RecoveryLayer()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    decision = layer.handle(err, _state(failures=3), _act(), tools=None)
    assert decision.kind == "degrade"
