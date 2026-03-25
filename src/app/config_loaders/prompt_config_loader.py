from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from modules.model.config import ModelProvider, ModelRegistry
from .session_config_loader import read_config_mapping


class PromptConfigLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class PromptConfigSource:
    path: Path


@dataclass(frozen=True)
class PromptConfig:
    provider_params: Mapping[str, Mapping[str, Any]]


def load_prompt_config(source: PromptConfigSource) -> PromptConfig:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "prompts")
    providers = _require_mapping(root, "providers")
    out: dict[str, dict[str, Any]] = {}
    for provider_id, node in providers.items():
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise PromptConfigLoaderError("prompts.providers key must be non-empty string")
        if not isinstance(node, Mapping):
            raise PromptConfigLoaderError(f"prompts.providers.{provider_id} must be mapping")
        _validate_prompt_params(provider_id=provider_id, params=node)
        out[provider_id] = dict(node)
    return PromptConfig(provider_params=out)


def merge_prompt_config_into_registry(*, registry: ModelRegistry, prompt_config: PromptConfig) -> ModelRegistry:
    merged: dict[str, ModelProvider] = {}
    for provider_id, provider in registry.providers.items():
        extra = prompt_config.provider_params.get(provider_id, {})
        params = dict(provider.params)
        params.update(dict(extra))
        merged[provider_id] = ModelProvider(
            id=provider.id,
            backend=provider.backend,
            params=params,
            failover_chain=provider.failover_chain,
        )
    # 禁止为不存在 provider 注入提示词
    unknown = set(prompt_config.provider_params.keys()) - set(registry.providers.keys())
    if unknown:
        names = ", ".join(sorted(unknown))
        raise PromptConfigLoaderError(f"prompts.providers contains unknown provider ids: {names}")
    return ModelRegistry(providers=merged, default_provider_id=registry.default_provider_id)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    v = parent.get(key)
    if not isinstance(v, Mapping):
        raise PromptConfigLoaderError(f"missing object field: {key}")
    return v


def _validate_prompt_params(*, provider_id: str, params: Mapping[str, Any]) -> None:
    _validate_prompt_profiles(provider_id=provider_id, params=params, key="prompt_profiles")
    _validate_prompt_profiles(provider_id=provider_id, params=params, key="user_prompt_profiles")
    _validate_str_mapping(provider_id=provider_id, params=params, key="prompt_vars_env")
    _validate_str_mapping(provider_id=provider_id, params=params, key="user_prompt_vars_env")
    _validate_optional_mapping(provider_id=provider_id, params=params, key="prompt_vars")
    _validate_optional_mapping(provider_id=provider_id, params=params, key="user_prompt_vars")
    _validate_tool_result_render(provider_id=provider_id, params=params)
    _validate_tool_first_tools(provider_id=provider_id, params=params)
    _validate_nonneg_int(provider_id=provider_id, params=params, key="user_input_max_chars")


def _validate_prompt_profiles(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    node = params.get(key)
    if node is None:
        return
    if not isinstance(node, Mapping):
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be mapping")
    for profile_name, profile_value in node.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise PromptConfigLoaderError(f"provider {provider_id}: {key} profile name must be non-empty string")
        if not isinstance(profile_value, Mapping):
            raise PromptConfigLoaderError(f"provider {provider_id}: {key}.{profile_name} must be strategy mapping")
        for strategy_name, strategy_text in profile_value.items():
            if not isinstance(strategy_name, str) or not strategy_name.strip():
                raise PromptConfigLoaderError(
                    f"provider {provider_id}: {key}.{profile_name} strategy name must be non-empty string"
                )
            if not isinstance(strategy_text, str) or not strategy_text.strip():
                raise PromptConfigLoaderError(
                    f"provider {provider_id}: {key}.{profile_name}.{strategy_name} must be non-empty string"
                )


def _validate_str_mapping(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    node = params.get(key)
    if node is None:
        return
    if not isinstance(node, Mapping):
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be mapping")
    for k, v in node.items():
        if not isinstance(k, str) or not k.strip():
            raise PromptConfigLoaderError(f"provider {provider_id}: {key} key must be non-empty string")
        if not isinstance(v, str) or not v.strip():
            raise PromptConfigLoaderError(f"provider {provider_id}: {key}.{k} value must be non-empty string")


def _validate_optional_mapping(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    node = params.get(key)
    if node is None:
        return
    if not isinstance(node, Mapping):
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be mapping")


def _validate_tool_result_render(*, provider_id: str, params: Mapping[str, Any]) -> None:
    key = "tool_result_render"
    node = params.get(key)
    if node is None:
        return
    valid = {"raw", "short", "short_with_reason"}
    if not isinstance(node, Mapping):
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be mapping")
    for mode_key, mode_value in node.items():
        if not isinstance(mode_key, str) or not mode_key.strip():
            raise PromptConfigLoaderError(f"provider {provider_id}: {key} mapping key must be non-empty string")
        if not isinstance(mode_value, str) or mode_value.strip().lower() not in valid:
            raise PromptConfigLoaderError(f"provider {provider_id}: {key}.{mode_key} must be one of {sorted(valid)}")


def _validate_tool_first_tools(*, provider_id: str, params: Mapping[str, Any]) -> None:
    key = "tool_first_tools"
    node = params.get(key)
    if node is None:
        return

    def _validate_names(value: Any, *, path: str) -> None:
        if not isinstance(value, list):
            raise PromptConfigLoaderError(f"provider {provider_id}: {path} must be list[str]")
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise PromptConfigLoaderError(f"provider {provider_id}: {path}[{i}] must be non-empty string")

    if not isinstance(node, Mapping):
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be mapping")
    for k, v in node.items():
        if not isinstance(k, str) or not k.strip():
            raise PromptConfigLoaderError(f"provider {provider_id}: {key} mapping key must be non-empty string")
        _validate_names(v, path=f"{key}.{k}")


def _validate_nonneg_int(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    value = params.get(key)
    if value is None:
        return
    if not isinstance(value, int) or value < 0:
        raise PromptConfigLoaderError(f"provider {provider_id}: {key} must be non-negative integer")
