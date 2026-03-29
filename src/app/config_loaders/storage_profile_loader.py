from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .session_config_loader import read_config_mapping


class StorageProfileLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class StorageProfile:
    id: str
    archive_backend: str
    archive_path: Path
    archive_store_ref: str
    memory_backend: str
    memory_path: Path
    memory_store_ref: str


@dataclass(frozen=True)
class StorageProfileRegistry:
    profiles: Mapping[str, StorageProfile]


@dataclass(frozen=True)
class StorageProfileSource:
    path: Path


def load_storage_profile_registry(source: StorageProfileSource) -> StorageProfileRegistry:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "storage_profiles")
    items = root.get("items")
    if not isinstance(items, list):
        raise StorageProfileLoaderError("storage_profiles.items must be a list")
    out: dict[str, StorageProfile] = {}
    for i, raw in enumerate(items):
        if not isinstance(raw, Mapping):
            raise StorageProfileLoaderError(f"storage_profiles.items[{i}] must be mapping")
        sid = _req_str(raw, "id", i)
        if sid in out:
            raise StorageProfileLoaderError(f"duplicate storage profile id: {sid}")
        archive = _require_mapping(raw, "archive")
        memory = _require_mapping(raw, "memory")
        archive_ref = _resolve_store_ref(archive, i, "archive")
        memory_ref = _resolve_store_ref(memory, i, "memory")
        out[sid] = StorageProfile(
            id=sid,
            archive_backend=_req_enum(archive, "backend", i, {"sqlite"}),
            archive_path=Path(_req_str(archive, "path", i)),
            archive_store_ref=archive_ref,
            memory_backend=_req_enum(memory, "backend", i, {"sqlite"}),
            memory_path=Path(_req_str(memory, "path", i)),
            memory_store_ref=memory_ref,
        )
    return StorageProfileRegistry(profiles=out)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise StorageProfileLoaderError(f"missing object field: {key}")
    return value


def _req_str(parent: Mapping[str, Any], key: str, i: int) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageProfileLoaderError(f"storage_profiles.items[{i}].{key} must be non-empty string")
    return value.strip()


def _req_enum(parent: Mapping[str, Any], key: str, i: int, allowed: set[str]) -> str:
    value = _req_str(parent, key, i).lower()
    if value not in allowed:
        names = ", ".join(sorted(allowed))
        raise StorageProfileLoaderError(f"storage_profiles.items[{i}].{key} must be one of [{names}]")
    return value


def _resolve_store_ref(node: Mapping[str, Any], i: int, section: str) -> str:
    raw = node.get("store_ref")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    backend = node.get("backend")
    if isinstance(backend, str) and backend.strip().lower() == "sqlite":
        return "builtin:sqlite"
    raise StorageProfileLoaderError(
        f"storage_profiles.items[{i}].{section} must set store_ref or backend=sqlite"
    )

