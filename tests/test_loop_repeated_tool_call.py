from __future__ import annotations

from core.agent_core import AgentCoreImpl
from core.agent_types import AgentRequest
from core.kernel_config import KernelConfig
from core.policies.loop_policy import tool_call_fingerprint
from core.session.message_factory import new_message
from core.session.session import SessionConfig, SessionLimits
from core.session.session_manager import SessionManagerImpl
from core.types import ToolCall
from infra.sqlite_session_store import SqliteSessionStore
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule


class _Asm(AssemblyModule):
    def build_initial_context(self, session, request):
        return type("Ctx", (), {"messages": [], "current": "", "intent": None, "meta": {}, "memory_context_block": None})()

    def apply_tool_result(self, session, tool_result):
        return type("Ctx", (), {"messages": [], "current": "ok", "intent": None, "meta": {}, "memory_context_block": None})()

    def format_final_reply(self, session, model_output):
        return str(model_output)


class _SameToolTwiceModel(ModelModule):
    def __init__(self) -> None:
        self._n = 0
        self._call = ToolCall(name="echo", arguments={"text": "same"}, call_id="c1")

    def run(self, session, context):
        self._n += 1
        return ModelOutput(kind="tool_call", tool_call=self._call)


class _EchoTools(ToolModule):
    def execute(self, session, tool_call):
        from core.types import ToolResult

        return ToolResult(name=tool_call.name, output={"echo": tool_call.arguments.get("text")})


def test_repeated_identical_tool_call_terminates_before_second_execute() -> None:
    store = SqliteSessionStore.ephemeral()
    manager = SessionManagerImpl(store)
    core = AgentCoreImpl(
        session_manager=manager,
        assembly=_Asm(),
        model=_SameToolTwiceModel(),
        tools=_EchoTools(),
        config_provider=lambda u, c: SessionConfig(
            model="stub",
            skills=[],
            security="none",
            limits=SessionLimits(
                max_tokens=100,
                max_context_window=100,
                max_loops=10,
                timeout_seconds=60.0,
                assembly_tail_messages=20,
            ),
        ),
        kernel_config=KernelConfig(
            core_max_loops=10,
            max_tool_calls_per_run=10,
            tool_allowlist=["echo"],
            tool_confirmation_required=[],
        ),
        security_policies={},
    )
    sess0 = manager.create_session("u", "cli", core._config_provider("u", "cli"))
    sid = sess0.session_id
    manager.append_message(sid, new_message(role="user", content="hi", loop_index=0))
    session = manager.get_session(sid)
    assert session is not None
    ctx = core._assembly.build_initial_context(session, AgentRequest(request_id="r1", user_id="u", channel="cli", payload="hi"))
    out = core._run_loop("r1", session, ctx, bypass_tool_confirmation=True)
    assert out.reason == "repeated_tool_call"
    assert out.error is not None


def test_tool_call_fingerprint_stable_for_key_order() -> None:
    a = ToolCall(name="echo", arguments={"b": 1, "a": 2}, call_id="x")
    b = ToolCall(name="echo", arguments={"a": 2, "b": 1}, call_id="y")
    assert tool_call_fingerprint(a) == tool_call_fingerprint(b)
