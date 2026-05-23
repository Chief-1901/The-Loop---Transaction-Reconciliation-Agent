import json
from pathlib import Path
from recon_agent.tools.fetch_api import FetchAPI, FetchAPIInput, _RNG_SEED_ENV
import os


def _write_payu(tmp: Path, n: int = 10) -> None:
    payload = {"page": 1, "page_size": n, "total": n, "next_cursor": None,
               "records": [{"settlement_id": f"S{i}", "reference_id": f"TX{i}",
                            "settled_at": "2026-04-22T08:00:00+00:00", "payee": "M",
                            "gross_amount": 100.0, "net_amount": 99.0,
                            "settlement_status": "settled"} for i in range(n)]}
    (tmp / "payu_settlements.json").write_text(json.dumps(payload))


def test_fetch_returns_records(tmp_path, monkeypatch):
    _write_payu(tmp_path)
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "0.0")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert result.ok
    assert len(result.output.records) == 10


def test_fetch_with_100pct_fail_rate(tmp_path, monkeypatch):
    _write_payu(tmp_path)
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("FETCH_API_FAIL_RATE", "1.0")
    monkeypatch.setenv(_RNG_SEED_ENV, "0")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert not result.ok
    assert result.error.code == "RATE_LIMIT"
    assert result.error.kind == "transient"


def test_fetch_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_API_DISABLED", "1")
    result = FetchAPI().run(FetchAPIInput(endpoint="payu_settlements"))
    assert not result.ok
    assert result.error.code == "API_NOT_FOUND"
    assert result.error.kind == "persistent"
