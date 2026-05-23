# tests/unit/test_compare_baseline.py
import json
from pathlib import Path

from evals.compare_baseline import main


def _write_results(path: Path, scenarios: list[tuple[str, bool]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pass_rate = sum(1 for _, p in scenarios if p) / max(1, len(scenarios))
    failures = [{"name": n, "reason": "x"} for n, p in scenarios if not p]
    payload = {
        "summary": {
            "total": len(scenarios),
            "passed": sum(1 for _, p in scenarios if p),
            "pass_rate": pass_rate,
            "failures": failures,
        },
        "scenarios": [{"name": n, "passed": p} for n, p in scenarios],
    }
    path.write_text(json.dumps(payload))


def test_baseline_missing_and_current_perfect_passes(tmp_path):
    cur = tmp_path / "current.json"
    base = tmp_path / "baseline.json"
    _write_results(cur, [("s1", True), ("s2", True)])
    # baseline doesn't exist
    assert main(["--current", str(cur), "--baseline", str(base)]) == 0


def test_baseline_missing_and_current_has_failures_fails(tmp_path):
    cur = tmp_path / "current.json"
    base = tmp_path / "baseline.json"
    _write_results(cur, [("s1", True), ("s2", False)])
    assert main(["--current", str(cur), "--baseline", str(base)]) == 1


def test_regression_detected(tmp_path):
    cur = tmp_path / "current.json"
    base = tmp_path / "baseline.json"
    _write_results(base, [("s1", True), ("s2", True)])     # baseline 2/2
    _write_results(cur, [("s1", True), ("s2", False)])     # current 1/2
    assert main(["--current", str(cur), "--baseline", str(base)]) == 1


def test_no_regression_passes(tmp_path):
    cur = tmp_path / "current.json"
    base = tmp_path / "baseline.json"
    _write_results(base, [("s1", True), ("s2", True)])
    _write_results(cur, [("s1", True), ("s2", True)])
    assert main(["--current", str(cur), "--baseline", str(base)]) == 0
