import json
from pathlib import Path
from recon_agent.tools.verify_reconciliation import VerifyReconciliation, VerifyInput


def test_verify_with_ledger(tmp_path):
    ledger = tmp_path / "corrections.jsonl"
    ledger.write_text(json.dumps(
        {"txn_id": "T1", "action": "applied", "kind": "value_mismatch"}) + "\n")
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"},
           {"txn_id": "T2", "order_value_inr": "50.0"}]
    api = [{"reference_id": "T1", "gross_amount": 100.0},
           {"reference_id": "T2", "gross_amount": 60.0}]   # T2 has value mismatch
    result = VerifyReconciliation().run(VerifyInput(
        csv_records=csv, api_records=api, ledger_path=str(ledger)))
    assert result.ok
    assert len(result.output.residual_discrepancies) == 1
    assert result.output.residual_discrepancies[0].txn_id == "T2"
