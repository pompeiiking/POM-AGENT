from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from .session_config_loader import read_config_mapping


CURRENT_RESOURCE_SCHEMA_VERSION = 2


class ResourceMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceMigrationReport:
    from_version: int
    to_version: int
    changed_files: tuple[Path, ...]
    dry_run: bool


MigrationStep = Callable[[Path, bool], list[Path]]


def migrate_resource_configs(
    *,
    src_root: Path,
    target_version: int | None = None,
    dry_run: bool = False,
) -> ResourceMigrationReport:
    cfg_root = src_root.resolve() / "platform_layer" / "resources" / "config"
    manifest_path = cfg_root / "resource_manifest.yaml"
    start_version = _read_manifest_version_for_migration(manifest_path)
    wanted = CURRENT_RESOURCE_SCHEMA_VERSION if target_version is None else target_version
    if wanted <= 0:
        raise ResourceMigrationError("target_version must be positive integer")
    if start_version == wanted:
        return ResourceMigrationReport(
            from_version=start_version,
            to_version=wanted,
            changed_files=(),
            dry_run=dry_run,
        )
    if start_version > wanted:
        raise ResourceMigrationError(
            f"resource schema cannot downgrade: current={start_version}, target={wanted}"
        )

    changed: list[Path] = []
    current = start_version
    while current < wanted:
        step = (current, current + 1)
        runner = _MIGRATIONS.get(step)
        if runner is None:
            raise ResourceMigrationError(f"missing migration step: {current} -> {current + 1}")
        changed.extend(runner(cfg_root, dry_run))
        current += 1

    if not dry_run:
        _write_manifest(manifest_path, wanted)
        changed.append(manifest_path)

    return ResourceMigrationReport(
        from_version=start_version,
        to_version=wanted,
        changed_files=tuple(changed),
        dry_run=dry_run,
    )


def _read_manifest_version_for_migration(manifest_path: Path) -> int:
    if not manifest_path.exists():
        return 0
    data = read_config_mapping(manifest_path)
    raw = data.get("schema_version")
    if not isinstance(raw, int) or raw < 0:
        raise ResourceMigrationError("resource_manifest.schema_version must be non-negative integer")
    return raw


def _write_manifest(path: Path, version: int) -> None:
    path.write_text(f"schema_version: {version}\n", encoding="utf-8")


def _migrate_0_to_1(cfg_root: Path, dry_run: bool) -> list[Path]:
    _ = cfg_root
    _ = dry_run
    # v1 仅引入 schema manifest，本次迁移由最终写 manifest 完成。
    return []


def _migrate_1_to_2(cfg_root: Path, dry_run: bool) -> list[Path]:
    """
    v2 规范：model_providers.yaml 中 providers.*.backend 不再允许 legacy alias "deepseek"，
    统一规范为 "openai_compatible"。
    """
    target = cfg_root / "model_providers.yaml"
    if not target.exists():
        return []
    data = read_config_mapping(target)
    providers = data.get("providers")
    if not isinstance(providers, dict):
        raise ResourceMigrationError("model_providers.yaml: providers must be mapping")
    touched = False
    for node in providers.values():
        if not isinstance(node, dict):
            raise ResourceMigrationError("model_providers.yaml: providers.* must be mapping")
        backend = node.get("backend")
        if isinstance(backend, str) and backend.strip().lower() == "deepseek":
            node["backend"] = "openai_compatible"
            touched = True
    if touched and not dry_run:
        dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        target.write_text(dumped, encoding="utf-8")
        return [target]
    if touched:
        return [target]
    return []


_MIGRATIONS: dict[tuple[int, int], MigrationStep] = {
    (0, 1): _migrate_0_to_1,
    (1, 2): _migrate_1_to_2,
}

