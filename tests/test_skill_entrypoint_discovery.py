from __future__ import annotations

import pytest

from app.config_loaders.skill_registry_loader import SkillRegistry, SkillSpec
from app.skill_entrypoint_discovery import (
    SkillEntrypointDiscoveryError,
    merge_skill_registry_with_entrypoints,
    skill_spec_from_mapping,
)


def _spec(sid: str) -> SkillSpec:
    return SkillSpec(
        id=sid,
        index="I",
        title="T",
        summary="S",
        content="C",
        quality_tier="gold",
        enabled=True,
        tags=(),
    )


def test_skill_spec_from_mapping_uses_entry_id() -> None:
    sp = skill_spec_from_mapping(
        {
            "index": "IX",
            "title": "Ti",
            "summary": "Su",
            "content": "Co",
            "quality_tier": "gold",
            "tags": ["a"],
        },
        skill_id="plugin_x",
    )
    assert sp.id == "plugin_x"
    assert sp.title == "Ti"


def test_merge_adds_entrypoint_only_skills() -> None:
    yaml_only = SkillRegistry(skills={"echo": _spec("echo")}, enable_entrypoints=True, entrypoint_group="g")

    def fake_discover(_group: str) -> dict[str, SkillSpec]:
        return {"plugin": _spec("plugin")}

    merged = merge_skill_registry_with_entrypoints(yaml_only, discover_fn=fake_discover)
    assert set(merged.skills.keys()) == {"echo", "plugin"}


def test_merge_yaml_overrides_entrypoint_same_id() -> None:
    ep_echo = SkillSpec(
        id="echo",
        index="E",
        title="from_ep",
        summary="s",
        content="c",
        quality_tier="gold",
        enabled=True,
        tags=(),
    )
    yaml_echo = SkillSpec(
        id="echo",
        index="E",
        title="from_yaml",
        summary="s",
        content="c",
        quality_tier="gold",
        enabled=True,
        tags=(),
    )
    reg = SkillRegistry(skills={"echo": yaml_echo}, enable_entrypoints=True, entrypoint_group="g")
    merged = merge_skill_registry_with_entrypoints(reg, discover_fn=lambda _g: {"echo": ep_echo})
    assert merged.skills["echo"].title == "from_yaml"


def test_merge_skips_when_disabled() -> None:
    reg = SkillRegistry(skills={"echo": _spec("echo")}, enable_entrypoints=False, entrypoint_group="g")

    def boom(_g: str) -> dict[str, SkillSpec]:
        raise AssertionError("should not discover")

    merged = merge_skill_registry_with_entrypoints(reg, discover_fn=boom)
    assert set(merged.skills.keys()) == {"echo"}


def test_skill_spec_from_mapping_rejects_bad_tags() -> None:
    with pytest.raises(SkillEntrypointDiscoveryError):
        skill_spec_from_mapping(
            {
                "index": "I",
                "title": "T",
                "summary": "S",
                "content": "C",
                "quality_tier": "gold",
                "tags": [1],
            },
            skill_id="x",
        )
