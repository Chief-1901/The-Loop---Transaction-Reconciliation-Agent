# tests/unit/test_verify.py
import json
from pathlib import Path
from evals.scenarios.base import Scenario, Expected
from evals.verify import verify_scenario


def _scenario(name: str) -> Scenario:
    return Scenario(
        name=name, fixture_variant="happy_clean",
        expected=Expected(status={"completed", "halted"}, findings_by_kind={},
                          recovery_invoked=False, max_cost_inr=5.0),
    )


def test_verify_missing_report_returns_failed(tmp_path):
    result = verify_scenario(_scenario("test"), tmp_path, gt={"injected": []})
    assert not result.passed
    assert "report.json missing" in result.failures[0]


def test_verify_status_match_passes(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "halted",
        "halt_reason": None,
        "findings_by_kind": {},
        "telemetry": {"total_cost_inr": 1.0},
    }))
    result = verify_scenario(_scenario("test"), tmp_path, gt={"injected": []})
    assert result.passed, f"failed unexpectedly: {result.failures}"


def test_verify_status_mismatch_fails(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "degraded",   # not in expected set
        "halt_reason": "x",
        "findings_by_kind": {},
        "telemetry": {"total_cost_inr": 1.0},
    }))
    result = verify_scenario(_scenario("test"), tmp_path, gt={"injected": []})
    assert not result.passed
    assert "status=degraded" in result.failures[0]


def test_verify_cost_overrun_fails(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "halted",
        "halt_reason": None,
        "findings_by_kind": {},
        "telemetry": {"total_cost_inr": 99.0},  # over max_cost_inr=5
    }))
    result = verify_scenario(_scenario("test"), tmp_path, gt={"injected": []})
    assert not result.passed
    assert any("cost" in f for f in result.failures)
