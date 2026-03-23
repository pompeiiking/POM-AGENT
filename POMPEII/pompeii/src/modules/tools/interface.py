from __future__ import annotations

from typing import Protocol

from core.session.session import Session
from core.types import ToolCall, ToolResult


class ToolModule(Protocol):
    def execute(self, session: Session, tool_call: ToolCall) -> ToolResult: ...

