# evals/compare_baseline.py
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--max-regression", type=float, default=0.0,
                        help="Max allowed drop in pass rate vs baseline (0.0 = no regressions)")
    args = parser.parse_args(argv)

    current = json.loads(args.current.read_text())
    if not args.baseline.exists():
        print(f"Baseline {args.baseline} not found; treating as no-regression.")
        return 0 if current["summary"]["pass_rate"] == 1.0 else 1

    baseline = json.loads(args.baseline.read_text())
    cur_rate = current["summary"]["pass_rate"]
    base_rate = baseline["summary"]["pass_rate"]
    delta = cur_rate - base_rate

    print(f"Pass rate current={cur_rate:.3f} baseline={base_rate:.3f} delta={delta:+.3f}")

    if delta < -args.max_regression:
        # Identify which scenarios specifically regressed
        cur_pass = {s["name"]: s["passed"] for s in current["scenarios"]}
        base_pass = {s["name"]: s["passed"] for s in baseline["scenarios"]}
        regressed = [n for n in base_pass if base_pass[n] and not cur_pass.get(n, False)]
        print(f"REGRESSION: {len(regressed)} scenario(s) regressed:")
        for n in regressed:
            print(f"  - {n}")
        return 1

    if cur_rate < 1.0:
        print("Current run has failures (independent of baseline). Failing CI.")
        return 1

    print("OK: no regression detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
