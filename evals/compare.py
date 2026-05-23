# evals/compare.py
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.scenarios.base import ScenarioResult
from recon_agent.llm.comparison import ComparisonReport, compare_configs


def load_results(tag: str) -> list[ScenarioResult]:
    """Find the most recent reports/eval_*_<tag>/results.json"""
    candidates = sorted(Path("reports").glob(f"eval_*_{tag}/results.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No reports/eval_*_{tag}/results.json")
    payload = json.loads(candidates[0].read_text())
    return [ScenarioResult(**r) for r in payload["scenarios"]]


def render_markdown(
    a_results: list[ScenarioResult], a_label: str,
    b_results: list[ScenarioResult], b_label: str,
    rep: ComparisonReport,
) -> str:
    lines = [
        f"# Shadow Comparison — Plan-phase model choice",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Configurations:** A = {a_label} · B = {b_label}",
        f"**Scenarios:** {rep.n} (replay mode)",
        "",
        "## Per-scenario outcomes",
        "| Scenario | A pass | B pass | A cost INR | B cost INR |",
        "|----------|--------|--------|------------|------------|",
    ]
    for a, b in zip(a_results, b_results):
        am = "PASS" if a.passed else "FAIL"
        bm = "PASS" if b.passed else "FAIL"
        lines.append(f"| {a.name} | {am} | {bm} | {a.cost_inr:.2f} | {b.cost_inr:.2f} |")

    a_cost = sum(r.cost_inr for r in a_results)
    b_cost = sum(r.cost_inr for r in b_results)
    lines.extend([
        "",
        "## Aggregate",
        f"| Config | Pass rate | Mean cost/run INR |",
        f"|--------|-----------|-------------------|",
        f"| A: {a_label} | {rep.config_a_pass*100:.1f}% | {a_cost/max(1,rep.n):.2f} |",
        f"| B: {b_label} | {rep.config_b_pass*100:.1f}% | {b_cost/max(1,rep.n):.2f} |",
        "",
        "## Statistical test (paired bootstrap, 10k resamples)",
        f"- **Observed Delta pass-rate (A - B):** {rep.observed_delta:+.3f}",
        f"- **95% CI:** [{rep.ci_lower:+.3f}, {rep.ci_upper:+.3f}]",
        f"- **p-value (two-sided):** {rep.p_value:.3f}",
        "",
        "## Verdict",
    ])
    if rep.observed_delta > 0 and rep.p_value < 0.05:
        lines.append(f"**{a_label} is statistically better than {b_label} for Plan "
                     f"(p={rep.p_value:.3f}). Keep current routing.**")
    elif rep.observed_delta < 0 and rep.p_value < 0.05:
        lines.append(f"**{b_label} appears statistically better. "
                     f"Consider switching default Plan provider.**")
    else:
        lines.append(f"No statistically significant difference at alpha=0.05 "
                     f"(p={rep.p_value:.3f}). Stick with the cheaper one ({a_label} costs "
                     f"INR {a_cost:.2f}, {b_label} costs INR {b_cost:.2f}).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_a", help="tag for config A (e.g., config_a)")
    parser.add_argument("config_b", help="tag for config B (e.g., config_b)")
    parser.add_argument("--label-a", default="Gemini 2.5 Flash")
    parser.add_argument("--label-b", default="GPT-4o")
    args = parser.parse_args(argv)

    a_results = load_results(args.config_a)
    b_results = load_results(args.config_b)
    if [r.name for r in a_results] != [r.name for r in b_results]:
        print("Scenarios differ between runs — aligning by name.", file=sys.stderr)
        b_by_name = {r.name: r for r in b_results}
        b_results = [b_by_name[r.name] for r in a_results if r.name in b_by_name]
        a_results = [r for r in a_results if r.name in b_by_name]

    rep = compare_configs(a_results, b_results)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/shadow_comparison_{ts}.md")
    out.write_text(render_markdown(a_results, args.label_a, b_results, args.label_b, rep),
                   encoding="utf-8")
    print(f"Comparison report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
