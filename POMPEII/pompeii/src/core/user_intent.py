"""
用户意图：在 Port 边界由唯一解析器产生，Core/Assembly/Model 只消费，不再解析原始字符串。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Chat:
    """普通对话，内容发往 LLM。"""
    text: str


@dataclass(frozen=True)
class SystemHelp:
    """系统帮助，由本地规则返回，不调用 LLM。"""
    pass


@dataclass(frozen=True)
class SystemSummary:
    """会话概要，由本地规则或后续 LLM 摘要。"""
    pass


@dataclass(frozen=True)
class SystemArchive:
    """将当前活跃会话标记为 ARCHIVED（SQLite 时写入 session_archives）。"""
    pass


@dataclass(frozen=True)
class ToolEcho:
    """触发 echo 工具。"""
    text: str


@dataclass(frozen=True)
class ToolTakePhoto:
    """触发 take_photo 设备请求。"""
    pass


@dataclass(frozen=True)
class ToolPing:
    """触发 MCP 演示工具 ping（需配置 MCP 与白名单）。"""
    pass


@dataclass(frozen=True)
class ToolAdd:
    """触发 MCP 演示工具 add。"""
    a: int
    b: int


UserIntent = Union[
    Chat,
    SystemHelp,
    SystemSummary,
    SystemArchive,
    ToolEcho,
    ToolTakePhoto,
    ToolPing,
    ToolAdd,
]
