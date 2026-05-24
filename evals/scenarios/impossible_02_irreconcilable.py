from pathlib import Path
from .base import Scenario, Expected, BudgetOverride

# NOTE: irreconcilable variant has all API reference_ids as "DROPPED-TX-..." so
# match_records produces 500 unmatched_csv. classify_discrepancy is called with
# 500 records — it may time out (LLM processing 500 items), causing recovery
# to be dispatched (consecutive_failures → degrade or budget breach).
# We accept any run outcome and do not require specific recovery behaviour.
SCENARIO = Scenario(
    name="impossible_02_irreconcilable",
    fixture_variant="irreconcilable", fixture_seed=4002,
    cli_env={"FETCH_API_FAIL_RATE": "0.0"},
    budget_overrides=BudgetOverride(max_tool_calls=15),
    expected=Expected(
        status={"degraded", "halted", "completed"},
        findings_by_kind={},
        findings_tolerance={},
        recovery_invoked=True, max_cost_inr=10.00,
        min_correction_coverage=0.0,
    ),
    cassette_file=Path("evals/cassettes/impossible_02_irreconcilable.jsonl"),
)
