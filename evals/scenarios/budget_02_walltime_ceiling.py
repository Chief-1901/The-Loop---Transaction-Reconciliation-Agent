from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

SCENARIO = Scenario(
    name="budget_02_walltime_ceiling",
    fixture_variant="default", fixture_seed=3002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_wall_clock_s=5.0),
    expected=Expected(
        status={"halted"}, findings_by_kind={},
        findings_tolerance={k: 100 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=False, max_cost_inr=1.00,
        halt_reason_contains="budget breach: wall_clock",
    ),
    cassette_file=Path("evals/cassettes/budget_02_walltime_ceiling.jsonl"),
)
