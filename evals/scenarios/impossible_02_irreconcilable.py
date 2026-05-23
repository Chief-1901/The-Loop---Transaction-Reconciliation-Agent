from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="impossible_02_irreconcilable",
    fixture_variant="irreconcilable", fixture_seed=4002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"degraded", "halted", "completed"},
        findings_by_kind={"missing_in_api": 500},
        findings_tolerance={"missing_in_api": 100, "missing_in_csv": 100},
        recovery_invoked=True, max_cost_inr=4.00,
    ),
    cassette_file=Path("evals/cassettes/impossible_02_irreconcilable.jsonl"),
)
