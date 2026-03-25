"""
多模态用户输入（MVP）：与 OpenAI Chat Completions 的 user content 块对齐。

- HTTP/程序化入口：`AgentRequest.payload` 可为 ``{"openai_user_content": [...], "text": "..."}``。
- 会话持久化：``Message.parts`` 中 ``Part(type="text"|"image_url", ...)``；模型部 history 中非当前轮 user 亦输出块数组。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from .session import Message, Part


OPENAI_USER_CONTENT_KEY = "openai_user_content"
MULTIMODAL_TEXT_FALLBACK_KEY = "text"


def is_multimodal_agent_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    raw = payload.get(OPENAI_USER_CONTENT_KEY)
    return isinstance(raw, list) and len(raw) > 0


def flatten_payload_for_security(payload: Any) -> str:
    """供关卡① 长度与守卫：将多模态载荷摊平为可扫描字符串。"""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return str(payload)
    chunks: list[str] = []
    fb = payload.get(MULTIMODAL_TEXT_FALLBACK_KEY)
    if isinstance(fb, str) and fb.strip():
        chunks.append(fb.strip())
    blocks = payload.get(OPENAI_USER_CONTENT_KEY)
    if isinstance(blocks, list):
        for b in blocks:
            if not isinstance(b, dict):
                chunks.append(str(b))
                continue
            t = str(b.get("type", "")).strip()
            if t == "text":
                tx = b.get("text")
                if isinstance(tx, str):
                    chunks.append(tx)
            elif t == "image_url":
                iu = b.get("image_url")
                if isinstance(iu, dict):
                    u = iu.get("url")
                    if isinstance(u, str):
                        chunks.append(f"[image_url]{u}")
                else:
                    chunks.append(json.dumps(iu, ensure_ascii=False))
            else:
                try:
                    chunks.append(json.dumps(b, ensure_ascii=False))
                except Exception:
                    chunks.append(str(b))
    if chunks:
        return "\n".join(chunks)
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(payload)


def context_current_string_from_payload(payload: Any) -> str:
    """Context.current：模板变量与去重启发式用的主文本。"""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        fb = payload.get(MULTIMODAL_TEXT_FALLBACK_KEY)
        if isinstance(fb, str) and fb.strip():
            return fb
        blocks = payload.get(OPENAI_USER_CONTENT_KEY)
        if isinstance(blocks, list):
            joined = _join_text_from_openai_blocks(blocks)
            if joined.strip():
                return joined
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(payload)
    return str(payload)


def _join_text_from_openai_blocks(blocks: list[Any]) -> str:
    out: list[str] = []
    for b in blocks:
        if isinstance(b, dict) and str(b.get("type", "")).strip() == "text":
            tx = b.get("text")
            if isinstance(tx, str) and tx.strip():
                out.append(tx.strip())
    return "\n".join(out)


def openai_blocks_to_parts(blocks: list[Any]) -> list[Part]:
    parts: list[Part] = []
    for i, raw in enumerate(blocks):
        if not isinstance(raw, dict):
            raise ValueError(f"openai_user_content[{i}] must be object")
        t = str(raw.get("type", "")).strip()
        if t == "text":
            tx = raw.get("text")
            if not isinstance(tx, str):
                raise ValueError(f"openai_user_content[{i}].text must be string")
            parts.append(Part(type="text", content=tx, metadata={}))
        elif t == "image_url":
            iu = raw.get("image_url")
            if not isinstance(iu, dict):
                raise ValueError(f"openai_user_content[{i}].image_url must be object")
            url = iu.get("url")
            if not isinstance(url, str) or not url.strip():
                raise ValueError(f"openai_user_content[{i}].image_url.url must be non-empty string")
            parts.append(Part(type="image_url", content=dict(iu), metadata={}))
        else:
            raise ValueError(f"unsupported openai_user_content[{i}].type {t!r} (MVP: text|image_url)")
    if not parts:
        raise ValueError("openai_user_content must be non-empty")
    return parts


def message_uses_openai_multimodal_user_content(message: Message) -> bool:
    if message.role != "user":
        return False
    if len(message.parts) != 1:
        return True
    only = message.parts[0]
    return only.type != "text"


def message_to_openai_user_blocks(message: Message) -> list[dict[str, Any]] | None:
    """若该 user 消息应走多模态 API，返回块列表；否则 ``None``（走纯字符串路径）。"""
    if message.role != "user" or not message.parts:
        return None
    if len(message.parts) == 1 and message.parts[0].type == "text":
        return None
    out: list[dict[str, Any]] = []
    for p in message.parts:
        if p.type == "text":
            c = p.content
            if not isinstance(c, str):
                c = str(c)
            out.append({"type": "text", "text": c})
        elif p.type == "image_url":
            c = p.content
            if not isinstance(c, dict):
                raise TypeError("image_url part content must be dict")
            out.append({"type": "image_url", "image_url": dict(c)})
        else:
            raise ValueError(f"unsupported user part type for OpenAI export: {p.type!r}")
    return out


def agent_payload_from_user_input(
    text: str,
    openai_user_content: tuple[dict[str, Any], ...] | None,
) -> Any:
    if openai_user_content:
        return {
            OPENAI_USER_CONTENT_KEY: list(openai_user_content),
            MULTIMODAL_TEXT_FALLBACK_KEY: text,
        }
    return text


def new_user_message_from_agent_payload(payload: Any, *, loop_index: int) -> Message:
    if isinstance(payload, str):
        return _single_text_user_message(payload, loop_index=loop_index)
    if is_multimodal_agent_payload(payload):
        blocks = payload[OPENAI_USER_CONTENT_KEY]
        assert isinstance(blocks, list)
        parts = openai_blocks_to_parts(blocks)
        return Message(
            message_id=uuid4().hex,
            role="user",
            parts=parts,
            timestamp=datetime.now(),
            loop_index=loop_index,
            token_count=0,
        )
    return _single_text_user_message(str(payload), loop_index=loop_index)


def _single_text_user_message(text: str, *, loop_index: int) -> Message:
    return Message(
        message_id=uuid4().hex,
        role="user",
        parts=[Part(type="text", content=text, metadata={})],
        timestamp=datetime.now(),
        loop_index=loop_index,
        token_count=0,
    )
