from __future__ import annotations
from typing import Any

from ..agent.phases import ActOutput
from ..agent.state import AgentState
from ..tools.base import ToolError
from .classifier import ErrorClassifier
from .strategies import (
    RecoveryDecision, RetryWithBackoff, ReplanWithAlternativeTool, GracefulDegrade
)


class RecoveryLayer:
    def __init__(self, logger: Any = None):
        self.classifier = ErrorClassifier()
        self.retry = RetryWithBackoff()
        self.replan = ReplanWithAlternativeTool()
        self.degrade = GracefulDegrade()
        self.logger = logger

    def handle(
        self,
        error: ToolError,
        state: AgentState,
        original_act: ActOutput,
        tools: Any,
    ) -> RecoveryDecision:
        action = self.classifier.classify(error, state)
        if self.logger:
            try:
                self.logger.info("recovery.dispatched", action=action.kind, reason=action.reason)
            except Exception:
                pass  # logger optional

        if action.kind == "retry":
            return self.retry.execute(action, original_act, tools)
        if action.kind == "replan":
            return self.replan.execute(action)
        if action.kind == "degrade":
            return self.degrade.execute(action)

        return RecoveryDecision(kind="degrade", reason=f"unknown action {action.kind}")
