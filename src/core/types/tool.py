from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]
    # OpenAI tool_calls[].id，多轮工具对话时与 tool 消息的 tool_call_id 对齐
    call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    output: Any

