from __future__ import annotations

from pathlib import Path
from typing import Callable

from core import AgentCoreImpl, KernelConfig, SessionConfig, SessionManagerImpl
from core.session.session_store import SessionStore
from infra.sqlite_session_store import SqliteSessionStore
from modules.assembly.impl import AssemblyModuleImpl
from modules.model.impl import ModelModuleImpl
from modules.tools.impl import ToolModuleImpl
from app.config_provider import yaml_file_config_provider
from port.agent_port import GenericAgentPort, InteractionMode, PortEmitter
from port.request_factory import RequestFactory
from app.config_loaders.kernel_config_loader import KernelConfigSource, load_kernel_config
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from modules.model.config import ModelRegistry
from modules.tools.mcp_bridge import McpToolBridge


ConfigProvider = Callable[[str, str], SessionConfig]


def build_core(
    config_provider: ConfigProvider,
    model_registry: ModelRegistry | None = None,
    *,
    src_root: Path | None = None,
) -> AgentCoreImpl:
    base = src_root if src_root is not None else Path(__file__).resolve().parents[1]
    store = _load_session_store(base)
    manager = SessionManagerImpl(store)
    assembly = AssemblyModuleImpl()
    model = _build_model(model_registry)
    tools = ToolModuleImpl(mcp=_load_mcp_bridge(base))
    kernel_config = _load_kernel_config()
    return AgentCoreImpl(
        session_manager=manager,
        assembly=assembly,
        model=model,
        tools=tools,
        config_provider=config_provider,
        kernel_config=kernel_config,
    )


def build_port(mode: InteractionMode, request_factory: RequestFactory, emitter: PortEmitter) -> GenericAgentPort:
    base = Path(__file__).resolve().parents[1]  # .../pompeii/src
    config_path = base / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
    model_registry = _load_model_registry(base)
    core = build_core(
        config_provider=yaml_file_config_provider(config_path),
        model_registry=model_registry,
        src_root=base,
    )
    return GenericAgentPort(mode=mode, core=core, request_factory=request_factory, emitter=emitter)


def _load_kernel_config() -> KernelConfig:
    base = Path(__file__).resolve().parents[1]  # .../pompeii/src
    config_path = base / "platform_layer" / "resources" / "config" / "kernel_config.yaml"
    return load_kernel_config(KernelConfigSource(path=config_path))


def _load_model_registry(base: Path) -> ModelRegistry:
    config_path = base / "platform_layer" / "resources" / "config" / "model_providers.yaml"
    return load_model_registry(ModelProviderSource(path=config_path))


def _build_model(model_registry: ModelRegistry | None) -> ModelModuleImpl:
    if model_registry is None:
        return ModelModuleImpl()
    return ModelModuleImpl(registry=model_registry)


def _load_mcp_bridge(src_root: Path) -> McpToolBridge | None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        return None
    from infra.mcp_config_loader import McpConfigSource, load_mcp_config
    from infra.mcp_stdio_bridge import McpMultiStdioBridge, McpStdioBridge

    cfg = load_mcp_config(
        McpConfigSource(path=src_root / "platform_layer" / "resources" / "config" / "mcp_servers.yaml"),
        src_root=src_root,
    )
    if not cfg.enabled or not cfg.servers:
        return None
    if len(cfg.servers) == 1:
        return McpStdioBridge(cfg.servers[0], src_root=src_root)
    return McpMultiStdioBridge(cfg.servers, src_root=src_root)


def _load_session_store(src_root: Path) -> SessionStore:
    path = src_root / "platform_layer" / "resources" / "config" / "runtime.yaml"
    rc = load_runtime_config(RuntimeConfigSource(path=path))
    resolved = rc.sqlite_path if rc.sqlite_path.is_absolute() else (src_root / rc.sqlite_path)
    return SqliteSessionStore(resolved)

