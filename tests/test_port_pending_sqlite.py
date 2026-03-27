from __future__ import annotations

from pathlib import Path

from core.agent_types import AgentResponse, ResponseReason
from core.types import ToolCall
from port.agent_port import GenericAgentPort, HttpMode
from port.http_emitter import HttpEmitter
from port.input_events import SystemCommandInput, UserMessageInput
from port.request_factory import session_request_factory


class _CoreNeedConfirm:
    def handle(self, request, *, stream_delta=None):
        _ = stream_delta
        return AgentResponse(
            request_id=request.request_id,
            session=type("S", (), {"session_id": "s1"})(),
            reply_text=None,
            reason=ResponseReason.CONFIRMATION_REQUIRED,
            pending_tool_call=ToolCall(name="echo", arguments={"x": 1}, call_id="c1"),
        )

    def handle_confirmation_approved(self, request, tool_call, *, stream_delta=None):
        _ = (request, tool_call, stream_delta)
        return AgentResponse(
            request_id="r2",
            session=type("S", (), {"session_id": "s1"})(),
            reply_text="ok",
            reason=ResponseReason.OK,
        )

    def handle_device_result(self, request, *, tool_result, tool_call_id=None, stream_delta=None):
        _ = (request, tool_result, tool_call_id, stream_delta)
        return AgentResponse(
            request_id="r3",
            session=type("S", (), {"session_id": "s1"})(),
            reply_text="ok",
            reason=ResponseReason.OK,
        )


def test_pending_confirmation_persisted_in_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "pending.db"
    p1 = GenericAgentPort(
        mode=HttpMode(),
        core=_CoreNeedConfirm(),  # type: ignore[arg-type]
        request_factory=session_request_factory(user_id="u", channel="ch"),
        emitter=HttpEmitter(),
        pending_state_sqlite_path=db,
    )
    p2 = GenericAgentPort(
        mode=HttpMode(),
        core=_CoreNeedConfirm(),  # type: ignore[arg-type]
        request_factory=session_request_factory(user_id="u", channel="ch"),
        emitter=HttpEmitter(),
        pending_state_sqlite_path=db,
    )
    p1.handle(UserMessageInput(kind="user_message", text="hi"), user_id="u", channel="ch", emitter=HttpEmitter())
    em = HttpEmitter()
    p2.handle(SystemCommandInput(kind="system_command", text="yes"), user_id="u", channel="ch", emitter=em)
    dumped = em.dump()
    assert any(e.get("kind") in ("reply", "status") for e in dumped)
