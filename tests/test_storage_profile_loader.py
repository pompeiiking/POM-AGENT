from __future__ import annotations

import pytest

from app.config_loaders.storage_profile_loader import (
    StorageProfileLoaderError,
    StorageProfileSource,
    load_storage_profile_registry,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "storage_profiles.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_storage_profile_registry_ok(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
storage_profiles:
  items:
    - id: "default"
      archive:
        backend: "sqlite"
        path: "platform_layer/resources/data/sessions.db"
      memory:
        backend: "sqlite"
        path: "platform_layer/resources/data/memory.db"
""",
    )
    reg = load_storage_profile_registry(StorageProfileSource(path=p))
    assert "default" in reg.profiles


def test_load_storage_profile_registry_rejects_unsupported_backend(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
storage_profiles:
  items:
    - id: "default"
      archive:
        backend: "postgres"
        path: "x"
      memory:
        backend: "sqlite"
        path: "y"
""",
    )
    with pytest.raises(StorageProfileLoaderError):
        load_storage_profile_registry(StorageProfileSource(path=p))
