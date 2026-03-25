from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Mapping

from core.session.session import Session
from core.types import DeviceRequest, ToolCall, ToolResult
from .interface import ToolModule
from .mcp_bridge import McpToolBridge
from .network_policy import ToolNetworkPolicyConfig

ToolHandler = Callable[[Session, ToolCall], ToolResult]


class ToolModuleImpl(ToolModule):
    """
    最终版工具模块：
    - 本地工具由配置声明并动态加载（无硬编码工具名）
    - 设备请求路由由配置声明（无 core 内硬编码）
    - 本地未命中时可回退 MCP
    """

    def __init__(
        self,
        *,
        local_handlers: Mapping[str, ToolHandler] | None = None,
        device_routes: Mapping[str, DeviceRequest] | None = None,
        mcp: McpToolBridge | None = None,
        network_policy: ToolNetworkPolicyConfig | None = None,
    ) -> None:
        self._local_handlers: dict[str, ToolHandler] = dict(local_handlers or {})
        self._device_routes: dict[str, DeviceRequest] = dict(device_routes or {})
        self._mcp = mcp
        self._network_policy = network_policy

    def execute(self, session: Session, tool_call: ToolCall) -> ToolResult:
        pol = self._network_policy
        if pol is not None and pol.enabled and tool_call.name in pol.deny_tool_names:
            return ToolResult(
                name=tool_call.name,
                output={
                    "error": "tool_network_denied",
                    "reason": "tool_name_blocked_by_network_policy",
                    "session_id": session.session_id,
                },
            )

        handler = self._local_handlers.get(tool_call.name)
        if handler is not None:
            return handler(session, tool_call)
        if self._mcp is not None:
            if (
                pol is not None
                and pol.enabled
                and pol.mcp_allowlist_enforced
                and tool_call.name not in pol.mcp_tool_allowlist
            ):
                return ToolResult(
                    name=tool_call.name,
                    output={
                        "error": "tool_network_mcp_denied",
                        "reason": "mcp_tool_not_in_allowlist",
                        "session_id": session.session_id,
                    },
                    source="mcp",
                )
            bridged = self._mcp.try_call(session, tool_call)
            if bridged is not None:
                return bridged
        return ToolResult(
            name=tool_call.name,
            output={
                "error": f"unknown tool: {tool_call.name!r}",
                "session_id": session.session_id,
            },
        )

    def resolve_device_request(self, tool_call: ToolCall) -> DeviceRequest | None:
        route = self._device_routes.get(tool_call.name)
        if route is None:
            return None
        merged = {**dict(route.parameters), **dict(tool_call.arguments)}
        return DeviceRequest(device=route.device, command=route.command, parameters=merged)


def load_tool_handler(ref: str) -> ToolHandler:
    """
    动态加载 handler：`module.path:function_name`
    """
    module_name, func_name = _split_ref(ref)
    mod = import_module(module_name)
    fn = getattr(mod, func_name, None)
    if not callable(fn):
        raise ValueError(f"tool handler is not callable: {ref}")
    return fn  # type: ignore[return-value]


def _split_ref(ref: str) -> tuple[str, str]:
    if ":" not in ref:
        raise ValueError(f"invalid tool handler reference: {ref!r}")
    module_name, func_name = ref.split(":", 1)
    module_name = module_name.strip()
    func_name = func_name.strip()
    if not module_name or not func_name:
        raise ValueError(f"invalid tool handler reference: {ref!r}")
    return module_name, func_name

