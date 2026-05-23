from __future__ import annotations
import argparse
from pathlib import Path

from ..agent.loop import AgentLoop
from ..agent.budget import Budget
from ..tools.registry import ToolRegistry


def add_demo_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--task", default="Reconcile CSV vs PayU API.")
    p.add_argument("--budget-tokens", type=int, default=100_000)
    p.add_argument("--budget-time", type=float, default=600.0)
    p.add_argument("--budget-calls", type=int, default=60)
    p.add_argument("--budget-fails", type=int, default=5)
    p.add_argument("--budget-cost", type=float, default=50.0)
    p.add_argument("--run-dir", type=Path, default=None)


def run_demo(args: argparse.Namespace) -> int:
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
        run_dir=args.run_dir,
    )
    report = loop.run()
    print(f"Status: {report.status}")
    print(f"Halt reason: {report.halt_reason}")
    print(f"Steps: {report.telemetry['steps']}")
    print(f"Run dir: {loop.run_dir}")
    return 0 if report.status in ("completed", "halted") else 2
