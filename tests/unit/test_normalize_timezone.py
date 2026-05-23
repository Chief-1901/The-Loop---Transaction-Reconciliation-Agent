from recon_agent.tools.normalize_timezone import NormalizeTimezone, NormalizeTZInput


def test_normalizes_ist_to_utc():
    recs = [{"reference_id": "TX1", "settled_at": "2026-04-22T14:13:08+05:30"}]
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=recs, timestamp_field="settled_at"))
    assert result.ok
    out = result.output.records[0]
    assert out["settled_at"].endswith("+00:00")
    assert result.output.converted_count == 1


def test_detects_ist_as_utc():
    # Same clock hour as redemption_ts (IST), but with +00:00 — suspicious
    recs = [
        {"reference_id": "TX1", "settled_at": "2026-04-22T14:13:08+00:00",
         "_csv_ts": "2026-04-22T14:13:08+05:30"},  # hint for the detector
    ]
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=recs, timestamp_field="settled_at"))
    assert result.ok
    assert "TX1" in result.output.suspected_ist_as_utc


def test_missing_field_returns_error():
    result = NormalizeTimezone().run(NormalizeTZInput(
        records=[{"a": "x"}], timestamp_field="settled_at"))
    assert not result.ok
    assert result.error.code == "MISSING_FIELD"
