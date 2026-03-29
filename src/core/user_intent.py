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
class SystemRemember:
    """显式写入长期记忆（由 MemoryOrchestrator 落标准库 + 向量投影）。"""
    text: str


@dataclass(frozen=True)
class SystemForget:
    """按短语 tombstone 长期记忆项（标准库 + 向量级联）。"""
    phrase: str


@dataclass(frozen=True)
class SystemPreference:
    """用户偏好 CRUD：/preference set|get|list|delete。"""
    action: str  # "set" | "get" | "list" | "delete"
    key: str = ""
    value: str = ""


@dataclass(frozen=True)
class SystemFact:
    """事实记录 CRUD：/fact add|get|list|delete。"""
    action: str  # "add" | "get" | "list" | "delete"
    statement: str = ""


@dataclass(frozen=True)
class SystemDelegate:
    """
    多 Agent 协作（架构 ver0.4 Port.emit delegate）：
    由核心登记并经 Port 发出 DelegateEvent；具体子代理路由由网关在事件消费侧实现。
    """

    target: str
    payload: str


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
    SystemRemember,
    SystemForget,
    SystemPreference,
    SystemFact,
    SystemDelegate,
    ToolEcho,
    ToolTakePhoto,
    ToolPing,
    ToolAdd,
]
