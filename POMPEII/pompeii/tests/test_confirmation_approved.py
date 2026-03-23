from __future__ import annotations

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


class _Asm(AssemblyModule):
    def build_initial_context(self, session: Any, request: Any) -> Any:
        from modules.assembly.types import Context

        return Context(messages=list(session.messages), current=str(request.payload), intent=request.intent, meta={})

    def apply_tool_result(self, session: Any, tool_result: ToolResult) -> Any:
        from modules.assembly.types import Context

        return Context(messages=list(session.messages), current="x", intent=None, meta={})

    def format_final_reply(self, session: Any, model_output: Any) -> str:
        if isinstance(model_output, ModelOutput):
            return model_output.content or ""
        return str(model_output)


class _Model(ModelModule):
    def __init__(self) -> None:
        self.run_count = 0

    def run(self, session: Any, context: Any) -> ModelOutput:
        self.run_count += 1
        if self.run_count == 1:
            return ModelOutput(
                kind="tool_call",
                tool_call=ToolCall(name="echo", arguments={"text": "hi"}, call_id="c1"),
            )
        return ModelOutput(kind="text", content="after-tool")


class _Tools(ToolModule):
    def execute(self, session: Any, tool_call: ToolCall) -> ToolResult:
        return ToolResult(name=tool_call.name, output={"ok": True})


def _cfg(uid: str, ch: str) -> SessionConfig:
    _ = (uid, ch)
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=10,
        timeout_seconds=60.0,
    )
    return SessionConfig(model="stub", skills=[], security="none", limits=lim)


def test_confirmation_approved_does_not_duplicate_user_message() -> None:
    store = SqliteSessionStore.ephemeral()
    sm = SessionManagerImpl(store)
    model = _Model()
    core = AgentCoreImpl(
        session_manager=sm,
        assembly=_Asm(),
        model=model,
        tools=_Tools(),
        config_provider=_cfg,
        kernel_config=KernelConfig(
            core_max_loops=8,
            max_tool_calls_per_run=5,
            tool_allowlist=["echo"],
            tool_confirmation_required=["echo"],
        ),
    )
    req = AgentRequest(
        request_id="r1",
        user_id="u",
        channel="c",
        payload="please echo",
        intent=None,
    )
    r1 = core.handle(req)
    assert r1.reason == "confirmation_required"
    sess = sm.get_session(r1.session.session_id)
    assert sess is not None
    user_msgs = [m for m in sess.messages if m.role == "user"]
    assert len(user_msgs) == 1

    tc = r1.pending_tool_call
    assert tc is not None
    r2 = core.handle_confirmation_approved(req, tc)
    assert r2.reason == "ok"
    sess2 = sm.get_session(r1.session.session_id)
    assert sess2 is not None
    user_msgs2 = [m for m in sess2.messages if m.role == "user"]
    assert len(user_msgs2) == 1
    assert model.run_count == 2
