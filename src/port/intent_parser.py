"""
Port 边界唯一解析：将用户原始输入解析为结构化 UserIntent。
下游（Core/Assembly/Model）只消费 intent，不再做字符串判断。
"""
from __future__ import annotations

from core.user_intent import (
    Chat,
    SystemArchive,
    SystemHelp,
    SystemSummary,
    ToolAdd,
    ToolEcho,
    ToolPing,
    ToolTakePhoto,
    UserIntent,
)


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
