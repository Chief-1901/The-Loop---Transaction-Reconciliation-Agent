from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_01_clean_reconciliation",
    fixture_variant="happy_clean", fixture_seed=1001,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"}, findings_by_kind={},
        recovery_invoked=False, max_cost_inr=2.50,
    ),
    cassette_file=Path("evals/cassettes/happy_01_clean_reconciliation.jsonl"),
)
