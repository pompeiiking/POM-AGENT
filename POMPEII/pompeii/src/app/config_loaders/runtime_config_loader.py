from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .session_config_loader import read_config_mapping


class RuntimeConfigLoaderError(ValueError):
    pass


Backend = Literal["sqlite"]


@dataclass(frozen=True)
class RuntimeConfig:
    session_backend: Backend
    """sqlite 库文件路径；相对路径相对于 `src` 根目录（与 platform_layer 并列）。"""
    sqlite_path: Path


@dataclass(frozen=True)
class RuntimeConfigSource:
    path: Path


def load_runtime_config(source: RuntimeConfigSource) -> RuntimeConfig:
    data = read_config_mapping(source.path)
    node = _require_mapping(data, "session_store")
    backend_raw = _require_str(node, "backend")
    b = backend_raw.strip().lower()
    if b != "sqlite":
        raise RuntimeConfigLoaderError(
            f"session_store.backend must be sqlite (memory backend removed; use SqliteSessionStore.ephemeral() in tests), got {backend_raw!r}"
        )

    sqlite_rel = node.get("sqlite_path", "platform_layer/resources/data/sessions.db")
    if not isinstance(sqlite_rel, str) or not sqlite_rel.strip():
        raise RuntimeConfigLoaderError("session_store.sqlite_path must be a non-empty string when present")

    return RuntimeConfig(session_backend="sqlite", sqlite_path=Path(sqlite_rel.strip()))


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise RuntimeConfigLoaderError(f"missing object field: {key}")
    return value


def _require_str(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigLoaderError(f"field must be a non-empty string: {key}")
    return value
