import json
from recon_agent.tools.apply_correction import ApplyCorrection, ApplyCorrectionInput
from recon_agent.agent.state import CorrectionProposal


def test_applies_high_confidence(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    proposal = CorrectionProposal(
        txn_id="T1", field="gross_amount", old_value=110.0,
        new_value=100.0, reason="rounding", confidence=0.95)
    result = ApplyCorrection().run(ApplyCorrectionInput(
        proposal=proposal, ledger_path=str(ledger)))
    assert result.ok
    assert result.output.skipped_reason is None
    line = json.loads(ledger.read_text().strip())
    assert line["txn_id"] == "T1"
    assert line["action"] == "applied"
    assert line["new"] == 100.0


def test_skips_low_confidence(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    proposal = CorrectionProposal(
        txn_id="T2", field="merchant", old_value="x", new_value="y",
        reason="guess", confidence=0.5)
    result = ApplyCorrection().run(ApplyCorrectionInput(
        proposal=proposal, ledger_path=str(ledger)))
    assert result.ok
    assert result.output.skipped_reason == "low_confidence"
    line = json.loads(ledger.read_text().strip())
    assert line["action"] == "skipped"
