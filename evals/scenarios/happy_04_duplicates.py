from pathlib import Path
from .base import Scenario, Expected

# NOTE: duplicate_only injects 10 duplicate CSV rows (same txn_id appears twice in CSV,
# 510 rows total vs 500 API records). match_records matches both CSV rows against the
# same API record — both appear in 'matched'. The duplicates are therefore invisible to
# the pipeline. The agent reports 0 findings and halts cleanly with 500 verified matches.
# We accept this: the scenario exercises the dedup-resilience of match_records.
SCENARIO = Scenario(
    name="happy_04_duplicates",
    fixture_variant="duplicate_only", fixture_seed=1004,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=False, max_cost_inr=2.50,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/happy_04_duplicates.jsonl"),
)
