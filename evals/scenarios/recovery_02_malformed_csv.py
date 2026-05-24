from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

# NOTE: default_latin1_csv has the same 6 discrepancy types as default, but the CSV
# is written in Latin-1 encoding. chardet may detect it as UTF-8 (80% confidence)
# and succeed in loading. If it does, the agent completes normally. If chardet fails,
# recovery kicks in. Either way, only value_mismatch + missing pairs are detectable.
# timezone_shift/duplicate/encoding_corruption remain undetectable by the pipeline.
SCENARIO = Scenario(
    name="recovery_02_malformed_csv",
    fixture_variant="default_latin1_csv", fixture_seed=2002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_wall_clock_s=1800.0),
    expected=Expected(
        status={"completed", "halted", "degraded"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=False, max_cost_inr=10.00,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/recovery_02_malformed_csv.jsonl"),
)
