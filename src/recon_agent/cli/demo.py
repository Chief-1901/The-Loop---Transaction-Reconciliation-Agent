from __future__ import annotations
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from ..agent.loop import AgentLoop
from ..agent.budget import Budget
from ..llm.cassettes import CassetteLayer
from ..llm.router import LLMRouter
from ..recovery import RecoveryLayer
from ..tools.registry import ToolRegistry


_FIXTURE_CSV = Path(__file__).parent.parent / "data" / "fixtures" / "tracking_db.csv"

_DEFAULT_TASK = (
    "Reconcile GrabOn deal-redemption transactions. "
    f"CSV file: {_FIXTURE_CSV.resolve()}. "
    "For fetch_api use endpoint=payu_settlements. "
    "Steps: load_csv (use the CSV file path above), fetch_api (endpoint=payu_settlements), "
    "normalize_timezone, match_records, "
    "classify_discrepancy, propose_correction (loop per discrepancy), "
    "apply_correction (loop per proposal), verify_reconciliation."
)


def add_demo_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--task", default=_DEFAULT_TASK)
    p.add_argument("--budget-tokens", type=int, default=100_000)
    p.add_argument("--budget-time", type=float, default=600.0)
    p.add_argument("--budget-calls", type=int, default=60)
    p.add_argument("--budget-fails", type=int, default=5)
    p.add_argument("--budget-cost", type=float, default=50.0)
    p.add_argument("--llm-mode", choices=["live", "record", "replay"], default=None)
    p.add_argument("--run-dir", type=Path, default=None)


def run_demo(args: argparse.Namespace) -> int:
    load_dotenv()
    mode = args.llm_mode or os.environ.get("LLM_MODE", "live")
    cassette = CassetteLayer(mode=mode, path=Path("reports/_demo_cassette.jsonl"))
    router = LLMRouter(cassette)

    ToolRegistry.discover()
    budget = Budget(
        max_tokens=args.budget_tokens,
        max_wall_clock_s=args.budget_time,
        max_tool_calls=args.budget_calls,
        max_consecutive_failures=args.budget_fails,
        max_cost_inr=args.budget_cost,
    )
    loop = AgentLoop(
        task=args.task,
        tools=ToolRegistry,
        budget=budget,
        llm_router=router,
        recovery=RecoveryLayer(),
        run_dir=args.run_dir,
    )
    report = loop.run()
    print(f"Status: {report.status}")
    print(f"Halt reason: {report.halt_reason}")
    print(f"Steps: {report.telemetry['steps']}")
    print(f"LLM calls: {report.telemetry['llm_calls']}")
    print(f"Total cost: INR {report.telemetry['total_cost_inr']}")
    print(f"Run dir: {loop.run_dir}")
    return 0 if report.status in ("completed", "halted") else 2
