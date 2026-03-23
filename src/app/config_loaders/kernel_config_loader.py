from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.kernel_config import KernelConfig
from .session_config_loader import read_config_mapping


class KernelConfigLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class KernelConfigSource:
    path: Path


def load_kernel_config(source: KernelConfigSource) -> KernelConfig:
    data = read_config_mapping(source.path)
    kernel = _require_mapping(data, "kernel")
    return KernelConfig(
        core_max_loops=_require_positive_int(kernel, "core_max_loops"),
        max_tool_calls_per_run=_require_positive_int(kernel, "max_tool_calls_per_run"),
        tool_allowlist=_require_str_list(kernel, "tool_allowlist"),
        tool_confirmation_required=_require_str_list(kernel, "tool_confirmation_required"),
    )


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise KernelConfigLoaderError(f"missing object field: {key}")
    return value


def _require_positive_int(parent: Mapping[str, Any], key: str) -> int:
    value = parent.get(key)
    if not isinstance(value, int) or value <= 0:
        raise KernelConfigLoaderError(f"field must be a positive int: {key}")
    return value


def _require_str_list(parent: Mapping[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise KernelConfigLoaderError(f"field must be a list[str]: {key}")
    items = list(value)
    if not all(isinstance(x, str) for x in items):
        raise KernelConfigLoaderError(f"field must be a list[str]: {key}")
    return items

