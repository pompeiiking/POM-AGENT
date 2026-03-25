from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable

from core.session.session_store import SessionStore
from infra.sqlite_session_store import SqliteSessionStore


class SessionStoreRegistryError(ValueError):
    pass


SessionStoreFactory = Callable[..., SessionStore]


def resolve_session_store(
    ref: str,
    *,
    sqlite_path: Path,
    entrypoint_group: str = "pompeii_agent.session_stores",
    discover_fn: Callable[[str], dict[str, SessionStoreFactory]] | None = None,
) -> SessionStore:
    """
    会话存储热插拔入口。
    - builtin:sqlite：默认 SQLite 实现（与 infra.SqliteSessionStore 一致）
    - entrypoint:<name>：从 entry_points 加载工厂，签名为 factory(sqlite_path: Path) -> SessionStore
    """
    r = str(ref).strip()
    if not r:
        r = "builtin:sqlite"
    if r == "builtin:sqlite":
        return SqliteSessionStore(sqlite_path)
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise SessionStoreRegistryError("session store entrypoint name must be non-empty")
        if discover_fn is not None:
            registry = discover_fn(entrypoint_group)
        else:
            registry = _discover_session_store_factories(group=entrypoint_group)
        factory = registry.get(name)
        if factory is None:
            raise SessionStoreRegistryError(
                f"session store entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return factory(sqlite_path)
    raise SessionStoreRegistryError("session store ref must be 'builtin:sqlite' or 'entrypoint:<name>'")


def _discover_session_store_factories(*, group: str) -> dict[str, SessionStoreFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, SessionStoreFactory] = {}
    for ep in selected:
        name = str(ep.name).strip()
        if not name:
            raise SessionStoreRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise SessionStoreRegistryError(f"entry point {group}:{name} is not callable")
        out[name] = fn  # type: ignore[assignment]
    return out
