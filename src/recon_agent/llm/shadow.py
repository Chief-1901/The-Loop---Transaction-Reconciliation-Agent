# src/recon_agent/llm/shadow.py
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..agent.phases import Phase
from ..agent.state import LLMCallRecord


class ShadowRunner:
    """When enabled, Plan phase calls Gemini Flash AND GPT-4o in parallel.
    Primary feeds the loop; secondary logged for offline comparison."""

    def __init__(self, router: Any, enabled: bool, log_path: Path):
        self.router = router
        self.enabled = enabled
        self.log_path = log_path

    def plan_call(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        step: int = 0,
    ) -> tuple[BaseModel, list[LLMCallRecord]]:
        if not self.enabled:
            out, rec = self.router.call("plan", messages, schema, step=step, phase=Phase.PLAN)
            return out, [rec]

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_prim = ex.submit(self.router.call, "plan", messages, schema,
                               step=step, phase=Phase.PLAN)
            f_sec = ex.submit(self.router.call, "shadow_plan", messages, schema,
                              step=step, phase=Phase.PLAN)
            prim_out, prim_rec = f_prim.result()
            sec_out, sec_rec = f_sec.result()

        self._log(step, prim_out, sec_out, prim_rec, sec_rec)
        return prim_out, [prim_rec, sec_rec]

    def _log(self, step, prim, sec, prim_rec, sec_rec):
        line = {
            "step": step,
            "primary": {
                "tool": getattr(prim, "intended_tool", None),
                "args": getattr(prim, "tool_args", None),
                "model": prim_rec.model, "cost_inr": prim_rec.cost_inr,
            },
            "secondary": {
                "tool": getattr(sec, "intended_tool", None),
                "args": getattr(sec, "tool_args", None),
                "model": sec_rec.model, "cost_inr": sec_rec.cost_inr,
            },
            "agreed_tool": getattr(prim, "intended_tool", None)
                           == getattr(sec, "intended_tool", None),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
