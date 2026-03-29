"""
对外公共 API（工具子系统）。

外部用户应从本包导入所有工具相关类型，无需记忆内部模块路径::

    from pompeii_agent import (
        ToolModuleImpl,
        ToolModule,
        ToolHandler,
        load_tool_handler,
        McpToolBridge,
        ToolNetworkPolicyConfig,
        DeviceBackend,
        DeviceExecutionResult,
        LocalSimulatorBackend,
        CompositeDeviceBackend,
        device_result_to_tool_result,
        HttpUrlGuardError,
        assert_safe_http_tool_url,
        enforce_http_url_policy,
        ToolRegistryConfig,
        DeviceToolRoute,
        ToolRegistryLoaderError,
        discover_entrypoint_handlers,
        assert_tool_handler_signature,
        ToolPluginDiscoveryError,
        echo_handler,
        calc_handler,
        now_handler,
        make_http_get_handler,
    )
"""

from __future__ import annotations

from core.session.session import Session
from core.types import DeviceRequest, ToolCall, ToolResult

from .interface import ToolModule
from .mcp_bridge import McpToolBridge
from .network_policy import ToolNetworkPolicyConfig
from .http_url_guard import (
    HttpUrlGuardError,
    assert_safe_http_tool_url,
    enforce_http_url_policy,
)
from .device_backend import (
    DeviceBackend,
    DeviceExecutionResult,
    LocalSimulatorBackend,
    CompositeDeviceBackend,
    device_result_to_tool_result,
)
from .plugin_discovery import (
    ToolPluginDiscoveryError,
    discover_entrypoint_handlers,
    assert_tool_handler_signature,
)
from app.config_loaders.tool_registry_loader import (
    ToolRegistryConfig,
    DeviceToolRoute,
    ToolRegistryLoaderError,
    ToolRegistrySource,
    load_tool_registry_config,
)

# ToolHandler: 工具处理器签名的类型别名
# signature: Callable[[Session, ToolCall], ToolResult]
ToolHandler = __import__("typing").Callable[[Session, ToolCall], ToolResult]

# ── ToolModuleImpl 延迟导入（避免与 .device_backend 循环）──────────────────────
# 所有公开 API 均通过本 __init__.py 对外暴露，
# 但 ToolModuleImpl 自身依赖 DeviceBackendProtocol（在 impl.py 中定义），
# 故在 impl.py 底部 import 回来时不会触发循环。
# 为绝对安全，使用 TYPE_CHECKING guard。
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .impl import ToolModuleImpl
else:
    from .impl import ToolModuleImpl, load_tool_handler

__all__ = [
    # Core abstractions
    "ToolModule",
    "ToolModuleImpl",
    "ToolHandler",
    "load_tool_handler",
    # MCP
    "McpToolBridge",
    # Network policy
    "ToolNetworkPolicyConfig",
    "HttpUrlGuardError",
    "assert_safe_http_tool_url",
    "enforce_http_url_policy",
    # Device backend
    "DeviceBackend",
    "DeviceExecutionResult",
    "LocalSimulatorBackend",
    "CompositeDeviceBackend",
    "device_result_to_tool_result",
    # Plugin discovery
    "ToolPluginDiscoveryError",
    "discover_entrypoint_handlers",
    "assert_tool_handler_signature",
    # Tool registry config
    "ToolRegistryConfig",
    "DeviceToolRoute",
    "ToolRegistryLoaderError",
    "ToolRegistrySource",
    "load_tool_registry_config",
]
