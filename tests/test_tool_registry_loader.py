from __future__ import annotations

import pytest

from app.config_loaders.tool_registry_loader import (
    ToolRegistryLoaderError,
    ToolRegistrySource,
    load_tool_registry_config,
)
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall
from modules.tools.impl import ToolModuleImpl, load_tool_handler


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "tools.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def _sess() -> Session:
    lim = SessionLimits(max_tokens=10, max_context_window=10, max_loops=3, timeout_seconds=10.0)
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    return Session(
        session_id="s",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


def test_load_tool_registry_config_ok(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
tools:
  enable_entrypoints: true
  entrypoint_group: "pompeii_agent.tools"
  local_handlers:
    echo: "modules.tools.builtin_handlers:echo_handler"
  device_routes:
    - tool: "take_photo"
      device: "camera"
      command: "take_photo"
      fixed_parameters:
        quality: "low"
""",
    )
    cfg = load_tool_registry_config(ToolRegistrySource(path=path))
    assert cfg.local_handlers["echo"] == "modules.tools.builtin_handlers:echo_handler"
    assert "take_photo" in cfg.device_routes
    assert cfg.device_routes["take_photo"].device == "camera"
    assert cfg.enable_entrypoints is True
    assert cfg.entrypoint_group == "pompeii_agent.tools"
    assert cfg.network_policy.enabled is False
    assert cfg.network_policy.mcp_tool_allowlist == ()
    assert cfg.network_policy.http_url_guard_enabled is False
    assert cfg.network_policy.http_url_allowed_hosts == ()
    assert cfg.network_policy.http_blocked_content_type_prefixes == ()


def test_load_tool_registry_config_rejects_bad_handler_ref(tmp_path) -> None:
    path = _write_yaml(
        tmp_path,
        """
tools:
  local_handlers:
    echo: "bad_ref"
  device_routes: []
""",
    )
    with pytest.raises(ToolRegistryLoaderError):
        load_tool_registry_config(ToolRegistrySource(path=path))


def test_tool_module_impl_uses_loaded_handler_and_device_route() -> None:
    handler = load_tool_handler("modules.tools.builtin_handlers:echo_handler")
    tools = ToolModuleImpl(
        local_handlers={"echo": handler},
        device_routes={},
        mcp=None,
    )
    sess = _sess()
    res = tools.execute(sess, ToolCall(name="echo", arguments={"text": "x"}))
    assert isinstance(res.output, dict)
    assert res.output.get("echo") == {"text": "x"}
