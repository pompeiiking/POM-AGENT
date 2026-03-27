from __future__ import annotations

from core.agent_types import AgentResponse, ResponseReason
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from port.agent_port import _response_to_events


def _session() -> Session:
    lim = SessionLimits(max_tokens=100, max_context_window=100, max_loops=3, timeout_seconds=60.0)
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    return Session(
        session_id="s1",
        user_id="u1",
        channel="c1",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


def test_response_to_events_includes_policy_notice_for_approval_required() -> None:
    resp = AgentResponse(
        request_id="r1",
        session=_session(),
        reply_text="需要审批",
        reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
    )
    events = list(_response_to_events(resp))
    assert len(events) == 2
    assert events[0].kind == "policy_notice"
    assert events[1].kind == "reply"
