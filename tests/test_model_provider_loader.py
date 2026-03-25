from __future__ import annotations

from app.config_loaders.model_provider_loader import (
    ModelProviderLoaderError,
    ModelProviderSource,
    load_model_registry,
)
import pytest


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "model_providers.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_model_registry_accepts_minimal_provider_config(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      base_url: "https://api.deepseek.com"
      model: "deepseek-chat"
""",
    )
    reg = load_model_registry(ModelProviderSource(path=path))
    assert reg.default_provider_id == "deepseek"


def test_load_model_registry_rejects_legacy_backend_alias(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: deepseek
    params: {}
""",
    )
    with pytest.raises(ModelProviderLoaderError):
        load_model_registry(ModelProviderSource(path=path))

