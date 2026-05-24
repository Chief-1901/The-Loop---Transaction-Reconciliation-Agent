# evals/runner.py
from __future__ import annotations
import argparse
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from evals.scenarios.base import Scenario, ScenarioResult
from evals.verify import verify_scenario


def discover_scenarios() -> list[Scenario]:
    pkg_dir = Path("evals/scenarios")
    scenarios = []
    for p in sorted(pkg_dir.glob("*.py")):
        if p.name in ("__init__.py", "base.py"):
            continue
        mod = importlib.import_module(f"evals.scenarios.{p.stem}")
        if hasattr(mod, "SCENARIO"):
            scenarios.append(mod.SCENARIO)
    return scenarios


def run_one(scenario: Scenario, llm_mode: str, out_root: Path,
            enable_dashboard: bool = False, slow_ms: int = 0) -> ScenarioResult:
    from recon_agent.agent.budget import Budget
    from recon_agent.agent.loop import AgentLoop
    from recon_agent.data.generate_fixtures import generate_fixtures
    from recon_agent.llm.cassettes import CassetteLayer
    from recon_agent.llm.router import LLMRouter
    from recon_agent.recovery import RecoveryLayer
    from recon_agent.tools.registry import ToolRegistry

    started = time.time()
    run_dir = out_root / scenario.name
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply env overrides
    saved_env = {k: os.environ.get(k) for k in scenario.cli_env}
    for k, v in scenario.cli_env.items():
        os.environ[k] = v
    os.environ["FIXTURE_DIR"] = str(Path("src/recon_agent/data/fixtures"))

    try:
        # 2. Generate fixtures for this scenario's variant
        gt_obj = generate_fixtures(
            seed=scenario.fixture_seed, n_txns=500,
            variant=scenario.fixture_variant,
            out_dir=Path("src/recon_agent/data/fixtures"),
        )
        gt_path = Path(f"src/recon_agent/data/ground_truth_{scenario.fixture_variant}.json")
        gt = json.loads(gt_path.read_text())

        # 3. Set up agent
        cassette_path = scenario.cassette_file or run_dir / "cassette.jsonl"
        cassette = CassetteLayer(mode=llm_mode, path=cassette_path)
        router = LLMRouter(cassette)

        ToolRegistry.discover(force=True)

        # Budget overrides
        b_args = {}
        if scenario.budget_overrides:
            b_args = {k: v for k, v in scenario.budget_overrides.model_dump().items()
                      if v is not None}
        budget = Budget(**b_args)

        # Minimal JSONL logger so verify.py can detect recovery.dispatched events
        log_path = run_dir / "log.jsonl"

        class _JsonlLogger:
            def info(self, event: str, **kwargs):
                import json as _json
                with open(log_path, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps({"event": event, **kwargs}) + "\n")

        _logger = _JsonlLogger()
        recovery = RecoveryLayer(logger=_logger)
        # Slow-mode wraps the router to inject sleep between calls (for Loom recording visibility)
        if slow_ms > 0:
            _original_call = router.call
            def _slow_call(*args, **kwargs):
                time.sleep(slow_ms / 1000.0)
                return _original_call(*args, **kwargs)
            router.call = _slow_call

        loop = AgentLoop(
            task="Reconcile CSV vs PayU API. Apply corrections to ledger.",
            tools=ToolRegistry,
            budget=budget,
            llm_router=router,
            recovery=recovery,
            run_dir=run_dir,
            enable_dashboard=enable_dashboard,
            max_iterations=40,
        )
        try:
            loop.run()
        except Exception:
            traceback.print_exc()

    finally:
        # Restore env
        for k, prev in saved_env.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev

    result = verify_scenario(scenario, run_dir, gt)
    result.duration_s = round(time.time() - started, 2)
    return result


def write_results(results: list[ScenarioResult], out_dir: Path, llm_mode: str,
                  json_path: Path | None = None) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    md_lines = [
        f"# Eval Run · {datetime.now(timezone.utc).isoformat()}",
        f"**Mode:** {llm_mode} · **Total:** {total} · **Pass:** {passed}/{total}",
        "",
        "| # | Scenario | Status | Findings | Recovery | Cost INR | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        f_summary = ",".join(f"{k}={v}" for k, v in r.findings_by_kind.items()) or "-"
        verdict = "PASS" if r.passed else "FAIL"
        md_lines.append(
            f"| {i} | {r.name} | {r.status} | {f_summary} | "
            f"{'yes' if r.recovery_invoked else 'no'} | {r.cost_inr:.2f} | {verdict} |"
        )

    md_lines.append("")
    for r in results:
        if not r.passed:
            md_lines.append(f"## FAIL {r.name}")
            for f in r.failures:
                md_lines.append(f"- {f}")
            md_lines.append("")

    (out_dir / "results.md").write_text("\n".join(md_lines), encoding="utf-8")
    payload = {
        "summary": {
            "total": total, "passed": passed,
            "pass_rate": passed / total if total else 0,
            "failures": [{"name": r.name, "reason": "; ".join(r.failures)}
                         for r in results if not r.passed],
        },
        "scenarios": [r.model_dump() for r in results],
    }
    target = json_path or (out_dir / "results.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-mode", choices=["live", "record", "replay"],
                        default=os.environ.get("LLM_MODE", "replay"))
    parser.add_argument("--scenario", action="append", default=None,
                        help="Run only these scenarios (repeatable). Default: all.")
    parser.add_argument("--tag", default=None,
                        help="Suffix on the output dir name (used for comparison runs).")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--dashboard", action="store_true",
                        help="Show the Rich live dashboard during each scenario "
                             "(useful for Loom recording; default off for CI).")
    parser.add_argument("--slow-ms", type=int, default=0,
                        help="Inject N ms of sleep between LLM calls (Loom-recording aid; "
                             "default 0 = full speed).")
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_{args.tag}" if args.tag else ""
    out_root = Path(f"reports/eval_{ts}{suffix}")
    out_root.mkdir(parents=True, exist_ok=True)

    scenarios = discover_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s.name in args.scenario]

    results: list[ScenarioResult] = []
    for s in scenarios:
        print(f"-- {s.name} ...", end="", flush=True)
        result = run_one(s, args.llm_mode, out_root,
                         enable_dashboard=args.dashboard,
                         slow_ms=args.slow_ms)
        results.append(result)
        marker = "PASS" if result.passed else "FAIL"
        print(f" {marker} ({result.duration_s}s)")

    write_results(results, out_root, args.llm_mode, args.output_json)

    passed = sum(1 for r in results if r.passed)
    print(f"\nResult: {passed}/{len(results)} PASS in {out_root}/results.md")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
