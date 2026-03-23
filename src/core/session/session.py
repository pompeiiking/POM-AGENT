from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

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