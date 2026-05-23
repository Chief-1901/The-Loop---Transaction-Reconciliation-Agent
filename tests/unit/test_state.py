from datetime import datetime, timezone
from recon_agent.agent.state import AgentState, DecideOutput, LLMCallRecord
from recon_agent.agent.phases import Phase


def _empty_llm_call() -> LLMCallRecord:
    return LLMCallRecord(
        step=0, phase=Phase.PLAN, provider="none", model="none",
        subtask="none", tokens_in=0, tokens_out=0, latency_ms=0, cost_inr=0.0
    )


def test_apply_bumps_version_and_step():
    state = AgentState(
        run_id="r1", task_brief="test",
        started_at=datetime.now(timezone.utc),
    )
    assert state.version == 0
    assert state.step == 0
    assert state.current_phase == Phase.PLAN

    decision = DecideOutput(
        next_phase=Phase.ACT, reasoning="proceed", llm_call=_empty_llm_call()
    )
    state.apply(decision)

    assert state.version == 1
    assert state.step == 1
    assert state.current_phase == Phase.ACT
    assert state.last_decision_reasoning == "proceed"


def test_halt_sets_halt_reason():
    state = AgentState(run_id="r1", task_brief="t",
                       started_at=datetime.now(timezone.utc))
    decision = DecideOutput(
        next_phase=Phase.HALT, halt_reason="done", reasoning="finished",
        llm_call=_empty_llm_call()
    )
    state.apply(decision)
    assert state.is_terminal()
    assert state.halt_reason == "done"
