from pydantic import BaseModel
from .base import Tool, ToolResult


class NoopInput(BaseModel):
    note: str = ""


class NoopOutput(BaseModel):
    ok: bool = True


class NoopTool(Tool[NoopInput, NoopOutput]):
    name = "noop"
    input_schema = NoopInput
    output_schema = NoopOutput
    cost_estimate_inr = 0.0
    timeout_seconds = 1.0

    def run(self, inputs: NoopInput) -> ToolResult[NoopOutput]:
        return ToolResult(ok=True, output=NoopOutput(ok=True))
