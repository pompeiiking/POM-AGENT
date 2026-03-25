from __future__ import annotations

from datetime import datetime

from core.session.message_factory import new_message
from core.session.openai_message_format import tool_content_openai_v1
from core.session.session import Message, Part
from modules.assembly.token_budget import (
    apply_three_tier_token_budget,
    total_approx_tokens,
    trim_messages_to_approx_token_budget,
)


def _msg_tool_huge() -> Message:
    body = "x" * 4000
    return Message(
        message_id="t1",
        role="tool",
        parts=[Part(type="text", content=tool_content_openai_v1(tool_call_id="c1", payload=body), metadata={})],
        timestamp=datetime.now(),
        loop_index=0,
    )


def test_three_tier_with_zero_t1_t2_matches_trim_only() -> None:
    msgs = [new_message(role="user", content="a", loop_index=0) for _ in range(30)]
    budget = 5
    out_old = trim_messages_to_approx_token_budget(msgs, budget)
    out_new = apply_three_tier_token_budget(
        list(msgs),
        budget,
        compress_tool_max_chars=0,
        compress_early_turn_chars=0,
    )
    assert len(out_new) == len(out_old)
    assert total_approx_tokens(out_new) <= budget or len(out_new) == 1


def test_tier1_shortens_openai_tool_content() -> None:
    tool_m = _msg_tool_huge()
    before = len(tool_m.parts[0].content["message"]["content"])  # type: ignore[index]
    assert before > 500
    out = apply_three_tier_token_budget(
        [tool_m],
        budget=100,
        compress_tool_max_chars=200,
        compress_early_turn_chars=0,
    )
    inner = out[0].parts[0].content
    assert isinstance(inner, dict)
    body = inner["message"]["content"]
    assert isinstance(body, str)
    assert len(body) <= 250
    assert "tier1_tool_compressed" in body


def test_tier2_collapses_plain_user_assistant() -> None:
    u = new_message(role="user", content="x" * 400, loop_index=0)
    a = new_message(role="assistant", content="y" * 400, loop_index=0)
    budget = 80
    out = apply_three_tier_token_budget(
        [u, a],
        budget=budget,
        compress_tool_max_chars=0,
        compress_early_turn_chars=220,
    )
    assert len(out) == 1
    assert "早期对话已压缩" in render_plain(out[0])
    assert total_approx_tokens(out) <= budget


def render_plain(m: Message) -> str:
    from core.session.rule_summary import render_message_plain_text

    return render_message_plain_text(m)
