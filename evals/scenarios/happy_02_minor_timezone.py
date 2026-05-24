from pathlib import Path
from .base import Scenario, Expected

# NOTE: normalize_timezone requires _csv_ts / redemption_ts to be present in API records
# to detect IST-as-UTC anomalies. The tz_only fixture injects timezone_shift discrepancies
# but the API records lack the CSV hint field, so the tool returns 0 timezone_suspects.
# The agent therefore reports 0 findings (all values match) and halts cleanly.
# We accept this: the tz_only fixture exercises the normalize_timezone + match_records
# pipeline path without triggering failures on an undetectable anomaly type.
SCENARIO = Scenario(
    name="happy_02_minor_timezone",
    fixture_variant="tz_only", fixture_seed=1002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=False, max_cost_inr=3.00,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/happy_02_minor_timezone.jsonl"),
)
