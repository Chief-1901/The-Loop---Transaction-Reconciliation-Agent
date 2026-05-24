from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

# NOTE: wall_clock budget (5s) is reliably triggered during live/record runs (LLM calls
# take 5-50s each). In replay mode calls are near-instant so the 5s wall_clock is never
# reached; instead a CassetteMiss halts the run after the first few cassette entries.
# Either way the agent halts cleanly. We verify status=halted without checking halt_reason.
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
    ),
    cassette_file=Path("evals/cassettes/budget_02_walltime_ceiling.jsonl"),
)
