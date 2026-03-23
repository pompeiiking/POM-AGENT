from __future__ import annotations

import json
from typing import Any

from core.user_intent import UserIntent
from modules.model.interface import ModelOutput


def intent_type_name(intent: UserIntent | None) -> str | None:
    return None if intent is None else type(intent).__name__


def format_model_output_for_reply(model_output: Any) -> str:
    """
    将模型部产出转为对用户可见的最终字符串（组装部职责）。
    优先处理 ModelOutput(kind=text)；其余类型做防御性降级。
    """
    if isinstance(model_output, ModelOutput):
        if model_output.kind == "text":
            c = model_output.content
            return "" if c is None else str(c)
        if model_output.kind == "tool_call" and model_output.tool_call is not None:
            return f"[unexpected tool_call in text path] {model_output.tool_call.name!r}"
        return ""
    return str(model_output)


def serialize_tool_output_for_current(tool_name: str, output: Any) -> str:
    """
    工具结果 → 写入 Context.current 的短文本，供下一轮模型或规则阅读。
    """
    try:
        payload = json.dumps(output, ensure_ascii=False, default=str)
    except TypeError:
        payload = repr(output)
    return f"tool {tool_name} -> {payload}"
