"""
MCP 基础设施对外公共 API。

外部用户应从本包导入所有 MCP 相关类型::

    from infra import (
        McpRuntimeConfig,
        McpServerEntry,
        McpHttpServerEntry,
        McpConfigSource,
        McpBridgeRegistryError,
        load_mcp_config,
        resolve_mcp_bridge,
        McpStdioBridge,
        McpMultiStdioBridge,
        McpHttpBridge,
        McpMultiHttpBridge,
    )
"""

from __future__ import annotations

from .mcp_config_loader import (
    McpConfigLoaderError,
    McpServerEntry,
    McpRuntimeConfig,
    McpHttpServerEntry,
    McpConfigSource,
    load_mcp_config,
)
from app.mcp_bridge_registry import (
    McpBridgeRegistryError,
    resolve_mcp_bridge,
)
from .mcp_stdio_bridge import (
    McpStdioBridge,
    McpMultiStdioBridge,
)
from .mcp_http_bridge import (
    McpHttpBridge,
    McpMultiHttpBridge,
)

__all__ = [
    # Config loader
    "McpConfigLoaderError",
    "McpServerEntry",
    "McpRuntimeConfig",
    "McpHttpServerEntry",
    "McpConfigSource",
    "load_mcp_config",
    # Bridge registry
    "McpBridgeRegistryError",
    "resolve_mcp_bridge",
    # Stdio bridge
    "McpStdioBridge",
    "McpMultiStdioBridge",
    # HTTP bridge
    "McpHttpBridge",
    "McpMultiHttpBridge",
]
