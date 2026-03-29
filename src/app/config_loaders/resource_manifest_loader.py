from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .session_config_loader import read_config_mapping


SUPPORTED_RESOURCE_SCHEMA_VERSIONS = {1, 2}


class ResourceManifestLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceManifestSource:
    path: Path


@dataclass(frozen=True)
class ResourceManifest:
    schema_version: int


def load_resource_manifest(source: ResourceManifestSource) -> ResourceManifest:
    data = read_config_mapping(source.path)
    raw = data.get("schema_version")
    if not isinstance(raw, int):
        raise ResourceManifestLoaderError("resource_manifest.schema_version must be integer")
    if raw not in SUPPORTED_RESOURCE_SCHEMA_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_RESOURCE_SCHEMA_VERSIONS))
        raise ResourceManifestLoaderError(
            f"resource schema_version {raw} is not supported, expected one of [{supported}]"
        )
    return ResourceManifest(schema_version=raw)
