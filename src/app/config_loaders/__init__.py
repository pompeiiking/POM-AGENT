"""
工具注册表配置加载器对外公共 API。

外部用户应从本包导入::

    from app.config_loaders import (
        ToolRegistryConfig,
        DeviceToolRoute,
        ToolRegistrySource,
        ToolRegistryLoaderError,
        load_tool_registry_config,
    )
"""

from __future__ import annotations

from .tool_registry_loader import (
    ToolRegistryConfig,
    DeviceToolRoute,
    ToolRegistrySource,
    ToolRegistryLoaderError,
    load_tool_registry_config,
)

__all__ = [
    "ToolRegistryConfig",
    "DeviceToolRoute",
    "ToolRegistrySource",
    "ToolRegistryLoaderError",
    "load_tool_registry_config",
]
