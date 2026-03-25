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
        backend = _require_backend(value)
        params = _require_mapping(value, "params")
        chain = _parse_failover_chain(value, key)
        providers[key] = ModelProvider(id=key, backend=backend, params=dict(params), failover_chain=chain)
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

    for pid, prov in providers.items():
        for fid in prov.failover_chain:
            if fid not in providers:
                raise ModelProviderLoaderError(
                    f"providers.{pid}.failover_chain references unknown provider id: {fid!r}"
                )
            if fid == pid:
                raise ModelProviderLoaderError(
                    f"providers.{pid}.failover_chain must not include the provider's own id"
                )

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


def _parse_failover_chain(parent: Mapping[str, Any], provider_id: str) -> tuple[str, ...]:
    raw = parent.get("failover_chain")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ModelProviderLoaderError(f"providers.{provider_id}.failover_chain must be a list[str]")
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ModelProviderLoaderError(
                f"providers.{provider_id}.failover_chain[{i}] must be non-empty string"
            )
        out.append(item.strip())
    return tuple(out)


def _require_backend(parent: Mapping[str, Any]) -> str:
    backend = _require_str(parent, "backend").strip().lower()
    allowed = {"stub", "openai_compatible"}
    if backend not in allowed:
        names = ", ".join(sorted(allowed))
        raise ModelProviderLoaderError(f"backend must be one of [{names}], got {backend!r}")
    return backend

