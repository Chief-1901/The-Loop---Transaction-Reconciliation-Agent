from unittest.mock import MagicMock
from recon_agent.tools.propose_correction import (
    ProposeCorrection, ProposeCorrectionInput, ProposeCorrectionOutput
)
from recon_agent.agent.state import Discrepancy, CorrectionProposal, LLMCallRecord
from recon_agent.agent.phases import Phase


def test_propose_value_mismatch():
    fake_router = MagicMock()
    fake_router.call.return_value = (
        ProposeCorrectionOutput(
            proposal=CorrectionProposal(
                txn_id="T1", field="gross_amount", old_value=110.0, new_value=100.0,
                reason="rounding to nearest rupee", confidence=0.95,
            ),
            fallback=None,
        ),
        LLMCallRecord(step=0, phase=Phase.ACT, provider="gemini", model="gemini-2.5-flash",
                      subtask="propose", tokens_in=100, tokens_out=50, latency_ms=200, cost_inr=0.01),
    )
    tool = ProposeCorrection(router=fake_router)
    result = tool.run(ProposeCorrectionInput(
        discrepancy=Discrepancy(txn_id="T1", kind="value_mismatch")))
    assert result.ok
    assert result.output.proposal.new_value == 100.0
