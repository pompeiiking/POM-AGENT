from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .session.session import Session
from .types import DeviceRequest, ToolCall
from .user_intent import UserIntent


@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    user_id: str
    channel: str
    payload: Any
    intent: UserIntent | None = None


@dataclass(frozen=True)
class AgentResponse:
    request_id: str
    session: Session
    reply_text: str | None
    error: str | None = None
    reason: str | None = None
    pending_tool_call: ToolCall | None = None
    pending_device_request: DeviceRequest | None = None

