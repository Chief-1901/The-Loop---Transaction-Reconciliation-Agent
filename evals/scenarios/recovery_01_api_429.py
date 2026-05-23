from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="recovery_01_api_429",
    fixture_variant="default", fixture_seed=2001,
    cli_env={"FETCH_API_FAIL_RATE": "0.6", "FETCH_API_RNG_SEED": "1"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={
            "value_mismatch": 15, "timezone_shift": 25, "duplicate": 10,
            "missing_in_api": 10, "missing_in_csv": 3, "encoding_corruption": 5,
        },
        findings_tolerance={k: 5 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=5.50,
    ),
    cassette_file=Path("evals/cassettes/recovery_01_api_429.jsonl"),
)
