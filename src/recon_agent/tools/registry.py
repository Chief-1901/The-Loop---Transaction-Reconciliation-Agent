from __future__ import annotations
import importlib
import inspect
import pkgutil
from typing import ClassVar

from .base import Tool


class ToolRegistry:
    _tools: ClassVar[dict[str, Tool]] = {}
    _discovered: ClassVar[bool] = False

    @classmethod
    def register(cls, tool: Tool) -> None:
        cls._tools[tool.name] = tool

    @classmethod
    def discover(cls, force: bool = False) -> None:
        if cls._discovered and not force:
            return
        cls._tools.clear()
        import recon_agent.tools as pkg
        for _, mod_name, _ in pkgutil.iter_modules(pkg.__path__):
            if mod_name in ("base", "registry"):
                continue
            module = importlib.import_module(f"recon_agent.tools.{mod_name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, Tool)
                        and obj is not Tool
                        and hasattr(obj, "name")
                        and obj.__module__ == module.__name__):
                    cls.register(obj())
        cls._discovered = True

    @classmethod
    def get(cls, name: str) -> Tool:
        if not cls._discovered:
            cls.discover()
        return cls._tools[name]

    @classmethod
    def available(cls, disabled: set[str] = frozenset()) -> list[Tool]:
        if not cls._discovered:
            cls.discover()
        return [t for n, t in cls._tools.items() if n not in disabled]

    @classmethod
    def schemas_for_llm(cls, disabled: set[str] = frozenset()) -> list[dict]:
        return [t.describe() for t in cls.available(disabled)]
