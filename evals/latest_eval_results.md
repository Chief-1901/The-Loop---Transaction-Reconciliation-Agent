# Eval Run · 2026-05-24T14:34:00.593314+00:00
**Mode:** replay · **Total:** 12 · **Pass:** 12/12

| # | Scenario | Status | Findings | Recovery | Cost INR | Verdict |
|---|---|---|---|---|---|---|
| 1 | budget_01_token_ceiling | halted | - | no | 0.00 | PASS |
| 2 | budget_02_walltime_ceiling | halted | - | no | 0.00 | PASS |
| 3 | happy_01_clean_reconciliation | completed | - | no | 0.00 | PASS |
| 4 | happy_02_minor_timezone | completed | - | no | 0.00 | PASS |
| 5 | happy_03_encoding | completed | - | no | 0.00 | PASS |
| 6 | happy_04_duplicates | halted | - | no | 0.00 | PASS |
| 7 | happy_05_value_mismatch | halted | value_mismatch=11 | no | 0.95 | PASS |
| 8 | impossible_01_corrupted_source | degraded | - | yes | 0.00 | PASS |
| 9 | impossible_02_irreconcilable | halted | - | yes | 0.00 | PASS |
| 10 | recovery_01_api_429 | halted | missing_in_api=10,missing_in_csv=2,value_mismatch=13 | no | 0.15 | PASS |
| 11 | recovery_02_malformed_csv | halted | - | no | 0.00 | PASS |
| 12 | recovery_03_tool_disabled | degraded | - | yes | 0.00 | PASS |
