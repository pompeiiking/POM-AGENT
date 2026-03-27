from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable

from infra.mcp_config_loader import McpRuntimeConfig
from modules.tools.mcp_bridge import McpToolBridge


class McpBridgeRegistryError(ValueError):
    pass


McpBridgeFactory = Callable[[McpRuntimeConfig, Path], McpToolBridge | None]


def resolve_mcp_bridge(
    *,
    cfg: McpRuntimeConfig,
    src_root: Path,
    entrypoint_group: str = "pompeii_agent.mcp_bridges",
    discover_fn: Callable[[str], dict[str, McpBridgeFactory]] | None = None,
) -> McpToolBridge | None:
    """
    MCP 工具桥热插拔入口（调用方须已判定 cfg.enabled 且 cfg.servers 非空）。

    - ``builtin:stdio``：内置 ``McpStdioBridge`` / ``McpMultiStdioBridge``（需已安装 ``mcp`` 包）
    - ``builtin:http_json``：内置 HTTP 网关桥（`POST {base_url}/tools/call`）
    - ``entrypoint:<name>``：工厂签名为 ``(cfg: McpRuntimeConfig, src_root: Path) -> McpToolBridge | None``
    """
    r = str(cfg.bridge_ref).strip() or "builtin:stdio"
    if r == "builtin:stdio":
        return _builtin_stdio_bridge(cfg, src_root)
    if r == "builtin:http_json":
        return _builtin_http_json_bridge(cfg, src_root)
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise McpBridgeRegistryError("mcp bridge entrypoint name must be non-empty")
        if discover_fn is not None:
            registry = discover_fn(entrypoint_group)
        else:
            registry = _discover_mcp_bridge_factories(group=entrypoint_group)
        factory = registry.get(name)
        if factory is None:
            raise McpBridgeRegistryError(
                f"mcp bridge entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return factory(cfg, src_root)
    raise McpBridgeRegistryError("mcp bridge ref must be 'builtin:stdio' | 'builtin:http_json' | 'entrypoint:<name>'")


def _builtin_stdio_bridge(cfg: McpRuntimeConfig, src_root: Path) -> McpToolBridge | None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        return None
    from infra.mcp_stdio_bridge import McpMultiStdioBridge, McpStdioBridge

    if not cfg.servers:
        return None
    if len(cfg.servers) == 1:
        return McpStdioBridge(cfg.servers[0], src_root=src_root)
    return McpMultiStdioBridge(cfg.servers, src_root=src_root)


def _builtin_http_json_bridge(cfg: McpRuntimeConfig, src_root: Path) -> McpToolBridge | None:
    from infra.mcp_http_bridge import McpHttpBridge, McpMultiHttpBridge

    if not cfg.http_servers:
        return None
    if len(cfg.http_servers) == 1:
        return McpHttpBridge(cfg.http_servers[0], src_root=src_root)
    return McpMultiHttpBridge(cfg.http_servers, src_root=src_root)


def _discover_mcp_bridge_factories(*, group: str) -> dict[str, McpBridgeFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, McpBridgeFactory] = {}
    for ep in selected:
        name = str(ep.name).strip()
        if not name:
            raise McpBridgeRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise McpBridgeRegistryError(f"entry point {group}:{name} is not callable")
        out[name] = fn  # type: ignore[assignment]
    return out
