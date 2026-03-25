from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import Any

from app.config_loaders.skill_registry_loader import SkillRegistry, SkillSpec


class SkillEntrypointDiscoveryError(ValueError):
    pass


def skill_spec_from_mapping(raw: Mapping[str, Any], *, skill_id: str) -> SkillSpec:
    """将插件返回的 dict 规范为 ``SkillSpec``（entry point 的 ``name`` 为权威 id）。"""
    if not isinstance(raw, Mapping):
        raise SkillEntrypointDiscoveryError(f"skill plugin {skill_id!r} must return mapping or SkillSpec")
    idx = _req_str(raw, "index", skill_id)
    title = _req_str(raw, "title", skill_id)
    summary = _req_str(raw, "summary", skill_id)
    content = _req_str(raw, "content", skill_id)
    tier = _req_str(raw, "quality_tier", skill_id)
    enabled = bool(raw.get("enabled", True))
    tags_raw = raw.get("tags", [])
    if not isinstance(tags_raw, list) or not all(isinstance(t, str) and t.strip() for t in tags_raw):
        raise SkillEntrypointDiscoveryError(f"skill plugin {skill_id!r}: tags must be list[str]")
    return SkillSpec(
        id=skill_id,
        index=idx,
        title=title,
        summary=summary,
        content=content,
        quality_tier=tier,
        enabled=enabled,
        tags=tuple(str(t).strip() for t in tags_raw),
    )


def _req_str(m: Mapping[str, Any], key: str, skill_id: str) -> str:
    v = m.get(key)
    if not isinstance(v, str) or not v.strip():
        raise SkillEntrypointDiscoveryError(f"skill plugin {skill_id!r}: {key!r} must be non-empty string")
    return v.strip()


def discover_entrypoint_skill_specs(
    *,
    group: str,
    select_fn: Callable[[str], list[Any]] | None = None,
) -> dict[str, SkillSpec]:
    """
    setuptools entry_points：
    - group：默认 ``pompeii_agent.skills``
    - name：skill id
    - 可调用无参 ``() -> SkillSpec | dict``，或返回已构造的 ``SkillSpec``
    """
    eps = _iter_entry_points(group, select_fn=select_fn)
    out: dict[str, SkillSpec] = {}
    for ep in eps:
        name = str(ep.name).strip()
        if not name:
            raise SkillEntrypointDiscoveryError(f"entry point in group {group!r} has empty name")
        obj = ep.load()
        if callable(obj):
            raw = obj()
        else:
            raw = obj
        if isinstance(raw, SkillSpec):
            spec = raw
            if spec.id != name:
                raise SkillEntrypointDiscoveryError(
                    f"skill entrypoint {group}:{name} SkillSpec.id mismatch ({spec.id!r} != {name!r})"
                )
        else:
            spec = skill_spec_from_mapping(raw, skill_id=name)
        out[name] = spec
    return out


def _iter_entry_points(group: str, *, select_fn: Callable[[str], list[Any]] | None = None) -> list[Any]:
    if select_fn is not None:
        return list(select_fn(group))
    eps = entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    return [e for e in eps if e.group == group]


def merge_skill_registry_with_entrypoints(
    registry: SkillRegistry,
    *,
    discover_fn: Callable[[str], dict[str, SkillSpec]] | None = None,
) -> SkillRegistry:
    """
    若 ``registry.enable_entrypoints``：合并 entry point 技能；**YAML 声明覆盖同名插件**（与 tools 一致）。
    """
    if not registry.enable_entrypoints:
        return registry
    group = registry.entrypoint_group.strip() or "pompeii_agent.skills"
    if discover_fn is not None:
        extra = discover_fn(group)
    else:
        extra = discover_entrypoint_skill_specs(group=group)
    merged_skills = {**extra, **registry.skills}
    return SkillRegistry(
        skills=merged_skills,
        enable_entrypoints=registry.enable_entrypoints,
        entrypoint_group=registry.entrypoint_group,
    )
