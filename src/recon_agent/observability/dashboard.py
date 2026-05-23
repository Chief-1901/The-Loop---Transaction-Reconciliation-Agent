from __future__ import annotations
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class Dashboard:
    """Wraps a `rich.live.Live` context. Call `update(state, budget)` after every step."""

    def __init__(self, console: Console | None = None, enabled: bool = True):
        self.enabled = enabled
        self.console = console or Console(stderr=True)
        self._live: Live | None = None

    def __enter__(self):
        if not self.enabled:
            return self
        self._live = Live(self._render(None, None), console=self.console,
                          refresh_per_second=4, transient=False)
        self._live.start()
        return self

    def __exit__(self, *exc):
        if self._live:
            self._live.stop()

    def update(self, state: Any, budget: Any) -> None:
        if not self.enabled or not self._live:
            return
        self._live.update(self._render(state, budget))

    def _render(self, state: Any, budget: Any) -> Panel:
        if state is None:
            return Panel("Starting…", title="Recon Agent")

        # Top: phase + step + counters
        header = (
            f"Step {state.step}    Phase: {state.current_phase}    "
            f"Tools: {len(state.tool_calls)}    "
            f"LLM calls: {len(state.llm_calls)}    "
            f"Discrepancies: {len(state.discrepancies)}    "
            f"Applied: {state.corrections_applied}"
        )

        # Last 5 tool calls
        table = Table(title="Last 5 tool calls", show_header=True, header_style="bold")
        table.add_column("step", width=4)
        table.add_column("tool", width=24)
        table.add_column("outcome", width=10)
        table.add_column("ms", width=6, justify="right")
        for c in state.tool_calls[-5:]:
            marker = {"ok": "[green]OK[/green]", "error": "[red]ERR[/red]",
                      "recovered": "[yellow]REC[/yellow]"}.get(c.outcome, "?")
            table.add_row(str(c.step), f"{marker} {c.tool_name}",
                          c.outcome, str(c.latency_ms))

        # Budget bars
        tokens_used = sum(c.tokens_in + c.tokens_out for c in state.llm_calls)
        cost_used = sum(c.cost_inr for c in state.llm_calls) + sum(c.cost_inr for c in state.tool_calls)

        bars = (
            f"Tokens     {self._bar(tokens_used, budget.max_tokens)}  "
            f"{tokens_used}/{budget.max_tokens}\n"
            f"Tool calls {self._bar(len(state.tool_calls), budget.max_tool_calls)}  "
            f"{len(state.tool_calls)}/{budget.max_tool_calls}\n"
            f"Cost INR   {self._bar(cost_used, budget.max_cost_inr)}  "
            f"INR {cost_used:.2f}/{budget.max_cost_inr}"
        )

        # Last decision
        reasoning = state.last_decision_reasoning[:300] or "(none yet)"

        body = (
            f"{header}\n\n"
            f"[bold]Budget[/bold]\n{bars}\n\n"
            f"[bold]Last reasoning[/bold]\n> {reasoning}"
        )

        # Render the table separately by appending it to a renderable group
        from rich.console import Group
        return Panel(Group(body, table), title="Recon Agent (live)",
                     border_style="cyan", subtitle=f"run {getattr(state, 'run_id', '')}")

    def _bar(self, used: float, total: float) -> str:
        pct = used / max(1, total)
        filled = int(pct * 20)
        return "[" + "#" * filled + "." * (20 - filled) + "]"
