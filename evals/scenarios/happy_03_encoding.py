from pathlib import Path
from .base import Scenario, Expected

# NOTE: encoding_corruption is injected in the CSV merchant field (non-key, non-value field).
# The match_records tool only checks txn_id (key) and order_value_inr vs gross_amount (value).
# Encoding corruption in merchant names is invisible to the standard pipeline — all 500 txns
# match cleanly by txn_id and amount. The agent reports 0 findings and halts cleanly.
# We accept this: the scenario exercises the normalize_timezone + match_records path.
SCENARIO = Scenario(
    name="happy_03_encoding",
    fixture_variant="encoding_only", fixture_seed=1003,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    expected=Expected(
        status={"completed", "halted"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=False, max_cost_inr=2.50,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/happy_03_encoding.jsonl"),
)
