from __future__ import annotations

import pytest

from app.config_loaders.resource_migrator import (
    ResourceMigrationError,
    migrate_resource_configs,
)


def _ensure_cfg_root(tmp_path):
    src_root = tmp_path / "src"
    cfg_root = src_root / "platform_layer" / "resources" / "config"
    cfg_root.mkdir(parents=True, exist_ok=True)
    return src_root, cfg_root


def test_migrate_resource_configs_from_0_to_current_creates_manifest(tmp_path) -> None:
    src_root, cfg_root = _ensure_cfg_root(tmp_path)
    report = migrate_resource_configs(src_root=src_root)
    assert report.from_version == 0
    assert report.to_version == 2
    manifest = cfg_root / "resource_manifest.yaml"
    assert manifest.exists()
    assert "schema_version: 2" in manifest.read_text(encoding="utf-8")


def test_migrate_resource_configs_dry_run_does_not_write(tmp_path) -> None:
    src_root, cfg_root = _ensure_cfg_root(tmp_path)
    report = migrate_resource_configs(src_root=src_root, dry_run=True)
    assert report.dry_run is True
    assert not (cfg_root / "resource_manifest.yaml").exists()


def test_migrate_resource_configs_rejects_missing_step(tmp_path) -> None:
    src_root, cfg_root = _ensure_cfg_root(tmp_path)
    (cfg_root / "resource_manifest.yaml").write_text("schema_version: 2\n", encoding="utf-8")
    with pytest.raises(ResourceMigrationError):
        migrate_resource_configs(src_root=src_root, target_version=3)


def test_migrate_resource_configs_1_to_2_rewrites_legacy_backend_alias(tmp_path) -> None:
    src_root, cfg_root = _ensure_cfg_root(tmp_path)
    (cfg_root / "resource_manifest.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (cfg_root / "model_providers.yaml").write_text(
        """
default_provider: deepseek
providers:
  deepseek:
    backend: deepseek
    params: {}
""",
        encoding="utf-8",
    )
    report = migrate_resource_configs(src_root=src_root)
    assert report.from_version == 1
    assert report.to_version == 2
    content = (cfg_root / "model_providers.yaml").read_text(encoding="utf-8")
    assert "backend: openai_compatible" in content

