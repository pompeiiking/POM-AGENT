from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from core.session.session import Session
from core.types import ToolCall, ToolResult

ToolHandler = Any


class ToolPluginDiscoveryError(ValueError):
    pass


def discover_entrypoint_handlers(*, group: str) -> dict[str, ToolHandler]:
    """
    从 Python entry_points 动态发现工具处理器。
    约定：
    - entry point group: 例如 pompeii_agent.tools
    - entry point name: tool_name
    - entry point object: callable(session, tool_call) -> ToolResult
    """
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    handlers: dict[str, ToolHandler] = {}
    for ep in selected:
        name = str(ep.name).strip()
        if not name:
            raise ToolPluginDiscoveryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise ToolPluginDiscoveryError(f"entry point {group}:{name} is not callable")
        handlers[name] = fn
    return handlers


def assert_tool_handler_signature(handler: Any, *, path: str) -> None:
    # 运行时最小签名校验：只检查可调用，具体参数在调用时由 TypeError 暴露
    if not callable(handler):
        raise ToolPluginDiscoveryError(f"handler is not callable: {path}")
    _ = (Session, ToolCall, ToolResult)
