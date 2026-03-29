from __future__ import annotations

import json


def text_deltas_from_sse_line(line: str) -> list[str]:
    """解析单行 `data: {...}`，返回 choices[].delta.content 片段列表。"""
    s = line.strip()
    if not s.startswith("data:"):
        return []
    raw = s[5:].strip()
    if raw == "[DONE]":
        return []
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(obj, dict):
        return []
    out: list[str] = []
    choices = obj.get("choices")
    if not isinstance(choices, list):
        return out
    for ch in choices:
        if not isinstance(ch, dict):
            continue
        delta = ch.get("delta")
        if not isinstance(delta, dict):
            continue
        c = delta.get("content")
        if isinstance(c, str) and c:
            out.append(c)
    return out
