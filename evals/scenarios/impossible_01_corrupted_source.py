from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="impossible_01_corrupted_source",
    fixture_variant="corrupted_source", fixture_seed=4001,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"degraded", "halted"}, findings_by_kind={},
        recovery_invoked=True, max_cost_inr=2.00,
        halt_reason_contains="degrade",
    ),
    cassette_file=Path("evals/cassettes/impossible_01_corrupted_source.jsonl"),
)
