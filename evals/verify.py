# evals/verify.py
from __future__ import annotations
import json
from pathlib import Path

from evals.scenarios.base import Scenario, ScenarioResult


def verify_scenario(
    scenario: Scenario,
    run_dir: Path,
    gt: dict,
) -> ScenarioResult:
    """Five orthogonal checks. Pass ⟺ all five pass."""
    failures: list[str] = []

    # Load run artifacts
    report_path = run_dir / "report.json"
    if not report_path.exists():
        return ScenarioResult(
            name=scenario.name, passed=False,
            failures=[f"report.json missing in {run_dir}"],
        )
    report = json.loads(report_path.read_text())
    ledger_path = run_dir / "corrections.jsonl"
    ledger: list[dict] = []
    if ledger_path.exists():
        ledger = [json.loads(l) for l in ledger_path.open() if l.strip()]
    log_path = run_dir / "log.jsonl"
    log_lines: list[dict] = []
    if log_path.exists():
        log_lines = [json.loads(l) for l in log_path.open() if l.strip()]

    # 1. Status check
    status = report.get("status")
    if status not in scenario.expected.status:
        failures.append(f"status={status} not in expected {scenario.expected.status}")

    # 2. Discrepancy count check (with tolerance)
    found_by_kind = report.get("findings_by_kind", {})
    for kind, expected_count in scenario.expected.findings_by_kind.items():
        actual = found_by_kind.get(kind, 0)
        tol = scenario.expected.findings_tolerance.get(kind, 1)
        if abs(actual - expected_count) > tol:
            failures.append(f"findings[{kind}]={actual} not within ±{tol} of {expected_count}")

    # 3. Correction coverage
    applied_ids = {row["txn_id"] for row in ledger if row.get("action") == "applied"}
    expected_ids = {d["txn_id"] for d in gt.get("injected", [])
                    if d["kind"] not in ("missing_in_csv",)}  # missing_in_csv only flagged
    coverage = len(applied_ids & expected_ids) / max(1, len(expected_ids))
    if coverage < scenario.expected.min_correction_coverage \
            and scenario.expected.findings_by_kind:
        if "budget" not in scenario.name and "impossible" not in scenario.name:
            failures.append(
                f"correction coverage={coverage:.2f} < "
                f"{scenario.expected.min_correction_coverage}"
            )

    # 4. Recovery-invoked check (look for the event in log.jsonl)
    recovery_invoked = any(
        line.get("event") == "recovery.dispatched" for line in log_lines
    )
    if recovery_invoked != scenario.expected.recovery_invoked:
        failures.append(
            f"recovery_invoked={recovery_invoked} (expected {scenario.expected.recovery_invoked})"
        )

    # 5. Cost check
    cost = report.get("telemetry", {}).get("total_cost_inr", 0.0)
    if cost > scenario.expected.max_cost_inr:
        failures.append(f"cost ₹{cost:.2f} > max ₹{scenario.expected.max_cost_inr}")

    # 6. Halt reason substring (if specified)
    if scenario.expected.halt_reason_contains:
        halt_reason = report.get("halt_reason") or ""
        if scenario.expected.halt_reason_contains not in halt_reason:
            failures.append(
                f"halt_reason='{halt_reason}' missing "
                f"'{scenario.expected.halt_reason_contains}'"
            )

    return ScenarioResult(
        name=scenario.name,
        passed=len(failures) == 0,
        status=status,
        findings_by_kind=found_by_kind,
        recovery_invoked=recovery_invoked,
        cost_inr=cost,
        failures=failures,
    )
