"""
规则摘要（与 `/summary` 一致）：不调用 LLM，供模型部与归档等复用。
"""

from __future__ import annotations

import json
from typing import Sequence

from .session import Message, Part, Session


def summary_rule_limits(session: Session) -> tuple[int, int]:
    lim = session.config.limits
    n = max(1, min(200, lim.summary_tail_messages))
    e = max(16, min(4000, lim.summary_excerpt_chars))
    return n, e


def render_message_plain_text(message: Message) -> str:
    parts_text: list[str] = []
    for part in message.parts:
        content = _render_part_content(part)
        if content:
            parts_text.append(content)
    return "\n".join(parts_text)


def _render_part_content(part: Part) -> str:
    value = part.content
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(value)
    return str(value)


def build_rule_summary_for_view(session: Session, context_messages: Sequence[Message] | None) -> str:
    """
    基于会话消息列表生成与 `/summary` 一致的规则摘要正文。
    context_messages 为空时回退到 session.messages。
    """
    max_lines, max_excerpt = summary_rule_limits(session)
    raw = list(context_messages) if context_messages else []
    if not raw and session.messages:
        raw = list(session.messages)
    if max_lines > 0 and len(raw) > max_lines:
        raw = raw[-max_lines:]

    if not raw:
        return "当前会话暂无对话记录，无法生成概要。"

    role_labels = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}
    lines_out: list[str] = []
    for m in raw:
        text = render_message_plain_text(m)
        if not text.strip():
            continue
        label = role_labels.get(m.role, m.role)
        excerpt = text.strip().replace("\n", " ")
        if len(excerpt) > max_excerpt:
            excerpt = excerpt[: max_excerpt - 3] + "..."
        lines_out.append(f"- [{label}] {excerpt}")

    if not lines_out:
        return "当前会话暂无可读文本，无法生成概要。"

    return "最近对话概要（规则生成，非模型）：\n" + "\n".join(lines_out)


def build_rule_summary_for_archive(session: Session) -> str:
    """归档用：仅依据会话内消息，不依赖 Assembly 视图。"""
    return build_rule_summary_for_view(session, None)
