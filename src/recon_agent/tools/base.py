from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

IN = TypeVar("IN", bound=BaseModel)
OUT = TypeVar("OUT", bound=BaseModel)


class ToolError(BaseModel):
    kind: Literal["transient", "persistent", "fatal"]
    code: str
    message: str
    retriable: bool


class ToolResult(BaseModel, Generic[OUT]):
    ok: bool
    output: OUT | None = None
    error: ToolError | None = None


class Tool(ABC, Generic[IN, OUT]):
    name: str
    input_schema: type[IN]
    output_schema: type[OUT]
    timeout_seconds: float = 30.0
    cost_estimate_inr: float = 0.0

    @abstractmethod
    def run(self, inputs: IN) -> ToolResult[OUT]: ...

    def describe(self) -> dict:
        return {
            "name": self.name,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
            "cost_estimate_inr": self.cost_estimate_inr,
            "timeout_seconds": self.timeout_seconds,
        }
