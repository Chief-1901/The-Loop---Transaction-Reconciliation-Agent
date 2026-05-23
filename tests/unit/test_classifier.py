from datetime import datetime, timezone
from recon_agent.agent.state import AgentState
from recon_agent.tools.base import ToolError
from recon_agent.recovery.classifier import ErrorClassifier, MAX_RETRIES


def _state(failures: int = 0) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc),
                      consecutive_failures=failures)


def test_transient_retries_first():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    action = c.classify(err, _state())
    assert action.kind == "retry"
    assert action.backoff_ms > 0


def test_transient_escalates_after_max_retries():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="RATE_LIMIT", message="429", retriable=True)
    # Simulate enough retries to escalate
    state = _state()
    for _ in range(MAX_RETRIES):
        c._record_retry(state, err.code)
    action = c.classify(err, state)
    assert action.kind == "replan"


def test_persistent_replans_immediately():
    c = ErrorClassifier()
    err = ToolError(kind="persistent", code="API_NOT_FOUND", message="404", retriable=False)
    action = c.classify(err, _state())
    assert action.kind == "replan"
    assert action.hint  # has a hint


def test_fatal_degrades():
    c = ErrorClassifier()
    err = ToolError(kind="fatal", code="API_AUTH", message="401", retriable=False)
    action = c.classify(err, _state())
    assert action.kind == "degrade"


def test_three_consecutive_failures_degrades():
    c = ErrorClassifier()
    err = ToolError(kind="transient", code="API_5XX", message="503", retriable=True)
    state = _state(failures=3)
    action = c.classify(err, state)
    assert action.kind == "degrade"
