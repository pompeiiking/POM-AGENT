"""
底层与完整开放性：与仓库内 ``app`` / ``core`` / ``port`` / ``modules`` 对齐的装配与协议。

当 ``pompeii_agent`` 顶层映射函数不足以表达定制（自定义 ``AssemblyModule``、改写 ``ModelModule`` 等）时，从这里继续深入。
"""

from __future__ import annotations

from app.composition import build_core, build_port
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.session_config_loader import SessionConfigSource, load_session_config
from app.config_provider import in_memory_mapping_config_provider, yaml_file_config_provider
from app.http_app_factory import HttpAgentService, InputDTO, build_http_agent_service
from core import AgentCore, AgentCoreImpl
from core.agent_types import AgentRequest, AgentResponse, ResponseReason
from core.types import DeviceRequest, ToolCall, ToolResult
from core.user_intent import (
    Chat,
    SystemHelp,
    SystemSummary,
    SystemArchive,
    SystemRemember,
    SystemForget,
    SystemPreference,
    SystemFact,
    SystemDelegate,
    ToolEcho,
    ToolTakePhoto,
    ToolPing,
    ToolAdd,
    UserIntent,
)
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule
from modules.tools.interface import ToolModule
from platform_layer.bundled_root import framework_root
from port.agent_port import AgentPort, GenericAgentPort, InteractionMode, PortEmitter, CliMode, CliEmitter, WsMode, HttpMode
from port.request_factory import RequestFactory, cli_request_factory, http_request_factory, ws_request_factory, session_request_factory
from port.intent_parser import parse_user_intent
from port.http_emitter import HttpEmitter
from port.events import (
    PortEvent,
    StreamDeltaEvent,
    ReplyEvent,
    ErrorEvent,
    StatusEvent,
    PolicyNoticeEvent,
    ConfirmationEvent,
    DelegateEvent,
    DeviceRequestEvent,
)
from port.input_events import (
    PortInput,
    UserMessageInput,
    SystemCommandInput,
    DeviceResultInput,
)
from core.session.session import (
    Session,
    SessionConfig,
    SessionLimits,
    SessionStatus,
    SessionStats,
    Message,
    Part,
)
from core.session.session_manager import SessionManager, SessionManagerImpl
from core.session.session_store import SessionStore

# ── Tool subsystem — full public surface ────────────────────────────────────
from modules.tools import (
    ToolHandler,
    DeviceBackend,
    DeviceExecutionResult,
    LocalSimulatorBackend,
    CompositeDeviceBackend,
    device_result_to_tool_result,
    HttpUrlGuardError,
    assert_safe_http_tool_url,
    enforce_http_url_policy,
    ToolPluginDiscoveryError,
    discover_entrypoint_handlers,
    assert_tool_handler_signature,
)
from modules.tools.impl import ToolModuleImpl, load_tool_handler
from modules.tools.network_policy import ToolNetworkPolicyConfig
from modules.tools.mcp_bridge import McpToolBridge
from modules.tools.builtin_handlers import (
    echo_handler,
    calc_handler,
    now_handler,
    make_http_get_handler,
)
from app.config_loaders import (
    ToolRegistryConfig,
    DeviceToolRoute,
    ToolRegistryLoaderError,
    ToolRegistrySource,
    load_tool_registry_config,
)
from infra import (
    McpRuntimeConfig,
    McpServerEntry,
    McpHttpServerEntry,
    McpConfigSource,
    McpConfigLoaderError,
    McpBridgeRegistryError,
    resolve_mcp_bridge,
    McpStdioBridge,
    McpMultiStdioBridge,
    McpHttpBridge,
    McpMultiHttpBridge,
)
from app import (
    NoopDeviceBackend,
    DeviceBackendFactory,
    resolve_device_backend,
    build_device_backend,
)

__all__ = [
    # Config sources
    "ModelProviderSource",
    "SessionConfigSource",
    "ToolRegistrySource",
    "McpConfigSource",
    # Core
    "AgentCore",
    "AgentCoreImpl",
    "AgentPort",
    "AgentRequest",
    "AgentResponse",
    "AssemblyModule",
    "DeviceRequest",
    "GenericAgentPort",
    "HttpAgentService",
    "InputDTO",
    "InteractionMode",
    "ModelModule",
    "PortEmitter",
    "RequestFactory",
    "ResponseReason",
    "ToolCall",
    "ToolModule",
    "ToolResult",
    # User intent
    "Chat",
    "SystemHelp",
    "SystemSummary",
    "SystemArchive",
    "SystemRemember",
    "SystemForget",
    "SystemPreference",
    "SystemFact",
    "SystemDelegate",
    "ToolEcho",
    "ToolTakePhoto",
    "ToolPing",
    "ToolAdd",
    "UserIntent",
    # Port interaction modes
    "CliMode",
    "CliEmitter",
    "WsMode",
    "HttpMode",
    # Port events
    "PortEvent",
    "StreamDeltaEvent",
    "ReplyEvent",
    "ErrorEvent",
    "StatusEvent",
    "PolicyNoticeEvent",
    "ConfirmationEvent",
    "DelegateEvent",
    "DeviceRequestEvent",
    # Port inputs
    "PortInput",
    "UserMessageInput",
    "SystemCommandInput",
    "DeviceResultInput",
    # Port helpers
    "parse_user_intent",
    "cli_request_factory",
    "http_request_factory",
    "ws_request_factory",
    "session_request_factory",
    "HttpEmitter",
    # Session
    "Session",
    "SessionConfig",
    "SessionLimits",
    "SessionManager",
    "SessionManagerImpl",
    "SessionStats",
    "SessionStatus",
    "SessionStore",
    "Message",
    "Part",
    # Tool module
    "ToolModuleImpl",
    "ToolHandler",
    "load_tool_handler",
    "McpToolBridge",
    "ToolNetworkPolicyConfig",
    # Builtin handlers
    "echo_handler",
    "calc_handler",
    "now_handler",
    "make_http_get_handler",
    # Device backend
    "DeviceBackend",
    "DeviceExecutionResult",
    "LocalSimulatorBackend",
    "CompositeDeviceBackend",
    "device_result_to_tool_result",
    "NoopDeviceBackend",
    "DeviceBackendFactory",
    "resolve_device_backend",
    "build_device_backend",
    # URL guard
    "HttpUrlGuardError",
    "assert_safe_http_tool_url",
    "enforce_http_url_policy",
    # Plugin discovery
    "ToolPluginDiscoveryError",
    "discover_entrypoint_handlers",
    "assert_tool_handler_signature",
    # Tool registry
    "ToolRegistryConfig",
    "DeviceToolRoute",
    "ToolRegistryLoaderError",
    "load_tool_registry_config",
    # MCP
    "McpRuntimeConfig",
    "McpServerEntry",
    "McpHttpServerEntry",
    "McpConfigLoaderError",
    "McpBridgeRegistryError",
    "resolve_mcp_bridge",
    "McpStdioBridge",
    "McpMultiStdioBridge",
    "McpHttpBridge",
    "McpMultiHttpBridge",
    # Assembly
    "build_core",
    "build_http_agent_service",
    "build_port",
    "framework_root",
    "in_memory_mapping_config_provider",
    "load_model_registry",
    "load_session_config",
    "yaml_file_config_provider",
]
