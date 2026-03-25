from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from core.session.session import Message
from core.user_intent import UserIntent


@dataclass(frozen=True)
class Context:
    """
    Assembly 部构建给模型看的上下文视图。
    - messages: 当前会话中最近若干条消息（user/assistant/tool）
    - current: 本次请求的 payload 文本（供 LLM 或占位用）
    - intent: Port 边界解析后的用户意图，Model 仅按 intent 分发，不做字符串判断
    - meta: 预留扩展字段（如 user_id/channel/session_id 等）
    """

    messages: Sequence[Message]
    current: str
    intent: UserIntent | None
    meta: dict[str, Any]
    memory_context_block: str | None = None

