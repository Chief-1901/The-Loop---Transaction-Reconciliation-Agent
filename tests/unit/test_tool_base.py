from pydantic import BaseModel
from recon_agent.tools.base import Tool, ToolResult, ToolError


class InpModel(BaseModel):
    x: int


class OutModel(BaseModel):
    y: int


class DoubleTool(Tool[InpModel, OutModel]):
    name = "double"
    input_schema = InpModel
    output_schema = OutModel
    cost_estimate_inr = 0.0
    timeout_seconds = 1.0

    def run(self, inputs: InpModel) -> ToolResult[OutModel]:
        return ToolResult(ok=True, output=OutModel(y=inputs.x * 2))


def test_tool_run_returns_typed_result():
    t = DoubleTool()
    result = t.run(InpModel(x=21))
    assert result.ok is True
    assert result.output.y == 42
    assert result.error is None


def test_tool_describe_returns_schema():
    t = DoubleTool()
    desc = t.describe()
    assert desc["name"] == "double"
    assert "input_schema" in desc
    assert "output_schema" in desc


def test_tool_error_is_typed():
    err = ToolError(kind="transient", code="RATE_LIMIT",
                    message="429", retriable=True)
    assert err.kind == "transient"
