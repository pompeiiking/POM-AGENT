from __future__ import annotations

from pathlib import Path

import pytest

from app.session_store_registry import SessionStoreRegistryError, resolve_session_store
from infra.sqlite_session_store import SqliteSessionStore


def test_resolve_builtin_sqlite(tmp_path) -> None:
    p = tmp_path / "s.db"
    store = resolve_session_store("builtin:sqlite", sqlite_path=p)
    assert isinstance(store, SqliteSessionStore)


def test_resolve_entrypoint_custom_factory(tmp_path) -> None:
    p = tmp_path / "x.db"

    def factory(path: Path) -> SqliteSessionStore:
        return SqliteSessionStore(path)

    store = resolve_session_store(
        "entrypoint:custom",
        sqlite_path=p,
        discover_fn=lambda _g: {"custom": factory},
    )
    assert isinstance(store, SqliteSessionStore)


def test_resolve_missing_entrypoint_raises(tmp_path) -> None:
    with pytest.raises(SessionStoreRegistryError):
        resolve_session_store("entrypoint:nope", sqlite_path=tmp_path / "a.db", discover_fn=lambda _g: {})
