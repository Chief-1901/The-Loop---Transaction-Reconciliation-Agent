from unittest.mock import MagicMock
from recon_agent.tools.classify_discrepancy import (
    ClassifyDiscrepancy, ClassifyDiscrepancyInput, ClassifyDiscrepancyOutput
)
from recon_agent.agent.state import Discrepancy, LLMCallRecord
from recon_agent.agent.phases import Phase


def _mock_call_record() -> LLMCallRecord:
    return LLMCallRecord(step=0, phase=Phase.ACT, provider="openai", model="gpt-4o-mini",
                         subtask="classify", tokens_in=100, tokens_out=50,
                         latency_ms=200, cost_inr=0.01)


def test_classify_routes_unmatched_csv_to_missing_in_api():
    fake_router = MagicMock()
    fake_router.call.return_value = (
        ClassifyDiscrepancyOutput(classified=[
            Discrepancy(txn_id="T1", kind="missing_in_api",
                        csv_record={"txn_id": "T1"}, severity="medium", confidence=0.95)
        ]),
        _mock_call_record(),
    )
    tool = ClassifyDiscrepancy(router=fake_router)
    result = tool.run(ClassifyDiscrepancyInput(
        unmatched_csv=[{"txn_id": "T1"}],
        unmatched_api=[],
        value_conflicts=[],
        timezone_suspects=[],
    ))
    assert result.ok
    assert len(result.output.classified) == 1
    assert result.output.classified[0].kind == "missing_in_api"
    fake_router.call.assert_called_once()
