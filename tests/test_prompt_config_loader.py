from __future__ import annotations

import pytest

from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.prompt_config_loader import (
    PromptConfigLoaderError,
    PromptConfigSource,
    load_prompt_config,
    merge_prompt_config_into_registry,
)


def _write(path, text: str):
    path.write_text(text, encoding="utf-8")
    return path


def test_load_prompt_config_and_merge_into_registry(tmp_path) -> None:
    mp = _write(
        tmp_path / "model_providers.yaml",
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      model: "deepseek-chat"
""",
    )
    pp = _write(
        tmp_path / "prompts.yaml",
        """
prompts:
  providers:
    deepseek:
      prompt_profiles:
        default:
          default: "sys"
      tool_result_render:
        default: short
""",
    )
    reg = load_model_registry(ModelProviderSource(path=mp))
    prompt_cfg = load_prompt_config(PromptConfigSource(path=pp))
    merged = merge_prompt_config_into_registry(registry=reg, prompt_config=prompt_cfg)
    assert "prompt_profiles" in merged.providers["deepseek"].params
    assert merged.providers["deepseek"].params["tool_result_render"]["default"] == "short"


def test_load_prompt_config_rejects_invalid_render_mode(tmp_path) -> None:
    pp = _write(
        tmp_path / "prompts.yaml",
        """
prompts:
  providers:
    deepseek:
      tool_result_render: verbose
""",
    )
    with pytest.raises(PromptConfigLoaderError):
        load_prompt_config(PromptConfigSource(path=pp))


def test_load_prompt_config_rejects_string_profile_legacy_shape(tmp_path) -> None:
    pp = _write(
        tmp_path / "prompts.yaml",
        """
prompts:
  providers:
    deepseek:
      prompt_profiles:
        default: "legacy text"
""",
    )
    with pytest.raises(PromptConfigLoaderError):
        load_prompt_config(PromptConfigSource(path=pp))


def test_load_prompt_config_rejects_string_tool_result_render_legacy_shape(tmp_path) -> None:
    pp = _write(
        tmp_path / "prompts.yaml",
        """
prompts:
  providers:
    deepseek:
      tool_result_render: short
""",
    )
    with pytest.raises(PromptConfigLoaderError):
        load_prompt_config(PromptConfigSource(path=pp))


def test_merge_prompt_config_rejects_unknown_provider(tmp_path) -> None:
    mp = _write(
        tmp_path / "model_providers.yaml",
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params: {}
""",
    )
    pp = _write(
        tmp_path / "prompts.yaml",
        """
prompts:
  providers:
    openai:
      prompt_profiles:
        default:
          default: "sys"
""",
    )
    reg = load_model_registry(ModelProviderSource(path=mp))
    prompt_cfg = load_prompt_config(PromptConfigSource(path=pp))
    with pytest.raises(PromptConfigLoaderError):
        merge_prompt_config_into_registry(registry=reg, prompt_config=prompt_cfg)
