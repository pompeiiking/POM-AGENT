from __future__ import annotations

from core.session.message_factory import new_message
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.agent_types import AgentRequest
from core.session.rule_summary import render_message_plain_text
from modules.assembly.impl import AssemblyModuleImpl
from modules.assembly.token_budget import approximate_message_tokens, trim_messages_to_approx_token_budget


def test_trim_keeps_suffix_under_budget() -> None:
    msgs = [
        new_message(role="user", content="a" * 400, loop_index=0),
        new_message(role="user", content="b" * 400, loop_index=0),
    ]
    out = trim_messages_to_approx_token_budget(msgs, budget=50)
    assert len(out) == 1
    assert out[0].parts[0].content == msgs[1].parts[0].content


def test_approximate_message_tokens() -> None:
    m = new_message(role="user", content="x" * 40, loop_index=0)
    assert approximate_message_tokens(m) == 10


def test_assembly_respects_token_budget() -> None:
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=10,
        timeout_seconds=60.0,
        assembly_tail_messages=20,
        assembly_message_max_chars=0,
        assembly_approx_context_tokens=15,
    )
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    long_msg = new_message(role="user", content="z" * 400, loop_index=0)
    short_msg = new_message(role="user", content="tail-only", loop_index=0)
    sess = Session(
        session_id="s1",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[long_msg, short_msg],
    )
    asm = AssemblyModuleImpl()
    ctx = asm.build_initial_context(
        sess,
        AgentRequest(request_id="r1", user_id="u", channel="c", payload="hi", intent=None),
    )
    assert len(ctx.messages) == 1
    assert "tail-only" in render_message_plain_text(ctx.messages[0])
