from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.agent_core import AgentCoreImpl
from core.agent_types import AgentRequest
from core.kernel_config import KernelConfig
from core.session.session import SessionConfig, SessionLimits
from core.session.session_manager import SessionManagerImpl
from infra.sqlite_session_store import SqliteSessionStore
from core.types import ToolCall, ToolResult
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule


class FakeAssembly(AssemblyModule):
    def build_initial_context(self, session: Any, request: AgentRequest) -> Any:
        return {"history": [str(request.payload)]}

    def apply_tool_result(self, session: Any, tool_result: ToolResult) -> Any:
        return {"tool": tool_result.output}

    def format_final_reply(self, session: Any, model_output: Any) -> str:
        if isinstance(model_output, ModelOutput):
            return model_output.content or ""
        return str(model_output)


class FakeModel(ModelModule):
    def run(self, session: Any, context: Any) -> ModelOutput:
        return ModelOutput(kind="text", content="ok")


class FakeTools(ToolModule):
    def execute(self, session: Any, tool_call: ToolCall) -> ToolResult:
        return ToolResult(name=tool_call.name, output={"arguments": dict(tool_call.arguments)})


def _test_config_provider(user_id: str, channel: str) -> SessionConfig:
    _ = (user_id, channel)
    return SessionConfig(
        model="fake",
        skills=[],
        security="none",
        limits=SessionLimits(
            max_tokens=9999,
            max_context_window=9999,
            max_loops=10,
            timeout_seconds=9999.0,
            assembly_tail_messages=20,
            summary_tail_messages=12,
            summary_excerpt_chars=200,
        ),
    )


def main() -> None:
    store = SqliteSessionStore.ephemeral()
    session_manager = SessionManagerImpl(store)
    core = AgentCoreImpl(
        session_manager=session_manager,
        assembly=FakeAssembly(),
        model=FakeModel(),
        tools=FakeTools(),
        config_provider=_test_config_provider,
        kernel_config=KernelConfig(
            core_max_loops=10,
            max_tool_calls_per_run=3,
            tool_allowlist=["echo", "take_photo"],
            tool_confirmation_required=["take_photo"],
        ),
    )

    response = core.handle(
        AgentRequest(
            request_id="req_1",
            user_id="u1",
            channel="cli",
            payload={"text": "hi"},
        )
    )
    assert response.reason == "ok"
    assert response.reply_text == "ok"
    print("smoke ok")


if __name__ == "__main__":
    main()

