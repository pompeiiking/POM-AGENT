from __future__ import annotations

import pytest

from app.config_loaders.resource_manifest_loader import (
    ResourceManifestLoaderError,
    ResourceManifestSource,
    load_resource_manifest,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "resource_manifest.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_resource_manifest_ok(tmp_path) -> None:
    p = _write_yaml(tmp_path, "schema_version: 1\n")
    manifest = load_resource_manifest(ResourceManifestSource(path=p))
    assert manifest.schema_version == 1


def test_load_resource_manifest_rejects_unsupported_version(tmp_path) -> None:
    p = _write_yaml(tmp_path, "schema_version: 99\n")
    with pytest.raises(ResourceManifestLoaderError):
        load_resource_manifest(ResourceManifestSource(path=p))
