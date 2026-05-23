from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_05_value_mismatch",
    fixture_variant="value_only", fixture_seed=1005,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={"value_mismatch": 15},
        findings_tolerance={"value_mismatch": 3},
        recovery_invoked=False, max_cost_inr=3.50,
    ),
    cassette_file=Path("evals/cassettes/happy_05_value_mismatch.jsonl"),
)
