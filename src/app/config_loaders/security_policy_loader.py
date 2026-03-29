from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .session_config_loader import read_config_mapping


class SecurityPolicyLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class SecurityPolicySpec:
    id: str
    input_max_chars: int
    max_requests_per_minute: int
    guard_enabled: bool
    default_tool_risk_level: str
    tool_confirmation_level: str
    tool_risk_overrides: Mapping[str, str]
    guard_block_patterns: tuple[str, ...]
    guard_tool_output_redaction: str
    guard_evaluator_ref: str
    guard_model_ref: str
    guard_model_provider_id: str | None
    # 关卡④-c：工具结果写入会话前截断（0 表示关闭）；与 guard 独立，先于模式/守卫模型检测执行
    tool_output_max_chars: int = 0
    tool_output_truncation_marker: str = "…[truncated]"
    # 按工具名覆盖 tool_output_max_chars；键存在时优先（值为 0 表示该工具不截断）
    tool_output_max_chars_overrides: Mapping[str, int] = field(default_factory=dict)
    # 以下为信任分级截断：仅当 tool_output_max_chars_by_trust 非空时生效；与全局/按工具上限合并为 min（单边为 0 表示该侧不限制）
    default_tool_output_trust: str = "high"
    tool_output_trust_overrides: Mapping[str, str] = field(default_factory=dict)
    mcp_tool_output_trust: str = "low"
    # Port /device_result 回传写入会话前的信任档（与 mcp 独立可配）
    device_tool_output_trust: str = "low"
    # source=http_fetch（如 http_get）时的信任档，用于 tool_output_max_chars_by_trust
    http_fetch_tool_output_trust: str = "low"
    tool_output_max_chars_by_trust: Mapping[str, int] = field(default_factory=dict)
    # 关卡④-c：仅针对工具结果串的注入特征（子串匹配，小写）；在截断之后、guard_block_patterns 之前执行
    tool_output_injection_patterns: tuple[str, ...] = ()
    tool_output_injection_redaction: str = "[tool_output_injection_blocked]"


@dataclass(frozen=True)
class SecurityPolicyRegistry:
    policies: Mapping[str, SecurityPolicySpec]


@dataclass(frozen=True)
class SecurityPolicySource:
    path: Path


def load_security_policy_registry(source: SecurityPolicySource) -> SecurityPolicyRegistry:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "security_policies")
    items = root.get("items")
    if not isinstance(items, list):
        raise SecurityPolicyLoaderError("security_policies.items must be a list")
    out: dict[str, SecurityPolicySpec] = {}
    for i, raw in enumerate(items):
        if not isinstance(raw, Mapping):
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}] must be mapping")
        sid = _req_str(raw, "id", i)
        if sid in out:
            raise SecurityPolicyLoaderError(f"duplicate security policy id: {sid}")
        out[sid] = SecurityPolicySpec(
            id=sid,
            input_max_chars=_req_pos_int(raw, "input_max_chars", i),
            max_requests_per_minute=_req_pos_int(raw, "max_requests_per_minute", i),
            guard_enabled=_req_bool(raw, "guard_enabled", i),
            default_tool_risk_level=_req_enum(raw, "default_tool_risk_level", i, {"low", "medium", "high"}),
            tool_confirmation_level=_req_enum(raw, "tool_confirmation_level", i, {"low", "medium", "high"}),
            tool_risk_overrides=_req_risk_mapping(raw, "tool_risk_overrides", i),
            guard_block_patterns=_req_optional_pattern_list(raw, "guard_block_patterns", i),
            guard_tool_output_redaction=_req_optional_str(
                raw,
                "guard_tool_output_redaction",
                i,
                default="[guard_blocked_tool_output]",
            ),
            guard_evaluator_ref=_req_optional_str(raw, "guard_evaluator_ref", i, default="builtin:default"),
            guard_model_ref=_req_optional_str(raw, "guard_model_ref", i, default="builtin:none"),
            guard_model_provider_id=_req_optional_provider_id(raw, "guard_model_provider_id", i),
            tool_output_max_chars=_opt_nonneg_int(raw, "tool_output_max_chars", i, default=0),
            tool_output_truncation_marker=_opt_str_with_default(
                raw, "tool_output_truncation_marker", i, default="…[truncated]"
            ),
            tool_output_max_chars_overrides=_req_nonneg_int_mapping(
                raw, "tool_output_max_chars_overrides", i
            ),
            default_tool_output_trust=_opt_trust_level(
                raw, "default_tool_output_trust", i, default="high"
            ),
            tool_output_trust_overrides=_req_tool_output_trust_mapping(
                raw, "tool_output_trust_overrides", i
            ),
            mcp_tool_output_trust=_opt_trust_level(raw, "mcp_tool_output_trust", i, default="low"),
            device_tool_output_trust=_opt_trust_level(raw, "device_tool_output_trust", i, default="low"),
            http_fetch_tool_output_trust=_opt_trust_level(
                raw, "http_fetch_tool_output_trust", i, default="low"
            ),
            tool_output_max_chars_by_trust=_req_trust_level_nonneg_caps(
                raw, "tool_output_max_chars_by_trust", i
            ),
            tool_output_injection_patterns=_req_optional_pattern_list(
                raw, "tool_output_injection_patterns", i
            ),
            tool_output_injection_redaction=_req_optional_str(
                raw,
                "tool_output_injection_redaction",
                i,
                default="[tool_output_injection_blocked]",
            ),
        )
    return SecurityPolicyRegistry(policies=out)


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise SecurityPolicyLoaderError(f"missing object field: {key}")
    return value


def _req_str(parent: Mapping[str, Any], key: str, i: int) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be non-empty string")
    return value.strip()


def _req_pos_int(parent: Mapping[str, Any], key: str, i: int) -> int:
    value = parent.get(key)
    if not isinstance(value, int) or value <= 0:
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be positive int")
    return value


def _req_bool(parent: Mapping[str, Any], key: str, i: int) -> bool:
    value = parent.get(key)
    if not isinstance(value, bool):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be boolean")
    return value


def _req_enum(parent: Mapping[str, Any], key: str, i: int, allowed: set[str]) -> str:
    value = _req_str(parent, key, i).lower()
    if value not in allowed:
        names = ", ".join(sorted(allowed))
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be one of [{names}]")
    return value


_TRUST_LEVELS = frozenset({"low", "medium", "high"})


def _opt_trust_level(parent: Mapping[str, Any], key: str, i: int, *, default: str) -> str:
    if key not in parent:
        return default
    return _req_enum(parent, key, i, set(_TRUST_LEVELS))


def _req_tool_output_trust_mapping(parent: Mapping[str, Any], key: str, i: int) -> Mapping[str, str]:
    raw = parent.get(key, {})
    if not isinstance(raw, Mapping):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be mapping")
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} key must be non-empty string")
        if not isinstance(v, str) or v.strip().lower() not in _TRUST_LEVELS:
            names = ", ".join(sorted(_TRUST_LEVELS))
            raise SecurityPolicyLoaderError(
                f"security_policies.items[{i}].{key}.{k} must be one of [{names}]"
            )
        out[k.strip()] = v.strip().lower()
    return out


def _req_trust_level_nonneg_caps(parent: Mapping[str, Any], key: str, i: int) -> Mapping[str, int]:
    raw = parent.get(key, {})
    if not isinstance(raw, Mapping):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be mapping")
    out: dict[str, int] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} key must be non-empty string")
        kk = k.strip().lower()
        if kk not in _TRUST_LEVELS:
            names = ", ".join(sorted(_TRUST_LEVELS))
            raise SecurityPolicyLoaderError(
                f"security_policies.items[{i}].{key} keys must be one of [{names}]"
            )
        if isinstance(v, bool) or not isinstance(v, int):
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}.{k} must be int")
        if v < 0:
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}.{k} must be non-negative")
        out[kk] = v
    return out


def _req_nonneg_int_mapping(parent: Mapping[str, Any], key: str, i: int) -> Mapping[str, int]:
    raw = parent.get(key, {})
    if not isinstance(raw, Mapping):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be mapping")
    out: dict[str, int] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} key must be non-empty string")
        if isinstance(v, bool) or not isinstance(v, int):
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}.{k} must be int")
        if v < 0:
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}.{k} must be non-negative")
        out[k.strip()] = v
    return out


def _req_risk_mapping(parent: Mapping[str, Any], key: str, i: int) -> Mapping[str, str]:
    raw = parent.get(key, {})
    if not isinstance(raw, Mapping):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be mapping")
    out: dict[str, str] = {}
    allowed = {"low", "medium", "high"}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} key must be non-empty string")
        if not isinstance(v, str) or v.strip().lower() not in allowed:
            names = ", ".join(sorted(allowed))
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}.{k} must be one of [{names}]")
        out[k.strip()] = v.strip().lower()
    return out


def _req_optional_pattern_list(parent: Mapping[str, Any], key: str, i: int) -> tuple[str, ...]:
    raw = parent.get(key, [])
    if not isinstance(raw, list):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be list[str]")
    out: list[str] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key}[{idx}] must be non-empty string")
        out.append(item.strip().lower())
    return tuple(out)


def _req_optional_str(parent: Mapping[str, Any], key: str, i: int, *, default: str) -> str:
    if key not in parent:
        return default
    return _req_str(parent, key, i)


def _opt_nonneg_int(parent: Mapping[str, Any], key: str, i: int, *, default: int) -> int:
    if key not in parent:
        return default
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be int")
    if value < 0:
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be non-negative")
    return value


def _opt_str_with_default(parent: Mapping[str, Any], key: str, i: int, *, default: str) -> str:
    if key not in parent:
        return default
    return _req_str(parent, key, i)


def _req_optional_provider_id(parent: Mapping[str, Any], key: str, i: int) -> str | None:
    raw = parent.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise SecurityPolicyLoaderError(f"security_policies.items[{i}].{key} must be non-empty string when present")
    return raw.strip()

