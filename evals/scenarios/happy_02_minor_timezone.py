from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="happy_02_minor_timezone",
    fixture_variant="tz_only", fixture_seed=1002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={"timezone_shift": 25},
        findings_tolerance={"timezone_shift": 3},
        recovery_invoked=False, max_cost_inr=3.00,
    ),
    cassette_file=Path("evals/cassettes/happy_02_minor_timezone.jsonl"),
)
