from __future__ import annotations

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall, ToolResult
from modules.tools.device_backend import DeviceToolBackend
from modules.tools.impl import ToolModuleImpl


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


class _Stub(DeviceToolBackend):
    def try_local(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        _ = session
        if tool_call.name == "echo":
            return ToolResult(name="echo", output={"from": "stub"})
        return None


def test_device_backend_short_circuits_before_local_handlers() -> None:
    tools = ToolModuleImpl(device_backend=_Stub())
    sess = _sess()
    tc = ToolCall(name="echo", arguments={"text": "x"}, call_id="c1")
    r = tools.execute(sess, tc)
    assert r.output == {"from": "stub"}
