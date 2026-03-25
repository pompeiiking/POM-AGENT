from __future__ import annotations

import pytest

from app.config_loaders.tool_registry_loader import ToolRegistryLoaderError, ToolRegistrySource, load_tool_registry_config
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall, ToolResult
from modules.tools.impl import ToolModuleImpl, load_tool_handler
from modules.tools.mcp_bridge import McpToolBridge
from modules.tools.network_policy import ToolNetworkPolicyConfig


class _FakeMcp(McpToolBridge):
    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        return ToolResult(name=tool_call.name, output={"via": "mcp"}, source="mcp")


def _session() -> Session:
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


def test_mcp_allowlist_blocks_nonlisted_tool() -> None:
    pol = ToolNetworkPolicyConfig(
        enabled=True,
        mcp_allowlist_enforced=True,
        mcp_tool_allowlist=("ping",),
    )
    tools = ToolModuleImpl(
        local_handlers={},
        mcp=_FakeMcp(),
        network_policy=pol,
    )
    sess = _session()
    out = tools.execute(sess, ToolCall(name="add", arguments={}, call_id=None))
    assert out.output.get("error") == "tool_network_mcp_denied"


def test_mcp_allowlist_allows_listed_tool() -> None:
    pol = ToolNetworkPolicyConfig(
        enabled=True,
        mcp_allowlist_enforced=True,
        mcp_tool_allowlist=("ping",),
    )
    tools = ToolModuleImpl(
        local_handlers={},
        mcp=_FakeMcp(),
        network_policy=pol,
    )
    sess = _session()
    out = tools.execute(sess, ToolCall(name="ping", arguments={}, call_id=None))
    assert out.output.get("via") == "mcp"


def test_deny_tool_names_blocks_before_local_handler() -> None:
    h = load_tool_handler("modules.tools.builtin_handlers:echo_handler")
    pol = ToolNetworkPolicyConfig(enabled=True, deny_tool_names=("echo",))
    tools = ToolModuleImpl(
        local_handlers={"echo": h},
        mcp=None,
        network_policy=pol,
    )
    sess = _session()
    out = tools.execute(sess, ToolCall(name="echo", arguments={"text": "x"}, call_id=None))
    assert out.output.get("error") == "tool_network_denied"


def test_load_network_policy_yaml(tmp_path) -> None:
    p = tmp_path / "tools.yaml"
    p.write_text(
        """
tools:
  local_handlers: {}
  device_routes: []
  network_policy:
    enabled: true
    deny_tool_names: ["bad"]
    mcp_allowlist_enforced: true
    mcp_tool_allowlist: ["ping"]
    http_blocked_content_type_prefixes: ["application/octet-stream"]
""",
        encoding="utf-8",
    )
    cfg = load_tool_registry_config(ToolRegistrySource(path=p))
    assert cfg.network_policy.enabled is True
    assert cfg.network_policy.deny_tool_names == ("bad",)
    assert cfg.network_policy.mcp_tool_allowlist == ("ping",)
    assert cfg.network_policy.http_blocked_content_type_prefixes == ("application/octet-stream",)


def test_network_policy_rejects_bad_deny_list(tmp_path) -> None:
    p = tmp_path / "tools.yaml"
    p.write_text(
        """
tools:
  local_handlers: {}
  device_routes: []
  network_policy:
    enabled: true
    deny_tool_names: 1
""",
        encoding="utf-8",
    )
    with pytest.raises(ToolRegistryLoaderError):
        load_tool_registry_config(ToolRegistrySource(path=p))
