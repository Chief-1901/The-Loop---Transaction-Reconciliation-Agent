from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_03_encoding",
    fixture_variant="encoding_only", fixture_seed=1003,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={"encoding_corruption": 5},
        findings_tolerance={"encoding_corruption": 3},
        recovery_invoked=False, max_cost_inr=2.50,
    ),
    cassette_file=Path("evals/cassettes/happy_03_encoding.jsonl"),
)
