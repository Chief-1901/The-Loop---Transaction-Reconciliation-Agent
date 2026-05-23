from recon_agent.tools.match_records import MatchRecords, MatchRecordsInput


def test_exact_match():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T1", "gross_amount": 100.0}]
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.matched) == 1
    assert result.output.unmatched_csv == []
    assert result.output.unmatched_api == []


def test_value_mismatch_detected():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T1", "gross_amount": 110.0}]  # ₹10 off
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.value_conflicts) == 1


def test_unmatched_both_sides():
    csv = [{"txn_id": "T1", "order_value_inr": "100.0"}]
    api = [{"reference_id": "T2", "gross_amount": 200.0}]
    result = MatchRecords().run(MatchRecordsInput(csv_records=csv, api_records=api))
    assert result.ok
    assert len(result.output.unmatched_csv) == 1
    assert len(result.output.unmatched_api) == 1


def test_empty_input_returns_error():
    result = MatchRecords().run(MatchRecordsInput(csv_records=[], api_records=[]))
    assert not result.ok
    assert result.error.code == "EMPTY_INPUT"
