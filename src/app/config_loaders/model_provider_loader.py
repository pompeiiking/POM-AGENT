from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from modules.model.config import ModelProvider, ModelRegistry
from .session_config_loader import read_config_mapping


class ModelProviderLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class ModelProviderSource:
    path: Path


def load_model_registry(source: ModelProviderSource) -> ModelRegistry:
    data = read_config_mapping(source.path)
    providers_node = _require_mapping(data, "providers")
    providers: dict[str, ModelProvider] = {}
    for key, value in providers_node.items():
        if not isinstance(value, Mapping):
            raise ModelProviderLoaderError(f"provider config must be mapping: {key}")
        backend = _require_str(value, "backend")
        params = _require_mapping(value, "params")
        _validate_provider_params(provider_id=key, params=params)
        providers[key] = ModelProvider(id=key, backend=backend, params=dict(params))
    if not providers:
        raise ModelProviderLoaderError("providers must not be empty")

    default_raw = data.get("default_provider")
    if isinstance(default_raw, str) and default_raw.strip():
        default_id = default_raw.strip()
    elif len(providers) == 1:
        default_id = next(iter(providers.keys()))
    else:
        raise ModelProviderLoaderError(
            "default_provider is required when multiple providers are defined in model_providers.yaml"
        )

    if default_id not in providers:
        raise ModelProviderLoaderError(f"default_provider {default_id!r} is not defined under providers")

    return ModelRegistry(providers=providers, default_provider_id=default_id)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ModelProviderLoaderError(f"missing object field: {key}")
    return value


def _require_str(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value:
        raise ModelProviderLoaderError(f"field must be a non-empty string: {key}")
    return value


def _validate_provider_params(*, provider_id: str, params: Mapping[str, Any]) -> None:
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
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be mapping")
    for profile_name, profile_value in node.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ModelProviderLoaderError(f"provider {provider_id}: {key} profile name must be non-empty string")
        if isinstance(profile_value, str):
            if not profile_value.strip():
                raise ModelProviderLoaderError(f"provider {provider_id}: {key}.{profile_name} text must be non-empty")
            continue
        if not isinstance(profile_value, Mapping):
            raise ModelProviderLoaderError(f"provider {provider_id}: {key}.{profile_name} must be string or mapping")
        for strategy_name, strategy_text in profile_value.items():
            if not isinstance(strategy_name, str) or not strategy_name.strip():
                raise ModelProviderLoaderError(
                    f"provider {provider_id}: {key}.{profile_name} strategy name must be non-empty string"
                )
            if not isinstance(strategy_text, str) or not strategy_text.strip():
                raise ModelProviderLoaderError(
                    f"provider {provider_id}: {key}.{profile_name}.{strategy_name} must be non-empty string"
                )


def _validate_str_mapping(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    node = params.get(key)
    if node is None:
        return
    if not isinstance(node, Mapping):
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be mapping")
    for k, v in node.items():
        if not isinstance(k, str) or not k.strip():
            raise ModelProviderLoaderError(f"provider {provider_id}: {key} key must be non-empty string")
        if not isinstance(v, str) or not v.strip():
            raise ModelProviderLoaderError(f"provider {provider_id}: {key}.{k} value must be non-empty string")


def _validate_optional_mapping(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    node = params.get(key)
    if node is None:
        return
    if not isinstance(node, Mapping):
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be mapping")


def _validate_tool_result_render(*, provider_id: str, params: Mapping[str, Any]) -> None:
    key = "tool_result_render"
    node = params.get(key)
    if node is None:
        return
    valid = {"raw", "short", "short_with_reason"}
    if isinstance(node, str):
        if node.strip().lower() not in valid:
            raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be one of {sorted(valid)}")
        return
    if not isinstance(node, Mapping):
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be string or mapping")
    for mode_key, mode_value in node.items():
        if not isinstance(mode_key, str) or not mode_key.strip():
            raise ModelProviderLoaderError(f"provider {provider_id}: {key} mapping key must be non-empty string")
        if not isinstance(mode_value, str) or mode_value.strip().lower() not in valid:
            raise ModelProviderLoaderError(f"provider {provider_id}: {key}.{mode_key} must be one of {sorted(valid)}")


def _validate_tool_first_tools(*, provider_id: str, params: Mapping[str, Any]) -> None:
    key = "tool_first_tools"
    node = params.get(key)
    if node is None:
        return

    def _validate_names(value: Any, *, path: str) -> None:
        if not isinstance(value, list):
            raise ModelProviderLoaderError(f"provider {provider_id}: {path} must be list[str]")
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ModelProviderLoaderError(f"provider {provider_id}: {path}[{i}] must be non-empty string")

    if isinstance(node, list):
        _validate_names(node, path=key)
        return
    if not isinstance(node, Mapping):
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be list[str] or mapping")
    for k, v in node.items():
        if not isinstance(k, str) or not k.strip():
            raise ModelProviderLoaderError(f"provider {provider_id}: {key} mapping key must be non-empty string")
        _validate_names(v, path=f"{key}.{k}")


def _validate_nonneg_int(*, provider_id: str, params: Mapping[str, Any], key: str) -> None:
    value = params.get(key)
    if value is None:
        return
    if not isinstance(value, int) or value < 0:
        raise ModelProviderLoaderError(f"provider {provider_id}: {key} must be non-negative integer")

