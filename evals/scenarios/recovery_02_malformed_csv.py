from pathlib import Path
from .base import Scenario, Expected

SCENARIO = Scenario(
    name="recovery_02_malformed_csv",
    fixture_variant="default_latin1_csv", fixture_seed=2002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted", "degraded"},
        findings_by_kind={
            "value_mismatch": 15, "timezone_shift": 25, "duplicate": 10,
            "missing_in_api": 10, "encoding_corruption": 5,
        },
        findings_tolerance={k: 5 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=5.00,
    ),
    cassette_file=Path("evals/cassettes/recovery_02_malformed_csv.jsonl"),
)
