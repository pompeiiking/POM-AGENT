from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .session_config_loader import read_config_mapping


class RuntimeConfigLoaderError(ValueError):
    pass


Backend = Literal["sqlite"]
PendingStateBackend = Literal["memory", "sqlite_shared"]


@dataclass(frozen=True)
class RuntimeConfig:
    """
    - ``sqlite_path``：相对路径相对于 ``src`` 根目录（与 platform_layer 并列）。
    - ``port_interaction_mode_ref``：见 ``app.port_mode_registry``；CLI 用。
    """

    session_backend: Backend
    sqlite_path: Path
    port_interaction_mode_ref: str = "builtin:cli"
    pending_state_backend: PendingStateBackend = "memory"
    pending_state_sqlite_path: Path = Path("platform_layer/resources/data/port_pending.db")


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

    port_ref = "builtin:cli"
    port_raw = data.get("port")
    if port_raw is not None:
        if not isinstance(port_raw, Mapping):
            raise RuntimeConfigLoaderError("port must be a mapping when present")
        im = port_raw.get("interaction_mode_ref")
        if im is not None:
            if not isinstance(im, str) or not im.strip():
                raise RuntimeConfigLoaderError("port.interaction_mode_ref must be a non-empty string when present")
            port_ref = im.strip()

    pending_backend: PendingStateBackend = "memory"
    pending_sqlite_rel = "platform_layer/resources/data/port_pending.db"
    if port_raw is not None:
        pb = port_raw.get("pending_state_backend")
        if pb is not None:
            if not isinstance(pb, str) or pb.strip() not in ("memory", "sqlite_shared"):
                raise RuntimeConfigLoaderError("port.pending_state_backend must be memory|sqlite_shared")
            pending_backend = pb.strip()  # type: ignore[assignment]
        psp = port_raw.get("pending_state_sqlite_path")
        if psp is not None:
            if not isinstance(psp, str) or not psp.strip():
                raise RuntimeConfigLoaderError("port.pending_state_sqlite_path must be non-empty string")
            pending_sqlite_rel = psp.strip()

    return RuntimeConfig(
        session_backend="sqlite",
        sqlite_path=Path(sqlite_rel.strip()),
        port_interaction_mode_ref=port_ref,
        pending_state_backend=pending_backend,
        pending_state_sqlite_path=Path(pending_sqlite_rel),
    )


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
