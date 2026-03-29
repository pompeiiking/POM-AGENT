from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.kernel_config import KernelConfig
from .session_config_loader import read_config_mapping

_DELEGATE_TARGET_TOKEN = re.compile(r"^[a-zA-Z0-9_.-]+$")


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
        archive_llm_summary_enabled=_opt_bool(kernel, "archive_llm_summary_enabled", default=False),
        archive_llm_summary_provider_id=_opt_str(kernel, "archive_llm_summary_provider_id", default=""),
        archive_llm_summary_max_dialogue_chars=_opt_positive_int(
            kernel, "archive_llm_summary_max_dialogue_chars", default=12000
        ),
        archive_llm_summary_max_output_chars=_opt_positive_int(
            kernel, "archive_llm_summary_max_output_chars", default=2000
        ),
        archive_llm_summary_system_prompt=_opt_str(kernel, "archive_llm_summary_system_prompt", default=""),
        context_isolation_enabled=_opt_bool(kernel, "context_isolation_enabled", default=True),
        tool_policy_engine_ref=_opt_str(kernel, "tool_policy_engine_ref", default="builtin:default"),
        loop_policy_engine_ref=_opt_str(kernel, "loop_policy_engine_ref", default="builtin:default"),
        prompt_strategy_ref=_opt_str(kernel, "prompt_strategy_ref", default="builtin:none"),
        delegate_target_allowlist=_opt_delegate_target_allowlist(kernel),
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


def _opt_bool(parent: Mapping[str, Any], key: str, *, default: bool) -> bool:
    v = parent.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    raise KernelConfigLoaderError(f"field must be boolean when present: {key}")


def _opt_str(parent: Mapping[str, Any], key: str, *, default: str) -> str:
    v = parent.get(key)
    if v is None:
        return default
    if isinstance(v, str):
        return v
    raise KernelConfigLoaderError(f"field must be string when present: {key}")


def _opt_delegate_target_allowlist(parent: Mapping[str, Any]) -> tuple[str, ...]:
    v = parent.get("delegate_target_allowlist")
    if v is None:
        return ()
    if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
        raise KernelConfigLoaderError("field must be a list[str]: delegate_target_allowlist")
    out: list[str] = []
    for i, x in enumerate(v):
        if not isinstance(x, str) or not x.strip():
            raise KernelConfigLoaderError(f"delegate_target_allowlist[{i}] must be non-empty string")
        t = x.strip()
        if not _DELEGATE_TARGET_TOKEN.fullmatch(t):
            raise KernelConfigLoaderError(
                f"delegate_target_allowlist[{i}]={t!r} must match [a-zA-Z0-9_.-]+"
            )
        out.append(t)
    return tuple(out)


def _opt_positive_int(parent: Mapping[str, Any], key: str, *, default: int) -> int:
    v = parent.get(key)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, int):
        raise KernelConfigLoaderError(f"field must be positive int when present: {key}")
    if v <= 0:
        raise KernelConfigLoaderError(f"field must be positive int when present: {key}")
    return v

