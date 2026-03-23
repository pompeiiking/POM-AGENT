from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

try:
    import yaml  # 需要安装 PyYAML 才能使用 YAML
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from core.session.session import SessionConfig, SessionLimits


class SessionConfigLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class SessionConfigSource:
    path: Path


def load_session_config(source: SessionConfigSource) -> SessionConfig:
    config_data = read_config_mapping(source.path)
    session_node = _require_mapping(config_data, "session")
    limits_data = _require_mapping(session_node, "limits")

    limits = SessionLimits(
        max_tokens=_require_positive_int(limits_data, "max_tokens"),
        max_context_window=_require_positive_int(limits_data, "max_context_window"),
        max_loops=_require_positive_int(limits_data, "max_loops"),
        timeout_seconds=_require_positive_float(limits_data, "timeout_seconds"),
        assembly_tail_messages=_optional_positive_int(limits_data, "assembly_tail_messages", default=20),
        summary_tail_messages=_optional_positive_int(limits_data, "summary_tail_messages", default=12),
        summary_excerpt_chars=_optional_positive_int(limits_data, "summary_excerpt_chars", default=200),
        assembly_message_max_chars=_optional_nonneg_int(limits_data, "assembly_message_max_chars", default=0),
        assembly_approx_context_tokens=_optional_nonneg_int(limits_data, "assembly_approx_context_tokens", default=0),
    )

    return SessionConfig(
        model=_require_non_empty_str(session_node, "model"),
        skills=_require_str_list(session_node, "skills"),
        security=_require_non_empty_str(session_node, "security"),
        limits=limits,
        prompt_profile=_optional_non_empty_str(session_node, "prompt_profile", default="default"),
        prompt_strategy=_optional_non_empty_str(session_node, "prompt_strategy", default="default"),
    )


ConfigReader = Callable[[Path], Mapping[str, Any]]


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SessionConfigLoaderError(f"invalid json: {path}: {e}") from e
    if not isinstance(data, dict):
        raise SessionConfigLoaderError(f"json root must be an object: {path}")
    return data


def _read_toml(path: Path) -> Mapping[str, Any]:
    if tomllib is None:
        raise SessionConfigLoaderError("tomllib is not available in this python runtime")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SessionConfigLoaderError(f"invalid toml: {path}: {e}") from e
    if not isinstance(data, dict):
        raise SessionConfigLoaderError(f"toml root must be a table/object: {path}")
    return data


def _read_yaml(path: Path) -> Mapping[str, Any]:
    if yaml is None:
        raise SessionConfigLoaderError("PyYAML is not available for yaml config")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SessionConfigLoaderError(f"invalid yaml: {path}: {e}") from e
    if not isinstance(data, dict):
        raise SessionConfigLoaderError(f"yaml root must be a mapping: {path}")
    return data


_READERS: Mapping[str, ConfigReader] = {
    ".json": _read_json,
    ".toml": _read_toml,
    ".yaml": _read_yaml,
    ".yml": _read_yaml,
}


def read_config_mapping(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise SessionConfigLoaderError(f"config file not found: {path}")

    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise SessionConfigLoaderError(f"unsupported config format: {suffix} ({path})")

    return reader(path)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise SessionConfigLoaderError(f"missing object field: {key}")
    return value


def _require_non_empty_str(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SessionConfigLoaderError(f"field must be a non-empty string: {key}")
    return value


def _require_str_list(parent: Mapping[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SessionConfigLoaderError(f"field must be a list[str]: {key}")
    items = list(value)
    if not all(isinstance(x, str) for x in items):
        raise SessionConfigLoaderError(f"field must be a list[str]: {key}")
    return items


def _require_positive_int(parent: Mapping[str, Any], key: str) -> int:
    value = parent.get(key)
    if not isinstance(value, int) or value <= 0:
        raise SessionConfigLoaderError(f"field must be a positive int: {key}")
    return value


def _require_positive_float(parent: Mapping[str, Any], key: str) -> float:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or float(value) <= 0:
        raise SessionConfigLoaderError(f"field must be a positive number: {key}")
    return float(value)


def _optional_positive_int(parent: Mapping[str, Any], key: str, *, default: int) -> int:
    if key not in parent:
        return default
    value = parent.get(key)
    if not isinstance(value, int) or value <= 0:
        raise SessionConfigLoaderError(f"field must be a positive int: {key}")
    return value


def _optional_nonneg_int(parent: Mapping[str, Any], key: str, *, default: int) -> int:
    """0 表示关闭（如组装部单条消息字符上限）。"""
    if key not in parent:
        return default
    value = parent.get(key)
    if not isinstance(value, int) or value < 0:
        raise SessionConfigLoaderError(f"field must be a non-negative int: {key}")
    return value


def _optional_non_empty_str(parent: Mapping[str, Any], key: str, *, default: str) -> str:
    if key not in parent:
        return default
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SessionConfigLoaderError(f"field must be a non-empty string: {key}")
    return value.strip()

