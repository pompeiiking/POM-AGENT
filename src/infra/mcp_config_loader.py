from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


class McpConfigLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class McpServerEntry:
    """单条 stdio MCP 进程配置（仅允许来自静态 YAML，禁止用户输入拼接）。"""

    id: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class McpRuntimeConfig:
    enabled: bool
    servers: tuple[McpServerEntry, ...]
    http_servers: tuple["McpHttpServerEntry", ...] = ()
    # builtin:stdio = 内置多进程 stdio 客户端；entrypoint:<name> 见 pompeii_agent.mcp_bridges
    bridge_ref: str = "builtin:stdio"


@dataclass(frozen=True)
class McpHttpServerEntry:
    id: str
    base_url: str
    api_key_env: str | None = None
    timeout_seconds: float = 20.0
    stream_enabled: bool = False
    stream_endpoint_path: str = "/tools/call/stream"
    # 流式事件字段映射（便于适配不同网关 JSON 结构）
    sse_event_type_key: str = "type"
    sse_delta_key: str = "delta"
    sse_text_key: str = "text"
    sse_output_key: str = "output"
    sse_result_event_value: str = "result"


@dataclass(frozen=True)
class McpConfigSource:
    path: Path


def load_mcp_config(source: McpConfigSource, *, src_root: Path) -> McpRuntimeConfig:
    if yaml is None:
        raise McpConfigLoaderError("PyYAML is required for mcp_servers.yaml")
    if not source.path.exists():
        return McpRuntimeConfig(enabled=False, servers=(), bridge_ref="builtin:stdio")

    raw = yaml.safe_load(source.path.read_text(encoding="utf-8"))
    if raw is None:
        return McpRuntimeConfig(enabled=False, servers=(), bridge_ref="builtin:stdio")
    if not isinstance(raw, dict):
        raise McpConfigLoaderError("mcp_servers.yaml root must be a mapping")

    enabled = bool(raw.get("enabled", False))
    bridge_ref = _parse_bridge_ref(raw)
    servers_raw = raw.get("servers")
    http_servers_raw = raw.get("http_servers")
    if servers_raw is None and http_servers_raw is None:
        return McpRuntimeConfig(enabled=enabled, servers=(), http_servers=(), bridge_ref=bridge_ref)
    if servers_raw is not None and not isinstance(servers_raw, list):
        raise McpConfigLoaderError("servers must be a list")
    if http_servers_raw is not None and not isinstance(http_servers_raw, list):
        raise McpConfigLoaderError("http_servers must be a list")

    servers: list[McpServerEntry] = []
    http_servers: list[McpHttpServerEntry] = []
    root_s = str(src_root.resolve())
    if isinstance(servers_raw, list):
        for i, item in enumerate(servers_raw):
            if not isinstance(item, Mapping):
                raise McpConfigLoaderError(f"servers[{i}] must be a mapping")
            sid = _require_str(item, "id")
            command = _require_str(item, "command")
            args = _require_str_list(item, "args")
            _validate_command(command)
            _validate_args(args)
            timeout = float(item.get("timeout_seconds", 30.0))
            if timeout <= 0 or timeout > 600:
                raise McpConfigLoaderError("timeout_seconds must be in (0, 600]")

            env: dict[str, str] | None = None
            if "env" in item and item["env"] is not None:
                env = _stringify_env(item["env"], src_root=root_s)
            cwd: str | None = None
            if item.get("cwd"):
                cwd = str(item["cwd"]).replace("{src_root}", root_s)

            servers.append(
                McpServerEntry(
                    id=sid,
                    command=command,
                    args=[a.replace("{src_root}", root_s) for a in args],
                    env=env,
                    cwd=cwd.replace("{src_root}", root_s) if cwd else None,
                    timeout_seconds=timeout,
                )
            )

    if isinstance(http_servers_raw, list):
        for i, item in enumerate(http_servers_raw):
            if not isinstance(item, Mapping):
                raise McpConfigLoaderError(f"http_servers[{i}] must be a mapping")
            sid = _require_str(item, "id")
            base_url = _require_str(item, "base_url").rstrip("/")
            if not (base_url.startswith("http://") or base_url.startswith("https://")):
                raise McpConfigLoaderError(f"http_servers[{i}].base_url must start with http:// or https://")
            timeout = float(item.get("timeout_seconds", 20.0))
            if timeout <= 0 or timeout > 600:
                raise McpConfigLoaderError("http_servers.timeout_seconds must be in (0, 600]")
            ak = item.get("api_key_env")
            api_key_env = str(ak).strip() if isinstance(ak, str) and str(ak).strip() else None
            stream_enabled_raw = item.get("stream_enabled", False)
            if not isinstance(stream_enabled_raw, bool):
                raise McpConfigLoaderError("http_servers.stream_enabled must be boolean")
            stream_path_raw = item.get("stream_endpoint_path", "/tools/call/stream")
            if not isinstance(stream_path_raw, str) or not stream_path_raw.strip().startswith("/"):
                raise McpConfigLoaderError("http_servers.stream_endpoint_path must start with '/'")
            type_key = _opt_non_empty_str(item, "sse_event_type_key", default="type")
            delta_key = _opt_non_empty_str(item, "sse_delta_key", default="delta")
            text_key = _opt_non_empty_str(item, "sse_text_key", default="text")
            output_key = _opt_non_empty_str(item, "sse_output_key", default="output")
            result_val = _opt_non_empty_str(item, "sse_result_event_value", default="result")
            http_servers.append(
                McpHttpServerEntry(
                    id=sid,
                    base_url=base_url,
                    api_key_env=api_key_env,
                    timeout_seconds=timeout,
                    stream_enabled=stream_enabled_raw,
                    stream_endpoint_path=stream_path_raw.strip(),
                    sse_event_type_key=type_key,
                    sse_delta_key=delta_key,
                    sse_text_key=text_key,
                    sse_output_key=output_key,
                    sse_result_event_value=result_val,
                )
            )

    return McpRuntimeConfig(enabled=enabled, servers=tuple(servers), http_servers=tuple(http_servers), bridge_ref=bridge_ref)


def _parse_bridge_ref(raw: Mapping[str, Any]) -> str:
    v = raw.get("bridge_ref")
    if v is None:
        return "builtin:stdio"
    if not isinstance(v, str) or not v.strip():
        raise McpConfigLoaderError("bridge_ref must be non-empty string when present")
    s = v.strip()
    if s in ("builtin:stdio", "builtin:http_json"):
        return s
    if s.startswith("entrypoint:"):
        name = s[len("entrypoint:") :].strip()
        if not name:
            raise McpConfigLoaderError("bridge_ref entrypoint name must be non-empty")
        return f"entrypoint:{name}"
    raise McpConfigLoaderError("bridge_ref must be 'builtin:stdio' | 'builtin:http_json' | 'entrypoint:<name>'")


def _require_str(parent: Mapping[str, Any], key: str) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or not v.strip():
        raise McpConfigLoaderError(f"missing non-empty string: {key}")
    return v.strip()


def _opt_non_empty_str(parent: Mapping[str, Any], key: str, *, default: str) -> str:
    v = parent.get(key)
    if v is None:
        return default
    if not isinstance(v, str) or not v.strip():
        raise McpConfigLoaderError(f"{key} must be non-empty string when present")
    return v.strip()


def _require_str_list(parent: Mapping[str, Any], key: str) -> list[str]:
    v = parent.get(key)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise McpConfigLoaderError(f"{key} must be a list[str]")
    return list(v)


def _stringify_env(raw: Any, *, src_root: str) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise McpConfigLoaderError("env must be a mapping")
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            raise McpConfigLoaderError("env keys must be strings")
        out[k] = str(v).replace("{src_root}", src_root)
    return out


_SAFE_CMD = re.compile(r"^(?:[a-zA-Z0-9_.\\/:\-]+|python|python3|uv|npx|node|deno)$")


def _validate_command(command: str) -> None:
    if Path(command).is_absolute():
        return
    if not _SAFE_CMD.match(command):
        raise McpConfigLoaderError(
            "command must be a known launcher (python, uv, ...) or an absolute path"
        )


def _validate_args(args: list[str]) -> None:
    for a in args:
        if any(ch in a for ch in ("&", "|", ";", "`", "$", "\n")):
            raise McpConfigLoaderError("args must not contain shell metacharacters")
