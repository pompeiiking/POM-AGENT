from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .session_config_loader import read_config_mapping


class SkillRegistryLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class SkillSpec:
    id: str
    index: str
    title: str
    summary: str
    content: str
    quality_tier: str
    enabled: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SkillRegistry:
    skills: Mapping[str, SkillSpec]
    enable_entrypoints: bool = False
    entrypoint_group: str = "pompeii_agent.skills"


@dataclass(frozen=True)
class SkillRegistrySource:
    path: Path


def load_skill_registry(source: SkillRegistrySource) -> SkillRegistry:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "skills")
    items = root.get("items")
    if not isinstance(items, list):
        raise SkillRegistryLoaderError("skills.items must be a list")
    enable_entrypoints = bool(root.get("enable_entrypoints", False))
    entrypoint_group = str(root.get("entrypoint_group", "pompeii_agent.skills")).strip()
    if not entrypoint_group:
        raise SkillRegistryLoaderError("skills.entrypoint_group must be non-empty string when present")
    out: dict[str, SkillSpec] = {}
    for i, raw in enumerate(items):
        if not isinstance(raw, Mapping):
            raise SkillRegistryLoaderError(f"skills.items[{i}] must be mapping")
        sid = _req_str(raw, "id", i)
        idx = _req_str(raw, "index", i)
        title = _req_str(raw, "title", i)
        summary = _req_str(raw, "summary", i)
        content = _req_str(raw, "content", i)
        tier = _req_str(raw, "quality_tier", i)
        enabled = bool(raw.get("enabled", True))
        tags_raw = raw.get("tags", [])
        if not isinstance(tags_raw, list) or not all(isinstance(t, str) and t.strip() for t in tags_raw):
            raise SkillRegistryLoaderError(f"skills.items[{i}].tags must be list[str]")
        if sid in out:
            raise SkillRegistryLoaderError(f"duplicate skill id: {sid}")
        out[sid] = SkillSpec(
            id=sid,
            index=idx,
            title=title,
            summary=summary,
            content=content,
            quality_tier=tier,
            enabled=enabled,
            tags=tuple(str(t).strip() for t in tags_raw),
        )
    return SkillRegistry(
        skills=out,
        enable_entrypoints=enable_entrypoints,
        entrypoint_group=entrypoint_group,
    )


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    v = parent.get(key)
    if not isinstance(v, Mapping):
        raise SkillRegistryLoaderError(f"missing object field: {key}")
    return v


def _req_str(parent: Mapping[str, Any], key: str, i: int) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or not v.strip():
        raise SkillRegistryLoaderError(f"skills.items[{i}].{key} must be non-empty string")
    return v.strip()
