from __future__ import annotations

from core.session.rule_summary import render_message_plain_text
from core.session.session import Message, Part


def clip_message_for_context(message: Message, max_chars: int) -> Message:
    """
    为组装部纳入 Context 的单条消息做字符上限截断（不修改会话中的原始 Message）。
    max_chars <= 0 时原样返回。
    """
    if max_chars <= 0:
        return message
    text = render_message_plain_text(message)
    if len(text) <= max_chars:
        return message
    suffix = "..."
    take = max(0, max_chars - len(suffix))
    clipped = (text[:take] + suffix) if take > 0 else suffix[:max_chars]
    return Message(
        message_id=message.message_id,
        role=message.role,
        parts=[Part(type="text", content=clipped, metadata={})],
        timestamp=message.timestamp,
        loop_index=message.loop_index,
        token_count=message.token_count,
    )
