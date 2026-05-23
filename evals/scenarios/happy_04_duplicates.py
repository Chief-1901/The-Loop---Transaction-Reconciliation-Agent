from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_04_duplicates",
    fixture_variant="duplicate_only", fixture_seed=1004,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={"duplicate": 10},
        findings_tolerance={"duplicate": 3},
        recovery_invoked=False, max_cost_inr=2.50,
    ),
    cassette_file=Path("evals/cassettes/happy_04_duplicates.jsonl"),
)
