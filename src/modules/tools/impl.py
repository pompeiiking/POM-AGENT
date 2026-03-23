from __future__ import annotations

from typing import Callable
import ast
import operator

from core.session.session import Session
from .device_backend import DeviceToolBackend, NullDeviceBackend
from .interface import ToolModule
from .mcp_bridge import McpToolBridge
from core.types import ToolCall, ToolResult


class ToolModuleImpl(ToolModule):
    """
    工具部实现：
    - 本地工具：echo / calc / now 等
    - 可选 `McpToolBridge`：本地无 handler 时尝试 MCP（见 `mcp_bridge.py`）
    - 可选 `DeviceToolBackend`：在 `execute` 路径下优先尝试本地设备桩（见 `device_backend.py`）
    """

    def __init__(
        self,
        mcp: McpToolBridge | None = None,
        *,
        device_backend: DeviceToolBackend | None = None,
    ) -> None:
        self._mcp = mcp
        self._device_backend: DeviceToolBackend = device_backend or NullDeviceBackend()
        self._handlers: dict[str, Callable[[Session, ToolCall], ToolResult]] = {
            "echo": self._echo,
            "calc": self._calc,
            "now": self._now,
        }

    def execute(self, session: Session, tool_call: ToolCall) -> ToolResult:
        local_device = self._device_backend.try_local(session, tool_call)
        if local_device is not None:
            return local_device
        handler = self._handlers.get(tool_call.name)
        if handler is not None:
            return handler(session, tool_call)
        if self._mcp is not None:
            bridged = self._mcp.try_call(session, tool_call)
            if bridged is not None:
                return bridged
        return self._unknown(session, tool_call)

    def _echo(self, session: Session, tool_call: ToolCall) -> ToolResult:
        return ToolResult(
            name=tool_call.name,
            output={
                "echo": dict(tool_call.arguments),
                "session_id": session.session_id,
            },
        )

    def _calc(self, session: Session, tool_call: ToolCall) -> ToolResult:
        expr = str(tool_call.arguments.get("expression", ""))
        value = _safe_eval(expr)
        return ToolResult(
            name=tool_call.name,
            output={
                "kind": "calc",
                "expression": expr,
                "value": value,
                "session_id": session.session_id,
            },
        )

    def _now(self, session: Session, tool_call: ToolCall) -> ToolResult:
        from datetime import datetime, timezone

        _ = tool_call
        now = datetime.now(timezone.utc)
        return ToolResult(
            name="now",
            output={
                "kind": "now",
                "iso_utc": now.isoformat(),
                "timestamp": now.timestamp(),
                "session_id": session.session_id,
            },
        )

    def _unknown(self, session: Session, tool_call: ToolCall) -> ToolResult:
        return ToolResult(
            name=tool_call.name,
            output={
                "error": f"unknown tool: {tool_call.name!r}",
                "session_id": session.session_id,
            },
        )


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(expr: str) -> float | int | None:
    """
    极简安全算术表达式求值，仅支持数字和 + - * / // % ** ()。
    """
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    return _eval_node(node.body)


def _eval_node(node: ast.AST) -> float | int | None:
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return node.n  # type: ignore[no-any-return]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        operand = _eval_node(node.operand)
        if operand is None:
            return None
        return _OPS[type(node.op)](operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if left is None or right is None:
            return None
        return _OPS[type(node.op)](left, right)
    return None

