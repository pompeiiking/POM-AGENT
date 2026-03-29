"""
OpenAI Chat Completions 响应中 `message` 字段解析：正文或 `tool_calls` → `ModelOutput`。
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from core.types import ToolCall

from .interface import ModelOutput


def openai_message_to_model_output(msg: Mapping[str, Any], *, provider_id: str) -> ModelOutput:
    """
    将 choices[0].message 转为 ModelOutput。
    - 若存在非空 `tool_calls`，取第一条 `function.name` / `function.arguments`（JSON）构造 `tool_call`；
    - 否则返回 `content` 文本。
    """
    _ = provider_id
    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        first = tool_calls[0]
        if isinstance(first, dict):
            ext_id = first.get("id")
            call_id = str(ext_id).strip() if isinstance(ext_id, str) and ext_id.strip() else None
            fn = first.get("function")
            if isinstance(fn, dict):
                name = str(fn.get("name") or "").strip()
                raw_args = fn.get("arguments", "{}")
                arguments: dict[str, Any]
                if isinstance(raw_args, str):
                    try:
                        parsed: Any = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        parsed = {"_parse_error": True, "raw": raw_args}
                    if isinstance(parsed, dict):
                        arguments = parsed
                    else:
                        arguments = {"value": parsed}
                elif isinstance(raw_args, dict):
                    arguments = dict(raw_args)
                else:
                    arguments = {"value": raw_args}
                if name:
                    return ModelOutput(
                        kind="tool_call",
                        tool_call=ToolCall(name=name, arguments=arguments, call_id=call_id),
                    )

    content = msg.get("content")
    if content is None:
        content = ""
    return ModelOutput(kind="text", content=str(content))
