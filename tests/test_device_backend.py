from __future__ import annotations

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import DeviceRequest, ToolCall, ToolResult
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


def _echo_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    _ = (session, tool_call)
    return ToolResult(name="echo", output={"from": "local"})


def test_resolve_device_request_from_registered_route() -> None:
    tools = ToolModuleImpl(
        local_handlers={"echo": _echo_handler},
        device_routes={"take_photo": DeviceRequest(device="camera", command="take_photo", parameters={"quality": "low"})},
    )
    sess = _sess()
    tc = ToolCall(name="take_photo", arguments={"quality": "high"}, call_id="c1")
    req = tools.resolve_device_request(tc)
    assert req is not None
    assert req.device == "camera"
    assert req.command == "take_photo"
    assert req.parameters == {"quality": "high"}

    r = tools.execute(sess, ToolCall(name="echo", arguments={"text": "x"}, call_id="c2"))
    assert r.output == {"from": "local"}
