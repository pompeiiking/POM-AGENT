from __future__ import annotations

import pytest

from app.config_loaders.skill_registry_loader import (
    SkillRegistryLoaderError,
    SkillRegistrySource,
    load_skill_registry,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "skills.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_skill_registry_ok(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
skills:
  items:
    - id: "echo"
      index: "SKILL-001"
      title: "Echo"
      summary: "s"
      content: "c"
      quality_tier: "gold"
      enabled: true
      tags: ["a", "b"]
""",
    )
    reg = load_skill_registry(SkillRegistrySource(path=p))
    assert "echo" in reg.skills
    assert reg.skills["echo"].index == "SKILL-001"
    assert reg.enable_entrypoints is False
    assert reg.entrypoint_group == "pompeii_agent.skills"


def test_load_skill_registry_rejects_duplicate_id(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
skills:
  items:
    - id: "echo"
      index: "SKILL-001"
      title: "Echo"
      summary: "s"
      content: "c"
      quality_tier: "gold"
      enabled: true
      tags: ["a"]
    - id: "echo"
      index: "SKILL-002"
      title: "Echo2"
      summary: "s"
      content: "c"
      quality_tier: "gold"
      enabled: true
      tags: ["a"]
""",
    )
    with pytest.raises(SkillRegistryLoaderError):
        load_skill_registry(SkillRegistrySource(path=p))
