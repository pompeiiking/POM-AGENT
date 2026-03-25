"""
Port 边界唯一解析：将用户原始输入解析为结构化 UserIntent。
下游（Core/Assembly/Model）只消费 intent，不再做字符串判断。
"""
from __future__ import annotations

import re

from core.user_intent import (
    Chat,
    SystemArchive,
    SystemDelegate,
    SystemForget,
    SystemHelp,
    SystemRemember,
    SystemSummary,
    ToolAdd,
    ToolEcho,
    ToolPing,
    ToolTakePhoto,
    UserIntent,
)

_DELEGATE_TARGET = re.compile(r"^[a-zA-Z0-9_.-]+$")


def parse_user_intent(raw: str) -> UserIntent:
    """
    将原始用户输入解析为意图。规则集中在此处，便于扩展与测试。
    """
    stripped = raw.strip()
    if stripped == "/help":
        return SystemHelp()
    if stripped == "/summary":
        return SystemSummary()
    if stripped == "/archive":
        return SystemArchive()
    if stripped.startswith("/remember "):
        body = stripped[len("/remember ") :].strip()
        if body:
            return SystemRemember(text=body)
    if stripped.startswith("/forget "):
        body = stripped[len("/forget ") :].strip()
        if body:
            return SystemForget(phrase=body)
    if stripped.startswith("/delegate"):
        rest = stripped[len("/delegate") :].strip()
        if rest:
            head, sep, tail = rest.partition(" ")
            target = head.strip()
            payload = tail.strip() if sep else ""
            if target and _DELEGATE_TARGET.fullmatch(target):
                return SystemDelegate(target=target, payload=payload)
    if stripped.startswith("/tool echo "):
        return ToolEcho(text=stripped[len("/tool echo ") :].strip())
    if stripped == "/tool take_photo":
        return ToolTakePhoto()
    if stripped == "/tool ping":
        return ToolPing()
    if stripped.startswith("/tool add "):
        rest = stripped[len("/tool add ") :].strip().split()
        if len(rest) >= 2:
            try:
                return ToolAdd(a=int(rest[0]), b=int(rest[1]))
            except ValueError:
                pass
    return Chat(text=raw)
