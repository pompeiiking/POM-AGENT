from __future__ import annotations

import pytest

from app.config_loaders.resource_index_loader import (
    ResourceIndexLoaderError,
    ResourceIndexSource,
    load_resource_index,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "resource_index.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_resource_index_ok(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
resource_index:
  active_security_policy: "baseline"
  active_storage_profile: "default"
""",
    )
    idx = load_resource_index(ResourceIndexSource(path=p))
    assert idx.active_security_policy == "baseline"


def test_load_resource_index_rejects_missing_field(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
resource_index:
  active_security_policy: "baseline"
""",
    )
    with pytest.raises(ResourceIndexLoaderError):
        load_resource_index(ResourceIndexSource(path=p))
