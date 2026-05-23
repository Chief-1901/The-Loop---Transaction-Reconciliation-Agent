# Recovery Strategies

Every `ToolError` goes through `ErrorClassifier.classify(error, state)` → one of three strategies.

## Error → strategy table

| Error code | `kind` | First strategy | If retries exhausted |
|---|---|---|---|
| `RATE_LIMIT` (HTTP 429) | transient | retry w/ exp backoff | replan ("API rate-limited") |
| `API_5XX` | transient | retry w/ exp backoff | replan |
| `API_TIMEOUT` | transient | retry once | replan |
| `API_NOT_FOUND` (404) | persistent | **replan immediately** (no retry) | — |
| `API_AUTH` (401/403) | fatal | **degrade immediately** | — |
| `MALFORMED_CSV` | persistent | replan ("try latin-1") | — |
| `FILE_NOT_FOUND` | fatal | degrade | — |
| `LLM_RATE_LIMIT` | transient | retry w/ backoff | replan |
| `LLM_TIMEOUT` | transient | retry once | replan |
| `LLM_BAD_OUTPUT` | persistent | retry once with stricter prompt | replan |
| `LEDGER_WRITE_FAILED` | fatal | degrade (data integrity) | — |
| `LOW_CONFIDENCE` | persistent | replan ("request manual review") | — |
| (any) + `consecutive_failures ≥ 3` | (any) | **degrade** | — |

## Backoff parameters

```python
MAX_RETRIES = 3
BACKOFF_BASE_MS = 1000
BACKOFF_MAX_MS = 8000
JITTER_RATIO = 0.3   # ±30%
```

`ErrorClassifier._backoff(attempt)` returns `min(BACKOFF_BASE_MS * (2 ** attempt), BACKOFF_MAX_MS)` with random ±30% jitter applied.

## What happens on each strategy

- **RetryWithBackoff**: `time.sleep(backoff_ms / 1000)`, re-run the SAME tool with the SAME args. New `ToolCallRecord` appended with `outcome="recovered"` or `outcome="error"`.
- **ReplanWithAlternativeTool**: Force the loop back to PLAN phase, with `hint` added to the Plan's next system context (so the next Plan call considers an alternative path).
- **GracefulDegrade**: Emit HALT with `halt_reason="graceful degrade: ..."`. Loop exits cleanly with `status=degraded`. Reconciliation report shows what got done.

## Why a 404 is NOT a rate limit

A 404 means the endpoint doesn't exist OR the resource is gone. Retrying won't help — we'd just hit the same 404. So 404 is `persistent` and triggers immediate replan with hint "fetch_api unreliable; proceed CSV-only".

A 429 means the server is throttling. Retrying after a backoff might succeed. So 429 is `transient` and triggers retry.

This distinction is the deep-dive question waiting to happen: "show me where 404 and 429 take different paths." The answer is at `src/recon_agent/recovery/classifier.py:classify` — and the proof is in `tests/unit/test_classifier.py::test_persistent_replans_immediately` vs `test_transient_retries_first`.

## Why repeated consecutive failures degrade

`state.consecutive_failures` is incremented every time a tool call ends in error AND recovery didn't recover it. If we hit 3 in a row, the classifier short-circuits to `degrade` regardless of the latest error's kind — because the system is clearly stuck, not having a transient bad moment.

This is what makes the "set max_consecutive_failures=3 and crank fetch_api fail rate to 100%" stress test halt cleanly instead of looping forever.
