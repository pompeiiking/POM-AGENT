from __future__ import annotations

from dataclasses import replace

from core.agent_core import AgentCoreImpl
from core.agent_types import AgentRequest
from core.kernel_config import KernelConfig
from core.session.session import SessionConfig, SessionLimits
from core.session.session_manager import SessionManagerImpl
from core.user_intent import SystemDelegate
from infra.sqlite_session_store import SqliteSessionStore
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule
from port.agent_port import CliMode, GenericAgentPort
from port.events import DelegateEvent
from port.http_emitter import HttpEmitter
from port.input_events import UserMessageInput
from port.request_factory import session_request_factory


class _Asm(AssemblyModule):
    def build_initial_context(self, session, request):
        return None

    def apply_tool_result(self, session, tool_result):
        return None

    def format_final_reply(self, session, model_output):
        return str(model_output)


class _Mdl(ModelModule):
    def run(self, session, context):
        return ModelOutput(kind="text", content="x")


class _Tls(ToolModule):
    def execute(self, session, tool_call):
        raise NotImplementedError


def _cfg(_u: str, _c: str) -> SessionConfig:
    return SessionConfig(
        model="stub",
        skills=[],
        security="baseline",
        limits=SessionLimits(
            max_tokens=9999,
            max_context_window=9999,
            max_loops=10,
            timeout_seconds=9999.0,
            assembly_tail_messages=20,
        ),
    )


def _core_with_baseline_security() -> AgentCoreImpl:
    from types import SimpleNamespace

    store = SqliteSessionStore.ephemeral()
    manager = SessionManagerImpl(store)
    pol = SimpleNamespace(
        id="baseline",
        input_max_chars=12000,
        max_requests_per_minute=1000,
        guard_enabled=False,
        default_tool_risk_level="low",
        tool_confirmation_level="high",
        tool_risk_overrides={},
        guard_block_patterns=(),
        guard_tool_output_redaction="[guard_blocked_tool_output]",
        guard_evaluator_ref="builtin:default",
        guard_model_ref="builtin:none",
        guard_model_provider_id=None,
        tool_output_max_chars=0,
        tool_output_truncation_marker="…[truncated]",
        tool_output_max_chars_overrides={},
        default_tool_output_trust="high",
        tool_output_trust_overrides={},
        mcp_tool_output_trust="low",
        device_tool_output_trust="low",
        http_fetch_tool_output_trust="low",
        tool_output_max_chars_by_trust={},
        tool_output_injection_patterns=(),
        tool_output_injection_redaction="[tool_output_injection_blocked]",
    )
    return AgentCoreImpl(
        session_manager=manager,
        assembly=_Asm(),
        model=_Mdl(),
        tools=_Tls(),
        config_provider=_cfg,
        kernel_config=KernelConfig(
            core_max_loops=10,
            max_tool_calls_per_run=3,
            tool_allowlist=["echo"],
            tool_confirmation_required=[],
        ),
        security_policies={"baseline": pol},
    )


def test_core_handle_delegate_returns_response_fields() -> None:
    core = _core_with_baseline_security()
    r = AgentRequest(
        request_id="d1",
        user_id="u",
        channel="c",
        payload="/delegate sub_agent hello world",
        intent=SystemDelegate(target="sub_agent", payload="hello world"),
    )
    out = core.handle(r)
    assert out.reason == "delegate"
    assert out.delegate_target == "sub_agent"
    assert out.delegate_payload == "hello world"
    assert out.reply_text and "delegate" in out.reply_text.lower()


def test_delegate_denied_when_not_in_kernel_allowlist() -> None:
    core = _core_with_baseline_security()
    core._kernel_config = replace(core._kernel_config, delegate_target_allowlist=("allowed_only",))
    r = AgentRequest(
        request_id="d2",
        user_id="u",
        channel="c",
        payload="/delegate other hi",
        intent=SystemDelegate(target="other", payload="hi"),
    )
    out = core.handle(r)
    assert out.reason == "delegate_target_denied"
    assert out.error is not None


def test_port_emits_delegate_then_reply() -> None:
    core = _core_with_baseline_security()
    port = GenericAgentPort(
        mode=CliMode(),
        core=core,
        request_factory=session_request_factory(user_id="u", channel="http"),
        emitter=HttpEmitter(),
    )
    em = HttpEmitter()
    port.handle(
        UserMessageInput(kind="user_message", text="/delegate worker do task"),
        user_id="u",
        channel="http",
        emitter=em,
    )
    kinds = [e["kind"] for e in em.dump()]
    assert kinds[0] == "delegate"
    assert kinds[1] == "reply"
    d0 = em.events[0]
    assert isinstance(d0, DelegateEvent)
    assert d0.target == "worker"
    assert d0.payload == "do task"
