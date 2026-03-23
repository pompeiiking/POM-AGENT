from __future__ import annotations

import pytest

from app.config_loaders.model_provider_loader import (
    ModelProviderLoaderError,
    ModelProviderSource,
    load_model_registry,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "model_providers.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_model_registry_accepts_prompt_and_user_templates(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      prompt_profiles:
        default:
          default: "sys"
      user_prompt_profiles:
        default:
          default: "<u>{user_input}</u>"
      prompt_vars_env:
        tenant: "TENANT_ENV"
      user_prompt_vars_env:
        locale: "LOCALE_ENV"
      tool_result_render:
        default: short
      tool_first_tools:
        default: ["ping", "add"]
      user_input_max_chars: 4000
""",
    )
    reg = load_model_registry(ModelProviderSource(path=path))
    assert reg.default_provider_id == "deepseek"


def test_load_model_registry_rejects_invalid_tool_render_mode(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      tool_result_render: verbose
""",
    )
    with pytest.raises(ModelProviderLoaderError):
        load_model_registry(ModelProviderSource(path=path))


def test_load_model_registry_rejects_invalid_user_prompt_profiles_shape(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      user_prompt_profiles:
        default: 123
""",
    )
    with pytest.raises(ModelProviderLoaderError):
        load_model_registry(ModelProviderSource(path=path))


def test_load_model_registry_rejects_invalid_tool_first_tools_shape(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      tool_first_tools:
        default: ["ping", 3]
""",
    )
    with pytest.raises(ModelProviderLoaderError):
        load_model_registry(ModelProviderSource(path=path))


def test_load_model_registry_rejects_negative_user_input_max_chars(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      user_input_max_chars: -1
""",
    )
    with pytest.raises(ModelProviderLoaderError):
        load_model_registry(ModelProviderSource(path=path))

