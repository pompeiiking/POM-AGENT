from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable

from core.memory.protocol import LongTermMemoryStore, NoopLongTermMemoryStore
from infra.sqlite_long_term_memory_store import SqliteLongTermMemoryStore


class LongTermMemoryStoreRegistryError(ValueError):
    pass


LongTermMemoryStoreFactory = Callable[..., LongTermMemoryStore]


def resolve_long_term_memory_store(
    ref: str,
    *,
    memory_path: Path,
    entrypoint_group: str = "pompeii_agent.long_term_memory_stores",
    discover_fn: Callable[[str], dict[str, LongTermMemoryStoreFactory]] | None = None,
) -> LongTermMemoryStore:
    """
    旧版 `LongTermMemoryStore` 热插拔（**composition 不调用**；与 `memory_orchestrator_registry` 无关）。

    生产主线长期记忆见 `memory_policy` + `resolve_dual_memory_store`。开启 Orchestrator 时配置侧须将
    `storage_profiles.memory.store_ref` 置为 `builtin:noop`，避免与同路径双库文件冲突。

    - builtin:noop：不写库
    - builtin:sqlite：infra.SqliteLongTermMemoryStore（memory_path）
    - entrypoint:<name>：factory(memory_path: Path) -> LongTermMemoryStore
    """
    r = str(ref).strip()
    if not r:
        r = "builtin:noop"
    if r == "builtin:noop":
        return NoopLongTermMemoryStore()
    if r == "builtin:sqlite":
        return SqliteLongTermMemoryStore(memory_path)
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise LongTermMemoryStoreRegistryError("long-term memory entrypoint name must be non-empty")
        if discover_fn is not None:
            registry = discover_fn(entrypoint_group)
        else:
            registry = _discover_long_term_memory_factories(group=entrypoint_group)
        factory = registry.get(name)
        if factory is None:
            raise LongTermMemoryStoreRegistryError(
                f"long-term memory entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return factory(memory_path)
    raise LongTermMemoryStoreRegistryError(
        "long-term memory ref must be 'builtin:noop', 'builtin:sqlite', or 'entrypoint:<name>'"
    )


def _discover_long_term_memory_factories(*, group: str) -> dict[str, LongTermMemoryStoreFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, LongTermMemoryStoreFactory] = {}
    for ep in selected:
        ep_name = str(ep.name).strip()
        if not ep_name:
            raise LongTermMemoryStoreRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise LongTermMemoryStoreRegistryError(f"entry point {group}:{ep_name} is not callable")
        out[ep_name] = fn  # type: ignore[assignment]
    return out
