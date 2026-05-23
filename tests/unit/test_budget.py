from datetime import datetime, timedelta, timezone
from recon_agent.agent.budget import Budget, check
from recon_agent.agent.state import AgentState, LLMCallRecord, ToolCallRecord
from recon_agent.agent.phases import Phase


def _state(**kw) -> AgentState:
    return AgentState(run_id="r", task_brief="t",
                      started_at=datetime.now(timezone.utc), **kw)


def test_budget_default_values():
    b = Budget()
    assert b.max_tokens == 100_000
    assert b.max_wall_clock_s == 600.0
    assert b.max_tool_calls == 60
    assert b.max_consecutive_failures == 5
    assert b.max_cost_inr == 50.0


def test_check_returns_none_when_under_limits():
    b = Budget()
    s = _state()
    assert check(b, s) is None


def test_check_detects_token_breach():
    b = Budget(max_tokens=100)
    s = _state()
    s.llm_calls.append(LLMCallRecord(
        step=1, phase=Phase.PLAN, provider="g", model="g", subtask="p",
        tokens_in=200, tokens_out=0, latency_ms=0, cost_inr=0
    ))
    breach = check(b, s)
    assert breach is not None
    assert breach.dim == "tokens"


def test_check_detects_consecutive_failures():
    b = Budget(max_consecutive_failures=2)
    s = _state(consecutive_failures=2)
    breach = check(b, s)
    assert breach is not None
    assert breach.dim == "consecutive_failures"
