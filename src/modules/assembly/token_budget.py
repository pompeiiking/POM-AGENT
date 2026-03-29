from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from core.session.openai_message_format import OPENAI_V1
from core.session.rule_summary import render_message_plain_text
from core.session.session import Message, Part

_logger = logging.getLogger(__name__)

# (mode, encoding) -> counter，避免每轮重复 get_encoding
_MESSAGE_TOKEN_COUNTER_CACHE: dict[tuple[str, str], Callable[[Message], int]] = {}


def approximate_message_tokens(message: Message) -> int:
    """
    启发式近似 token：len(utf-8 文本)/4；不依赖 tiktoken。
    与 ``make_message_token_counter("heuristic", _)`` 等价。
    """
    n = len(render_message_plain_text(message).strip())
    if n == 0:
        return 0
    return max(1, n // 4)


def make_message_token_counter(mode: str, encoding: str) -> Callable[[Message], int]:
    """
    按会话配置构造单条消息的 token 计数函数。

    - ``heuristic``：len/4
    - ``tiktoken``：使用 ``tiktoken.get_encoding(encoding)``；未安装 tiktoken 时记录警告并回退 heuristic
    """
    key = (mode.strip().lower(), encoding.strip())
    cached = _MESSAGE_TOKEN_COUNTER_CACHE.get(key)
    if cached is not None:
        return cached

    if key[0] == "heuristic" or not key[0]:
        fn: Callable[[Message], int] = approximate_message_tokens
        _MESSAGE_TOKEN_COUNTER_CACHE[key] = fn
        return fn

    if key[0] == "tiktoken":
        try:
            import tiktoken
        except ImportError:
            _logger.warning(
                "assembly_token_counter=tiktoken but tiktoken is not installed; "
                "falling back to heuristic (len/4). Install tiktoken for precise counts."
            )
            _MESSAGE_TOKEN_COUNTER_CACHE[key] = approximate_message_tokens
            return approximate_message_tokens

        enc = tiktoken.get_encoding(key[1])

        def _tiktoken_count(message: Message) -> int:
            text = render_message_plain_text(message).strip()
            if not text:
                return 0
            n = len(enc.encode(text))
            return max(1, n)

        _MESSAGE_TOKEN_COUNTER_CACHE[key] = _tiktoken_count
        return _tiktoken_count

    raise ValueError(f"unknown assembly_token_counter: {mode!r}")


def total_approx_tokens(
    messages: Sequence[Message],
    *,
    count_tokens: Callable[[Message], int] | None = None,
) -> int:
    ct = count_tokens or approximate_message_tokens
    return sum(ct(m) for m in messages)


_TIER1_TOOL_SUFFIX = "…[tier1_tool_compressed]"
_TIER2_PREFIX = "[早期对话已压缩]"


def apply_three_tier_token_budget(
    messages: list[Message],
    budget: int,
    *,
    compress_tool_max_chars: int,
    compress_early_turn_chars: int,
    count_tokens: Callable[[Message], int] | None = None,
) -> list[Message]:
    """
    架构 §7.3 层面 A（MVP，无异步归档）：

    1. 在总量仍超 ``budget`` 时，若 ``compress_tool_max_chars > 0``，截短 openai_v1 **tool** 消息正文；
    2. 若仍超且 ``compress_early_turn_chars > 0``，自前向后折叠相邻纯文本 user+assistant 为一轮；
    3. 最后仍超则 ``trim_messages_to_approx_token_budget``（自新向旧丢消息）。

    ``compress_*`` 为 0 时跳过对应级（默认全 0 时与仅第三级行为一致）。
    """
    ct = count_tokens or approximate_message_tokens
    if budget <= 0:
        return list(messages)
    msgs = list(messages)
    if total_approx_tokens(msgs, count_tokens=ct) <= budget:
        return msgs

    if compress_tool_max_chars > 0:
        msgs = [_shorten_openai_tool_message(m, max_chars=compress_tool_max_chars) for m in msgs]
        if total_approx_tokens(msgs, count_tokens=ct) <= budget:
            return msgs

    if compress_early_turn_chars > 0:
        msgs = _tier2_collapse_early_plain_turns(
            msgs, budget=budget, max_chars=compress_early_turn_chars, count_tokens=ct
        )
        if total_approx_tokens(msgs, count_tokens=ct) <= budget:
            return msgs

    return trim_messages_to_approx_token_budget(msgs, budget, count_tokens=ct)


def trim_messages_to_approx_token_budget(
    messages: Sequence[Message],
    budget: int,
    count_tokens: Callable[[Message], int] | None = None,
) -> list[Message]:
    """
    从**最新**往旧保留消息，使 token 总和不超过 budget。
    budget <= 0 时不裁剪。
    """
    ct = count_tokens or approximate_message_tokens
    if budget <= 0:
        return list(messages)
    rev: list[Message] = []
    total = 0
    for m in reversed(messages):
        t = ct(m)
        if not rev and t > budget:
            return [m]
        if total + t > budget:
            break
        rev.append(m)
        total += t
    return list(reversed(rev))


def _is_openai_tool_message(m: Message) -> bool:
    if len(m.parts) != 1:
        return False
    c = m.parts[0].content
    if not isinstance(c, dict) or c.get("_format") != OPENAI_V1:
        return False
    inner = c.get("message") or {}
    return inner.get("role") == "tool" and isinstance(inner.get("content"), str)


def _shorten_openai_tool_message(m: Message, *, max_chars: int) -> Message:
    if not _is_openai_tool_message(m):
        return m
    p = m.parts[0]
    c = p.content
    assert isinstance(c, dict)
    inner = dict(c["message"])
    body = inner["content"]
    assert isinstance(body, str)
    if len(body) <= max_chars:
        return m
    suf = _TIER1_TOOL_SUFFIX
    take = max(0, max_chars - len(suf))
    inner["content"] = (body[:take] + suf) if take > 0 else suf[:max_chars]
    new_c = {**c, "message": inner}
    new_p = Part(type=p.type, content=new_c, metadata=dict(p.metadata))
    return Message(
        message_id=m.message_id,
        role=m.role,
        parts=[new_p],
        timestamp=m.timestamp,
        loop_index=m.loop_index,
        token_count=m.token_count,
    )


def _is_plain_single_text_message(m: Message) -> bool:
    return len(m.parts) == 1 and isinstance(m.parts[0].content, str)


def _tier2_collapse_early_plain_turns(
    messages: list[Message],
    *,
    budget: int,
    max_chars: int,
    count_tokens: Callable[[Message], int],
) -> list[Message]:
    msgs = list(messages)
    guard = 0
    max_iter = max(1, len(msgs) * 2)
    while total_approx_tokens(msgs, count_tokens=count_tokens) > budget and guard < max_iter:
        guard += 1
        new_msgs, did = _collapse_first_plain_user_assistant_pair(msgs, max_chars=max_chars)
        if not did:
            break
        msgs = new_msgs
    return msgs


def _collapse_first_plain_user_assistant_pair(
    messages: list[Message],
    *,
    max_chars: int,
) -> tuple[list[Message], bool]:
    for i in range(len(messages) - 1):
        u, a = messages[i], messages[i + 1]
        if u.role != "user" or a.role != "assistant":
            continue
        if not _is_plain_single_text_message(u) or not _is_plain_single_text_message(a):
            continue
        ut = str(u.parts[0].content).strip()
        at = str(a.parts[0].content).strip()
        merged_text = f"{_TIER2_PREFIX} U:{ut} | A:{at}"
        if len(merged_text) > max_chars:
            merged_text = merged_text[: max(0, max_chars - 1)] + "…"
        merged = Message(
            message_id=u.message_id,
            role="user",
            parts=[Part(type="text", content=merged_text, metadata={})],
            timestamp=u.timestamp,
            loop_index=u.loop_index,
            token_count=u.token_count,
        )
        return messages[:i] + [merged] + messages[i + 2 :], True
    return messages, False
