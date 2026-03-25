from __future__ import annotations

import time

from core.agent_core import AgentCoreImpl
from core.agent_types import AgentRequest
from core.archive_llm_summary import ArchiveLlmSummaryBinding
from core.kernel_config import KernelConfig
from core.session.message_factory import new_message
from core.session.session import SessionConfig, SessionLimits
from core.session.session_manager import SessionManagerImpl
from core.types import ToolCall, ToolResult
from core.user_intent import SystemArchive
from infra.sqlite_session_store import SqliteSessionStore
from modules.assembly.interface import AssemblyModule
from modules.model.archive_dialogue_summary import summarize_dialogue_for_archive
from modules.model.config import ModelProvider, ModelRegistry
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule


class _Asm(AssemblyModule):
    def build_initial_context(self, session, request):
        return {}

    def apply_tool_result(self, session, tool_result):
        return {}

    def format_final_reply(self, session, model_output):
        return str(model_output)


class _Mdl(ModelModule):
    def run(self, session, context):
        return ModelOutput(kind="text", content="x")


class _Tls(ToolModule):
    def execute(self, session, tool_call: ToolCall) -> ToolResult:
        return ToolResult(name=tool_call.name, output={})


def _cfg(_u: str, _c: str) -> SessionConfig:
    return SessionConfig(
        model="stub",
        skills=[],
        security="none",
        limits=SessionLimits(100, 100, 3, 60.0),
    )


def test_archive_command_schedules_llm_summary() -> None:
    store = SqliteSessionStore.ephemeral()
    mgr = SessionManagerImpl(store)

    def summarize(
        *,
        provider_id: str,
        dialogue_plain: str,
        max_output_chars: int,
        system_prompt: str,
    ) -> str:
        _ = (provider_id, max_output_chars, system_prompt)
        return "SYNTH_LINE"

    binding = ArchiveLlmSummaryBinding(
        provider_id="stub",
        max_dialogue_chars=8000,
        max_output_chars=500,
        system_prompt="",
        summarize=summarize,
    )
    core = AgentCoreImpl(
        session_manager=mgr,
        assembly=_Asm(),
        model=_Mdl(),
        tools=_Tls(),
        config_provider=_cfg,
        kernel_config=KernelConfig(
            core_max_loops=3,
            max_tool_calls_per_run=2,
            tool_allowlist=["echo"],
            tool_confirmation_required=[],
        ),
        archive_llm=binding,
    )
    s0 = mgr.create_session("u1", "ch1", _cfg("u1", "ch1"))
    mgr.append_message(s0.session_id, new_message(role="user", content="hello archive", loop_index=0))
    req = AgentRequest(
        request_id="r1",
        user_id="u1",
        channel="ch1",
        payload="/archive",
        intent=SystemArchive(),
    )
    core.handle(req)
    deadline = time.time() + 2.0
    while time.time() < deadline:
        rows = mgr.list_archives_for_user("u1", limit=5)
        if rows and rows[0].get("llm_summary_status") == "done":
            assert rows[0].get("llm_summary_text") == "SYNTH_LINE"
            return
        time.sleep(0.02)
    raise AssertionError("LLM archive summary did not complete")


def test_summarize_dialogue_stub_provider() -> None:
    reg = ModelRegistry(
        providers={"s": ModelProvider(id="s", backend="stub", params={})},
        default_provider_id="s",
    )
    t = summarize_dialogue_for_archive(
        registry=reg,
        provider_id="s",
        dialogue_plain="user: hi\nassistant: hello",
        max_output_chars=200,
        system_prompt="",
    )
    assert "[stub归档摘要]" in t


def test_summarize_dialogue_empty_returns_empty() -> None:
    reg = ModelRegistry(
        providers={"s": ModelProvider(id="s", backend="stub", params={})},
        default_provider_id="s",
    )
    assert (
        summarize_dialogue_for_archive(
            registry=reg,
            provider_id="s",
            dialogue_plain="   ",
            max_output_chars=200,
            system_prompt="",
        )
        == ""
    )
