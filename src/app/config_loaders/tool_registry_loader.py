from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from modules.tools.network_policy import ToolNetworkPolicyConfig

from .session_config_loader import read_config_mapping


class ToolRegistryLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class DeviceToolRoute:
    tool: str
    device: str
    command: str
    fixed_parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolRegistryConfig:
    local_handlers: dict[str, str]
    device_routes: dict[str, DeviceToolRoute]
    enable_entrypoints: bool
    entrypoint_group: str
    network_policy: ToolNetworkPolicyConfig
    device_backend_refs: tuple[str, ...]


@dataclass(frozen=True)
class ToolRegistrySource:
    path: Path


def load_tool_registry_config(source: ToolRegistrySource) -> ToolRegistryConfig:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "tools")
    local = _parse_local_handlers(root.get("local_handlers"))
    routes = _parse_device_routes(root.get("device_routes"))
    enable_entrypoints = bool(root.get("enable_entrypoints", True))
    entrypoint_group = str(root.get("entrypoint_group", "pompeii_agent.tools")).strip()
    if not entrypoint_group:
        raise ToolRegistryLoaderError("tools.entrypoint_group must be non-empty string")
    net = _parse_network_policy(root.get("network_policy"))
    device_backend_refs = _parse_device_backend_refs(root.get("device_backend_refs"))
    return ToolRegistryConfig(
        local_handlers=local,
        device_routes=routes,
        enable_entrypoints=enable_entrypoints,
        entrypoint_group=entrypoint_group,
        network_policy=net,
        device_backend_refs=device_backend_refs,
    )


def _parse_network_policy(raw: Any) -> ToolNetworkPolicyConfig:
    if raw is None:
        return ToolNetworkPolicyConfig()
    if not isinstance(raw, Mapping):
        raise ToolRegistryLoaderError("tools.network_policy must be a mapping")
    enabled = bool(raw.get("enabled", False))
    deny = _parse_nonempty_str_list(raw.get("deny_tool_names"), "tools.network_policy.deny_tool_names")
    mcp_enf = bool(raw.get("mcp_allowlist_enforced", False))
    mcp_list = _parse_nonempty_str_list(
        raw.get("mcp_tool_allowlist"), "tools.network_policy.mcp_tool_allowlist"
    )
    http_guard = bool(raw.get("http_url_guard_enabled", False))
    http_hosts = _parse_nonempty_str_list(
        raw.get("http_url_allowed_hosts"), "tools.network_policy.http_url_allowed_hosts"
    )
    http_ct_block = _parse_nonempty_str_list(
        raw.get("http_blocked_content_type_prefixes"),
        "tools.network_policy.http_blocked_content_type_prefixes",
    )
    http_ct_block_norm = tuple(s.strip().lower() for s in http_ct_block)
    return ToolNetworkPolicyConfig(
        enabled=enabled,
        deny_tool_names=tuple(deny),
        mcp_allowlist_enforced=mcp_enf,
        mcp_tool_allowlist=tuple(mcp_list),
        http_url_guard_enabled=http_guard,
        http_url_allowed_hosts=tuple(http_hosts),
        http_blocked_content_type_prefixes=http_ct_block_norm,
    )


def _parse_nonempty_str_list(raw: Any, path: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ToolRegistryLoaderError(f"{path} must be a list")
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ToolRegistryLoaderError(f"{path}[{i}] must be non-empty string")
        out.append(item.strip())
    return out


def _parse_device_backend_refs(raw: Any) -> tuple[str, ...]:
    """解析设备后端引用列表，默认使用本地模拟器"""
    if raw is None:
        return ("builtin:simulator",)
    if not isinstance(raw, list):
        raise ToolRegistryLoaderError("tools.device_backend_refs must be a list")
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ToolRegistryLoaderError(f"tools.device_backend_refs[{i}] must be non-empty string")
        ref = item.strip()
        if ":" not in ref:
            raise ToolRegistryLoaderError(
                f"tools.device_backend_refs[{i}] must be 'prefix:name' format (e.g., builtin:simulator)"
            )
        out.append(ref)
    return tuple(out) if out else ("builtin:simulator",)


def _parse_local_handlers(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ToolRegistryLoaderError("tools.local_handlers must be mapping")
    out: dict[str, str] = {}
    for tool_name, ref in raw.items():
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ToolRegistryLoaderError("tools.local_handlers key must be non-empty string")
        if not isinstance(ref, str) or ":" not in ref:
            raise ToolRegistryLoaderError(
                f"tools.local_handlers.{tool_name} must be 'module.path:function_name'"
            )
        out[tool_name.strip()] = ref.strip()
    return out


def _parse_device_routes(raw: Any) -> dict[str, DeviceToolRoute]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ToolRegistryLoaderError("tools.device_routes must be list")
    out: dict[str, DeviceToolRoute] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ToolRegistryLoaderError(f"tools.device_routes[{i}] must be mapping")
        tool = _require_str(item, "tool", f"tools.device_routes[{i}]")
        device = _require_str(item, "device", f"tools.device_routes[{i}]")
        command = _require_str(item, "command", f"tools.device_routes[{i}]")
        fixed_parameters = item.get("fixed_parameters")
        if fixed_parameters is None:
            fixed_parameters = {}
        if not isinstance(fixed_parameters, Mapping):
            raise ToolRegistryLoaderError(f"tools.device_routes[{i}].fixed_parameters must be mapping")
        out[tool] = DeviceToolRoute(
            tool=tool,
            device=device,
            command=command,
            fixed_parameters=dict(fixed_parameters),
        )
    return out


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    v = parent.get(key)
    if not isinstance(v, Mapping):
        raise ToolRegistryLoaderError(f"missing object field: {key}")
    return v


def _require_str(parent: Mapping[str, Any], key: str, path: str) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ToolRegistryLoaderError(f"{path}.{key} must be non-empty string")
    return v.strip()
