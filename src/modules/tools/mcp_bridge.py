"""
MCP 工具桥接协议（见 `infra/mcp_stdio_bridge.py`、`platform_layer/resources/config/mcp_servers.yaml`）。

由 `composition.build_core` 在已安装 `mcp` 且 `mcp_servers.yaml` 中 `enabled: true` 时注入；
`ToolModuleImpl` 在本地 handlers 无匹配时调用 `try_call`。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.session.session import Session
from core.types import ToolCall, ToolResult


@runtime_checkable
class McpToolBridge(Protocol):
    """由上层注入；本地工具名未命中时可尝试经 MCP 执行。"""

    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        """若 MCP 处理了该调用则返回结果，否则返回 None 让调用方走默认 unknown 路径。"""
        ...
