from __future__ import annotations

import json
from typing import Any


class OpenAiChatStreamCollector:
    """
    累积 OpenAI 兼容 Chat Completions 的 SSE JSON 块，支持 ``delta.content`` 与 ``delta.tool_calls``。
    参考流式 tool_calls 分片：按 ``index`` 合并 ``id`` / ``function.name`` / ``function.arguments``。
    """

    def __init__(self) -> None:
        self._content_parts: list[str] = []
        self._tool_slots: dict[int, dict[str, Any]] = {}

    def feed_sse_line(self, line: str) -> list[str]:
        """
        解析 ``data: {...}``；返回应通过 ``on_delta`` 下发的正文片段（与旧行为一致）。
        """
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
        return self.feed_chunk(obj)

    def feed_chunk(self, obj: dict[str, Any]) -> list[str]:
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
                self._content_parts.append(c)
                out.append(c)
            tcl = delta.get("tool_calls")
            if isinstance(tcl, list):
                self._merge_tool_deltas(tcl)
        return out

    def _merge_tool_deltas(self, tcl: list[Any]) -> None:
        for tc in tcl:
            if not isinstance(tc, dict):
                continue
            try:
                idx = int(tc.get("index", 0))
            except (TypeError, ValueError):
                idx = 0
            slot = self._tool_slots.setdefault(idx, {"id": None, "name": "", "arguments": ""})
            tid = tc.get("id")
            if isinstance(tid, str) and tid.strip():
                slot["id"] = tid.strip()
            fn = tc.get("function")
            if isinstance(fn, dict):
                nm = fn.get("name")
                if isinstance(nm, str) and nm.strip():
                    slot["name"] = nm.strip()
                arg = fn.get("arguments")
                if isinstance(arg, str) and arg:
                    slot["arguments"] = str(slot["arguments"]) + arg

    def accumulated_text(self) -> str:
        return "".join(self._content_parts)

    def build_assistant_message(self) -> dict[str, Any]:
        text = "".join(self._content_parts)
        msg: dict[str, Any] = {}
        if text.strip():
            msg["content"] = text
        else:
            msg["content"] = None
        if not self._tool_slots:
            return msg
        tool_calls: list[dict[str, Any]] = []
        for idx in sorted(self._tool_slots.keys()):
            slot = self._tool_slots[idx]
            name = str(slot.get("name") or "").strip()
            if not name:
                continue
            tid = slot.get("id")
            ext_id = tid if isinstance(tid, str) and tid.strip() else ""
            args = str(slot.get("arguments") or "")
            if not args.strip():
                args = "{}"
            tool_calls.append(
                {
                    "id": ext_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                }
            )
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg
