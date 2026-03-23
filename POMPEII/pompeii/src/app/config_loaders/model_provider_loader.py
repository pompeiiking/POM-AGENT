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

