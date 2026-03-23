from __future__ import annotations

from typing import Any, Protocol

from core.session.session import Session
from core.agent_types import AgentRequest
from core.types import ToolResult


class AssemblyModule(Protocol):
    # 首次构建 Context Window
    def build_initial_context(self, session: Session, request: AgentRequest) -> Any: ...

    # 工具结果回注时的追加路径
    def apply_tool_result(self, session: Session, tool_result: ToolResult) -> Any: ...

    # 最终回复的格式化（通常传入 ModelOutput；兼容其它测试桩）
    def format_final_reply(self, session: Session, model_output: Any) -> str: ...

