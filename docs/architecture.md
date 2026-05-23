# Architecture

## The loop

`AgentLoop.run()` is ~70 lines. While the agent is not terminal:

1. **Budget gate** — `budget.check(state)` at the top of every iteration. Breach → write `PARTIAL_REPORT.md`, halt, exit 2.
2. **PLAN** — LLM call (Gemini 2.5 Flash) emits a `PlanOutput` with one tool call + reasoning.
3. **ACT** — `ToolRegistry.get(plan.intended_tool)` → call → typed `ToolResult`.
4. **Recovery branch (only on tool error)** — classifier dispatches to retry / replan / degrade. Loop never sees raw exceptions.
5. **OBSERVE** — summarize the tool output, patch state.
6. **DECIDE** — LLM call (Gemini 2.5 Flash) returns next phase + reasoning.
7. **`state.apply(decision)`** — bumps `version` + `step`; writes `step_<n>.json` snapshot.

The Plan/Act/Observe/Decide phases are real classes in `src/recon_agent/agent/phases.py` — not method comments inside a single loop function.

## Data flow

```
fixtures/tracking_db.csv  ──┐
                             ├──▶ load_csv ────▶ state.txns_csv ──┐
fixtures/payu_settlements.json ┘                                    │
                              └──▶ fetch_api ──▶ state.txns_api ──┤
                                                                    │
state.txns_csv + state.txns_api ──▶ normalize_timezone ─────────────┤
                                                                    │
                                  ──▶ match_records ──▶ state.matches + state.discrepancies
                                                                    │
                                  ──▶ classify_discrepancy ────────┘
                                  ──▶ propose_correction ──▶ state.proposals
                                  ──▶ apply_correction ──▶ corrections.jsonl
                                  ──▶ verify_reconciliation
```

## State versioning

Every `state.apply()` bumps `version` and writes `reports/run_<ts>/step_<n>.json`. Diff two snapshots to see exactly what one loop iteration changed.

## Why no framework

- Brief's deep-dive will ask "what's under every abstraction layer?" → "raw SDK call" is a one-line answer
- LangChain's `AgentExecutor` would obscure the loop we're being graded on
- Pydantic gives us the typed contracts we need; structlog gives us the JSONL; Rich gives us the dashboard. That's the entire dependency story.

## See also

- `docs/model_routing.md` — per-subtask provider/model choice
- `docs/recovery_strategies.md` — error-code → strategy table
- `docs/superpowers/specs/2026-05-23-recon-agent-design.md` — canonical design spec
