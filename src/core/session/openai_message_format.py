"""
在 Session.messages 中承载 OpenAI Chat Completions 所需的 assistant(tool_calls) / tool(tool_call_id) 结构。

使用 Part.content 为带 `_format: openai_v1` 的 dict，由模型层 `_render_history_messages_for_model` 展开为 API `messages` 元素。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any

from core.types import ToolCall

OPENAI_V1 = "openai_v1"


def ensure_tool_call_id(tool_call: ToolCall) -> ToolCall:
    if tool_call.call_id:
        return tool_call
    return replace(tool_call, call_id=uuid.uuid4().hex)


def assistant_content_openai_v1(tool_call: ToolCall) -> dict[str, Any]:
    """assistant 消息：含 tool_calls（单条）。"""
    tc = ensure_tool_call_id(tool_call)
    args_str = json.dumps(dict(tc.arguments), ensure_ascii=False)
    return {
        "_format": OPENAI_V1,
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": args_str},
                }
            ],
        },
    }


def tool_content_openai_v1(*, tool_call_id: str, payload: Any) -> dict[str, Any]:
    """tool 消息：字符串 content（常为 JSON）。"""
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return {
        "_format": OPENAI_V1,
        "message": {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": body,
        },
    }
