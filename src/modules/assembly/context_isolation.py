"""
关卡② 上下文隔离（架构设计 ver0.4 §6.2 / §3.1）：

在送入 LLM 的文本外包一层稳定可解析的分区标记，区分系统说明、长期记忆、用户输入、
工具结果等来源，降低跨区 prompt injection 与区界混淆风险。

标记采用 HTML 注释形态，避免与 Markdown 代码块常见冲突；name/source/trust 仅允许
安全字符（字母数字与 _-.）。
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"^[a-zA-Z0-9_.-]+$")


def _sanitize_token(raw: str, *, label: str) -> str:
    s = str(raw).strip()
    if not s or not _TOKEN.fullmatch(s):
        raise ValueError(f"context isolation {label} must match [a-zA-Z0-9_.-]+, got {raw!r}")
    return s


def format_isolated_zone(
    zone_name: str,
    body: str,
    *,
    source: str,
    trust: str,
) -> str:
    """
    将 ``body`` 包在成对注释标记中。

    ``zone_name``: 逻辑分区，如 ``system`` / ``memory`` / ``user`` / ``tool_result`` /
    ``history_user`` / ``history_assistant`` / ``history_tool``。
    ``source`` / ``trust``: 架构中的来源与信任档（自由字符串，受 token 规则约束）。
    """
    z = _sanitize_token(zone_name, label="zone_name")
    src = _sanitize_token(source, label="source")
    tr = _sanitize_token(trust, label="trust")
    b = str(body)
    return (
        f"<!-- pompeii:zone-begin name={z} source={src} trust={tr} -->\n"
        f"{b}\n"
        f"<!-- pompeii:zone-end name={z} -->"
    )


def trust_for_tool_result_source(source: str | None) -> str:
    """与 ToolResult.source 对齐的默认 trust 档（关卡④ 来源在关卡② 呈现）。"""
    if source == "mcp":
        return "low"
    if source == "device":
        return "low"
    return "high"


def tool_execution_source_token(source: str | None) -> str:
    """写入 zone source= 的简短 token（须过 _sanitize_token）。"""
    s = (source or "").strip() or "local"
    if s in ("local", "mcp", "device"):
        return s
    if _TOKEN.fullmatch(s):
        return s
    return "unknown"
