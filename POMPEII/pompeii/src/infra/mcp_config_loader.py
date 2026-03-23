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


@dataclass(frozen=True)
class McpConfigSource:
    path: Path


def load_mcp_config(source: McpConfigSource, *, src_root: Path) -> McpRuntimeConfig:
    if yaml is None:
        raise McpConfigLoaderError("PyYAML is required for mcp_servers.yaml")
    if not source.path.exists():
        return McpRuntimeConfig(enabled=False, servers=())

    raw = yaml.safe_load(source.path.read_text(encoding="utf-8"))
    if raw is None:
        return McpRuntimeConfig(enabled=False, servers=())
    if not isinstance(raw, dict):
        raise McpConfigLoaderError("mcp_servers.yaml root must be a mapping")

    enabled = bool(raw.get("enabled", False))
    servers_raw = raw.get("servers")
    if servers_raw is None:
        return McpRuntimeConfig(enabled=enabled, servers=())
    if not isinstance(servers_raw, list):
        raise McpConfigLoaderError("servers must be a list")

    servers: list[McpServerEntry] = []
    root_s = str(src_root.resolve())
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

    return McpRuntimeConfig(enabled=enabled, servers=tuple(servers))


def _require_str(parent: Mapping[str, Any], key: str) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or not v.strip():
        raise McpConfigLoaderError(f"missing non-empty string: {key}")
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
