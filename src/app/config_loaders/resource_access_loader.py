from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.resource_access import ResourceAccessProfile, ResourceAccessRule

from .session_config_loader import read_config_mapping


class ResourceAccessLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceAccessRegistry:
    profiles: Mapping[str, ResourceAccessProfile]


@dataclass(frozen=True)
class ResourceAccessSource:
    path: Path


def load_resource_access_registry(source: ResourceAccessSource) -> ResourceAccessRegistry:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "resource_access")
    profiles_raw = root.get("profiles")
    if not isinstance(profiles_raw, Mapping):
        raise ResourceAccessLoaderError("resource_access.profiles must be a mapping")
    out: dict[str, ResourceAccessProfile] = {}
    for pname, pnode in profiles_raw.items():
        if not isinstance(pname, str) or not pname.strip():
            raise ResourceAccessLoaderError("resource_access.profiles key must be non-empty string")
        if not isinstance(pnode, Mapping):
            raise ResourceAccessLoaderError(f"resource_access.profiles[{pname!r}] must be mapping")
        res_root = pnode.get("resources")
        if not isinstance(res_root, Mapping):
            raise ResourceAccessLoaderError(f"resource_access.profiles[{pname!r}].resources must be mapping")
        rules: dict[str, ResourceAccessRule] = {}
        for rid, rnode in res_root.items():
            if not isinstance(rid, str) or not rid.strip():
                raise ResourceAccessLoaderError(f"resource_access.profiles[{pname!r}].resources key invalid")
            if not isinstance(rnode, Mapping):
                raise ResourceAccessLoaderError(f"resource_access.profiles[{pname!r}].resources[{rid!r}] invalid")
            rules[rid.strip()] = ResourceAccessRule(
                read=_req_mode(rnode, "read", pname, rid),
                write=_req_mode(rnode, "write", pname, rid),
                read_requires_approval=_opt_bool(rnode, "read_requires_approval", default=False),
                write_requires_approval=_opt_bool(rnode, "write_requires_approval", default=False),
            )
        out[pname.strip()] = ResourceAccessProfile(rules=rules)
    if not out:
        raise ResourceAccessLoaderError("resource_access.profiles must be non-empty")
    return ResourceAccessRegistry(profiles=out)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ResourceAccessLoaderError(f"missing object field: {key}")
    return value


def _req_mode(parent: Mapping[str, Any], key: str, profile: str, resource: str) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or v.strip().lower() not in ("allow", "deny"):
        raise ResourceAccessLoaderError(
            f"resource_access.profiles[{profile!r}].resources[{resource!r}].{key} must be allow|deny"
        )
    return v.strip().lower()


def _opt_bool(parent: Mapping[str, Any], key: str, *, default: bool) -> bool:
    v = parent.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    raise ResourceAccessLoaderError(f"{key} must be boolean when present")
