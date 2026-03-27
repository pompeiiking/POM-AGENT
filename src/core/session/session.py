from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

#Part
@dataclass(frozen=True)
class Part:
    type: str
    content: str | dict | bytes
    metadata: dict[str, Any] = field(default_factory=dict)
#Message
@dataclass
class Message:
    message_id: str
    role: str  # "user" | "assistant" | "system" | "tool"
    parts: list[Part]
    timestamp: datetime = field(default_factory=datetime.now)
    loop_index: int = 0
    token_count: int = 0

class SessionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    ARCHIVED = "archived"
    DESTROYED = "destroyed"

# ── Session 状态机：合法转换表 ──
# ACTIVE  → IDLE（超时）、ARCHIVED（用户归档）、DESTROYED（管理清理）
# IDLE    → ACTIVE（新消息激活）、ARCHIVED（归档闲置会话）、DESTROYED（管理清理）
# ARCHIVED→ DESTROYED（最终清理）
# DESTROYED 为终态，不可转出
_VALID_TRANSITIONS: frozenset[tuple[SessionStatus, SessionStatus]] = frozenset({
    (SessionStatus.ACTIVE, SessionStatus.IDLE),
    (SessionStatus.ACTIVE, SessionStatus.ARCHIVED),
    (SessionStatus.ACTIVE, SessionStatus.DESTROYED),
    (SessionStatus.IDLE, SessionStatus.ACTIVE),
    (SessionStatus.IDLE, SessionStatus.ARCHIVED),
    (SessionStatus.IDLE, SessionStatus.DESTROYED),
    (SessionStatus.ARCHIVED, SessionStatus.DESTROYED),
})


class InvalidSessionTransition(Exception):
    """会话状态转换不合法时抛出。"""

    def __init__(self, session_id: str, current: SessionStatus, target: SessionStatus) -> None:
        self.session_id = session_id
        self.current = current
        self.target = target
        super().__init__(
            f"invalid session transition: {current.value!r} → {target.value!r} "
            f"(session_id={session_id!r})"
        )


def validate_session_transition(
    session_id: str, current: SessionStatus, target: SessionStatus,
) -> None:
    """校验状态转换合法性；同状态视为无操作不报错。"""
    if current == target:
        return
    if (current, target) not in _VALID_TRANSITIONS:
        raise InvalidSessionTransition(session_id, current, target)

#SessionLimits
@dataclass
class SessionLimits:
    max_tokens: int
    max_context_window: int
    max_loops: int
    timeout_seconds: float
    # 组装部取会话消息尾部条数上限（与 token 窗口配合，先以条数落地）
    assembly_tail_messages: int = 20
    # /summary 规则摘要：纳入的消息条数与单条摘录最大字符数
    summary_tail_messages: int = 12
    summary_excerpt_chars: int = 200
    # 组装部 Context.messages 中单条消息渲染为纯文本后的最大字符数（近似控制上下文体积）；0 表示不截断
    assembly_message_max_chars: int = 0
    # 组装部纳入 Context 的近似 token 总上限（启发式，见 assembly/token_budget.py）；0 表示不按总量裁剪
    assembly_approx_context_tokens: int = 0
    # §7.3 第一级：openai_v1 的 tool 消息 content 最大字符；0 表示不启用该级（仍可走 2/3 级）
    assembly_compress_tool_max_chars: int = 0
    # §7.3 第二级：将早期相邻纯文本 user+assistant 折叠为一轮时的总字符上限；0 表示不启用该级
    assembly_compress_early_turn_chars: int = 0
    # 组装部 token 计数：heuristic=len/4；tiktoken=按 encoding 精确计数（需安装 tiktoken）
    assembly_token_counter: Literal["heuristic", "tiktoken"] = "heuristic"
    assembly_tiktoken_encoding: str = "cl100k_base"

@dataclass
class SessionConfig:
    model: str
    skills: list[str]
    security: str | dict[str, Any]
    limits: SessionLimits
    # 提示词配置档位（由 model provider 的 prompt_profiles 解析）；默认 default
    prompt_profile: str = "default"
    # 提示词策略（如 default/concise/tool_first）；默认 default
    prompt_strategy: str = "default"

@dataclass
class SessionStats:
    total_tokens_used: int = 0
    message_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)

@dataclass
class Session:
    session_id: str
    user_id: str
    channel: str
    config: SessionConfig
    status: SessionStatus = SessionStatus.ACTIVE
    stats: SessionStats = field(default_factory=SessionStats)
    messages: list[Message] = field(default_factory=list)