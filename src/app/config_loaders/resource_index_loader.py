from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .session_config_loader import read_config_mapping


class ResourceIndexLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceIndex:
    active_security_policy: str
    active_storage_profile: str
    active_resource_access_profile: str


@dataclass(frozen=True)
class ResourceIndexSource:
    path: Path


def load_resource_index(source: ResourceIndexSource) -> ResourceIndex:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "resource_index")
    return ResourceIndex(
        active_security_policy=_req_str(root, "active_security_policy"),
        active_storage_profile=_req_str(root, "active_storage_profile"),
        active_resource_access_profile=_opt_str(root, "active_resource_access_profile", default="default"),
    )


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ResourceIndexLoaderError(f"missing object field: {key}")
    return value


def _req_str(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceIndexLoaderError(f"field must be a non-empty string: {key}")
    return value.strip()


def _opt_str(parent: Mapping[str, Any], key: str, *, default: str) -> str:
    value = parent.get(key)
    if value is None:
        return default
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default

