from pathlib import Path
from .base import Scenario, Expected, ToolOverride

SCENARIO = Scenario(
    name="recovery_03_tool_disabled",
    fixture_variant="default", fixture_seed=2003,
    cli_env={"FETCH_API_DISABLED": "1"},
    tool_overrides=[ToolOverride(name="fetch_api", action="disable")],
    expected=Expected(
        status={"degraded", "halted"},
        findings_by_kind={},
        findings_tolerance={k: 50 for k in
            ["value_mismatch", "timezone_shift", "duplicate", "missing_in_api",
             "missing_in_csv", "encoding_corruption"]},
        recovery_invoked=True, max_cost_inr=4.00,
        halt_reason_contains="degrade",
    ),
    cassette_file=Path("evals/cassettes/recovery_03_tool_disabled.jsonl"),
)
