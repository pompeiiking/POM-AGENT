from __future__ import annotations

from collections.abc import Sequence

from core.session.rule_summary import render_message_plain_text
from core.session.session import Message


def approximate_message_tokens(message: Message) -> int:
    """
    近似 token 数（不依赖 tiktoken）：len(utf-8 文本) / 4 为常见启发式，用于组装部总预算裁剪。
    """
    n = len(render_message_plain_text(message).strip())
    if n == 0:
        return 0
    return max(1, n // 4)


def trim_messages_to_approx_token_budget(messages: Sequence[Message], budget: int) -> list[Message]:
    """
    从**最新**往旧保留消息，使近似 token 总和不超过 budget。
    budget <= 0 时不裁剪。
    """
    if budget <= 0:
        return list(messages)
    rev: list[Message] = []
    total = 0
    for m in reversed(messages):
        t = approximate_message_tokens(m)
        if not rev and t > budget:
            return [m]
        if total + t > budget:
            break
        rev.append(m)
        total += t
    return list(reversed(rev))
