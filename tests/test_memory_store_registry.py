from __future__ import annotations

from pathlib import Path

import pytest

from app.memory_store_registry import LongTermMemoryStoreRegistryError, resolve_long_term_memory_store
from core.memory.protocol import NoopLongTermMemoryStore
from infra.sqlite_long_term_memory_store import SqliteLongTermMemoryStore


def test_resolve_builtin_noop(tmp_path: Path) -> None:
    store = resolve_long_term_memory_store("builtin:noop", memory_path=tmp_path / "m.db")
    assert isinstance(store, NoopLongTermMemoryStore)


def test_resolve_builtin_sqlite(tmp_path: Path) -> None:
    p = tmp_path / "m.db"
    store = resolve_long_term_memory_store("builtin:sqlite", memory_path=p)
    assert isinstance(store, SqliteLongTermMemoryStore)


def test_resolve_entrypoint_custom_factory(tmp_path: Path) -> None:
    p = tmp_path / "m.db"

    def factory(path: Path) -> SqliteLongTermMemoryStore:
        return SqliteLongTermMemoryStore(path)

    store = resolve_long_term_memory_store(
        "entrypoint:custom",
        memory_path=p,
        discover_fn=lambda _g: {"custom": factory},
    )
    assert isinstance(store, SqliteLongTermMemoryStore)


def test_resolve_missing_entrypoint_raises(tmp_path: Path) -> None:
    with pytest.raises(LongTermMemoryStoreRegistryError):
        resolve_long_term_memory_store("entrypoint:nope", memory_path=tmp_path / "a.db", discover_fn=lambda _g: {})
