from __future__ import annotations

from core.agent_types import AgentRequest
from core.session.message_factory import new_message
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolResult
from modules.assembly.formatting import format_model_output_for_reply, serialize_tool_output_for_current
from core.session.rule_summary import render_message_plain_text
from modules.assembly.impl import AssemblyModuleImpl
from modules.assembly.message_clip import clip_message_for_context
from modules.model.interface import ModelOutput


def _session() -> Session:
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=10,
        timeout_seconds=60.0,
        assembly_tail_messages=20,
    )
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    return Session(
        session_id="s1",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[
            new_message(role="user", content="hello", loop_index=0),
        ],
    )


def test_format_model_output_for_reply_text() -> None:
    assert format_model_output_for_reply(ModelOutput(kind="text", content="hi")) == "hi"
    assert format_model_output_for_reply(ModelOutput(kind="text", content=None)) == ""


def test_serialize_tool_output_for_current() -> None:
    s = serialize_tool_output_for_current("echo", {"a": 1})
    assert "echo" in s and '"a"' in s


def test_assembly_build_and_tool_meta() -> None:
    asm = AssemblyModuleImpl()
    sess = _session()
    req = AgentRequest(request_id="r1", user_id="u", channel="c", payload="ping", intent=None)
    ctx = asm.build_initial_context(sess, req)
    assert ctx.meta.get("phase") == "user_turn"
    assert ctx.meta.get("intent_type") is None

    ctx2 = asm.apply_tool_result(sess, ToolResult(name="echo", output={"x": 2}))
    assert ctx2.meta.get("phase") == "post_tool"
    assert "echo" in ctx2.current


def test_assembly_format_final_reply_model_output() -> None:
    asm = AssemblyModuleImpl()
    sess = _session()
    out = asm.format_final_reply(sess, ModelOutput(kind="text", content="final"))
    assert out == "final"


def test_clip_message_for_context() -> None:
    sess = _session()
    m = sess.messages[0]
    clipped = clip_message_for_context(m, 3)
    assert render_message_plain_text(clipped) == "..."


def test_assembly_applies_message_char_budget() -> None:
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=10,
        timeout_seconds=60.0,
        assembly_tail_messages=20,
        assembly_message_max_chars=24,
    )
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    sess = Session(
        session_id="s1",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[new_message(role="user", content="y" * 100, loop_index=0)],
    )
    asm = AssemblyModuleImpl()
    req = AgentRequest(request_id="r1", user_id="u", channel="c", payload="p", intent=None)
    ctx = asm.build_initial_context(sess, req)
    t = render_message_plain_text(ctx.messages[0])
    assert len(t) == 24
    assert t.endswith("...")
