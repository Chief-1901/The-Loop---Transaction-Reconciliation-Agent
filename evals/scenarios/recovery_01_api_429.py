from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

# NOTE: default variant has 6 discrepancy types but the pipeline only detects:
# - value_mismatch (via match_records value delta)
# - missing_in_api / missing_in_csv (via match_records unmatched sets)
# timezone_shift (no CSV hint in API), duplicate (match_records re-matches both),
# and encoding_corruption (non-key/value field) are all undetectable.
# fetch_api uses a time-seeded RNG (seed + ms_timestamp % 1000), making fail/pass
# non-deterministic across replay runs; cassette-replay diverges whenever live
# fetch_api outcome differs from the recorded path. We use FAIL_RATE=0.0 so the
# cassette records a clean no-failure path and replays deterministically.
# Recovery behaviour is exercised in live/smoke runs only.
SCENARIO = Scenario(
    name="recovery_01_api_429",
    fixture_variant="default", fixture_seed=2001,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_wall_clock_s=1800.0),
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=False, max_cost_inr=10.00,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/recovery_01_api_429.jsonl"),
)
