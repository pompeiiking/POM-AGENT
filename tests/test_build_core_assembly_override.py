from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.composition import build_core
from app.config_provider import yaml_file_config_provider
from core.session.session import Session
from core.types import ToolResult
from modules.assembly.impl import AssemblyModuleImpl
from modules.model.interface import ModelOutput


def _src_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src"


def _session_defaults_path() -> Path:
    return _src_root() / "platform_layer" / "resources" / "config" / "session_defaults.yaml"


class _TaggedAssembly:
    """最小 AssemblyModule，用于断言 build_core 使用了注入实例。"""

    tag = "composition_injected_assembly"

    def build_initial_context(self, session: Session, request: Any) -> Any:
        _ = (session, request)
        return {"assembly_tag": self.tag}

    def apply_tool_result(self, session: Session, tool_result: ToolResult) -> Any:
        _ = (session, tool_result)
        return {"assembly_tag": self.tag}

    def format_final_reply(self, session: Session, model_output: Any) -> str:
        _ = session
        if isinstance(model_output, ModelOutput):
            return model_output.content or ""
        return str(model_output)


@pytest.mark.integration
def test_build_core_uses_injected_assembly_instance() -> None:
    asm = _TaggedAssembly()
    core = build_core(
        yaml_file_config_provider(_session_defaults_path()),
        src_root=_src_root(),
        assembly=asm,
    )
    assert core._assembly is asm


@pytest.mark.integration
def test_build_core_default_assembly_is_impl() -> None:
    core = build_core(
        yaml_file_config_provider(_session_defaults_path()),
        src_root=_src_root(),
    )
    assert isinstance(core._assembly, AssemblyModuleImpl)
