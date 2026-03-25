from __future__ import annotations

import argparse
from pathlib import Path

from app.config_loaders.resource_migrator import (
    CURRENT_RESOURCE_SCHEMA_VERSION,
    ResourceMigrationError,
    migrate_resource_configs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pompeii-Agent 资源配置迁移器")
    parser.add_argument("--src-root", type=str, default=None, help="src 根目录，默认自动定位到当前项目的 src")
    parser.add_argument("--to", type=int, default=CURRENT_RESOURCE_SCHEMA_VERSION, help="目标 schema_version")
    parser.add_argument("--dry-run", action="store_true", help="仅预演，不写入文件")
    args = parser.parse_args()

    src_root = Path(args.src_root).resolve() if args.src_root else Path(__file__).resolve().parents[1]
    try:
        report = migrate_resource_configs(src_root=src_root, target_version=args.to, dry_run=args.dry_run)
    except ResourceMigrationError as exc:
        raise SystemExit(f"[resource_migrator] failed: {exc}")

    changed_count = len(report.changed_files)
    print(
        "[resource_migrator] ok: "
        f"{report.from_version} -> {report.to_version}, "
        f"dry_run={report.dry_run}, changed_files={changed_count}"
    )
    for p in report.changed_files:
        print(f"- {p}")


if __name__ == "__main__":
    main()

