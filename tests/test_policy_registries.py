from __future__ import annotations

import pytest

from app.loop_policy_registry import LoopPolicyRegistryError, resolve_loop_governance_fn
from app.tool_policy_registry import ToolPolicyRegistryError, resolve_tool_policy_decide
from core.kernel_config import KernelConfig
from core.policies.tool_policy import ToolPolicyDecision
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall


def test_resolve_tool_policy_default() -> None:
    fn = resolve_tool_policy_decide("builtin:default")
    d = fn(
        tool_call=ToolCall(name="echo", arguments={}, call_id=None),
        kernel_config=KernelConfig(
            core_max_loops=3,
            max_tool_calls_per_run=3,
            tool_allowlist=["echo"],
            tool_confirmation_required=[],
        ),
        bypass_tool_confirmation=False,
    )
    assert d.allowed is True


def test_resolve_tool_policy_unknown_entrypoint() -> None:
    with pytest.raises(ToolPolicyRegistryError):
        resolve_tool_policy_decide("entrypoint:does_not_exist_xyz")


def test_resolve_loop_policy_default() -> None:
    fn = resolve_loop_governance_fn("builtin:default")
    lim = SessionLimits(max_tokens=10, max_context_window=10, max_loops=2, timeout_seconds=1.0)
    cfg = SessionConfig(model="m", skills=[], security="s", limits=lim)
    sess = Session(
        session_id="s",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    k = KernelConfig(
        core_max_loops=5,
        max_tool_calls_per_run=3,
        tool_allowlist=[],
        tool_confirmation_required=[],
    )
    g = fn(sess, k)
    assert g.max_loops == 2
    assert g.max_tool_calls_per_run == 3


def test_resolve_loop_unknown_entrypoint() -> None:
    with pytest.raises(LoopPolicyRegistryError):
        resolve_loop_governance_fn("entrypoint:missing_loop_policy_plugin")


def test_custom_tool_policy_via_discover_fn() -> None:
    def deny_all(**_kwargs) -> ToolPolicyDecision:
        return ToolPolicyDecision(allowed=False, reason="custom", needs_confirmation=False)

    fn = resolve_tool_policy_decide(
        "entrypoint:deny",
        discover_fn=lambda _g: {"deny": deny_all},
    )
    d = fn(
        tool_call=ToolCall(name="echo", arguments={}, call_id=None),
        kernel_config=KernelConfig(
            core_max_loops=3,
            max_tool_calls_per_run=3,
            tool_allowlist=["echo"],
            tool_confirmation_required=[],
        ),
        bypass_tool_confirmation=True,
    )
    assert d.allowed is False
    assert d.reason == "custom"
