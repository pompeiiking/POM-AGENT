from __future__ import annotations

import pytest

from app.config_loaders.model_provider_loader import ModelProviderLoaderError, ModelProviderSource, load_model_registry
from core.types import ToolCall
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from modules.assembly.types import Context
from modules.model.config import ModelProvider, ModelRegistry
from modules.model.impl import (
    ModelModuleImpl,
    _dispatch_chat_with_failover,
    _expand_provider_failover_sequence,
)
from modules.model.interface import ModelOutput
from modules.model.openai_failure import openai_output_suggests_failover


def test_openai_output_suggests_failover() -> None:
    assert openai_output_suggests_failover(ModelOutput(kind="text", content="模型 [x] 调用失败：oops"))
    assert openai_output_suggests_failover(
        ModelOutput(kind="text", content="模型 [x] 未配置：请在环境变量 FOO 中设置 API Key。")
    )
    assert openai_output_suggests_failover(
        ModelOutput(kind="text", content="模型 [x] 调用过于频繁：本窗口内已达 1 次上限，约 3s 后可重试。")
    )
    assert not openai_output_suggests_failover(ModelOutput(kind="text", content="hello world"))
    assert not openai_output_suggests_failover(
        ModelOutput(kind="tool_call", tool_call=ToolCall(name="x", arguments={}, call_id=None))
    )


def test_expand_provider_failover_sequence_dedupes() -> None:
    a = ModelProvider(id="a", backend="openai_compatible", params={}, failover_chain=("b", "a"))
    b = ModelProvider(id="b", backend="openai_compatible", params={})
    reg = ModelRegistry(providers={"a": a, "b": b}, default_provider_id="a")
    seq = _expand_provider_failover_sequence(a, reg)
    assert [p.id for p in seq] == ["a", "b"]


def test_load_model_registry_failover_chain(tmp_path) -> None:
    p = tmp_path / "model_providers.yaml"
    p.write_text(
        """
default_provider: p1
providers:
  p1:
    backend: openai_compatible
    params: {}
    failover_chain: ["p2"]
  p2:
    backend: stub
    params: {}
""",
        encoding="utf-8",
    )
    reg = load_model_registry(ModelProviderSource(path=p))
    assert reg.providers["p1"].failover_chain == ("p2",)


def test_load_model_registry_rejects_unknown_failover_id(tmp_path) -> None:
    p = tmp_path / "model_providers.yaml"
    p.write_text(
        """
default_provider: p1
providers:
  p1:
    backend: openai_compatible
    params: {}
    failover_chain: ["missing"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelProviderLoaderError, match="unknown provider"):
        load_model_registry(ModelProviderSource(path=p))


def test_load_model_registry_rejects_self_failover(tmp_path) -> None:
    p = tmp_path / "model_providers.yaml"
    p.write_text(
        """
default_provider: p1
providers:
  p1:
    backend: openai_compatible
    params: {}
    failover_chain: ["p1"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelProviderLoaderError, match="must not include"):
        load_model_registry(ModelProviderSource(path=p))


def test_dispatch_chat_failover_falls_through_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_dispatch_openai(
        provider: ModelProvider,
        session: Session,
        context: Context,
        message: str,
        *,
        skill_registry=None,
        prompt_cache=None,
    ):
        calls.append(provider.id)
        return ModelOutput(
            kind="text",
            content=f"\u6a21\u578b [{provider.id}] \u8c03\u7528\u5931\u8d25\uff1anetwork",
        )

    monkeypatch.setattr("modules.model.impl._dispatch_openai_compatible_chat", fake_dispatch_openai)

    primary = ModelProvider(id="a", backend="openai_compatible", params={}, failover_chain=("s",))
    stubp = ModelProvider(id="s", backend="stub", params={})
    reg = ModelRegistry(providers={"a": primary, "s": stubp}, default_provider_id="a")
    lim = SessionLimits(max_tokens=10, max_context_window=10, max_loops=3, timeout_seconds=1.0)
    cfg = SessionConfig(model="a", skills=[], security="x", limits=lim)
    sess = Session(
        session_id="s",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    ctx = Context(messages=[], current="hi", intent=None, meta={})
    out = _dispatch_chat_with_failover(
        primary=primary,
        registry=reg,
        session=sess,
        context=ctx,
        message="hi",
        skill_registry={},
        prompt_cache=None,
    )
    assert calls == ["a"]
    assert "[model]" in str(out.content)


def test_model_module_impl_openai_primary_uses_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = ModelProvider(id="a", backend="openai_compatible", params={}, failover_chain=("s",))
    stubp = ModelProvider(id="s", backend="stub", params={})
    reg = ModelRegistry(providers={"a": primary, "s": stubp}, default_provider_id="a")
    mod = ModelModuleImpl(registry=reg, skill_registry={})

    def boom(*_a, **_k):
        return ModelOutput(kind="text", content="\u6a21\u578b [a] \u8c03\u7528\u5931\u8d25\uff1ax")

    monkeypatch.setattr("modules.model.impl._dispatch_openai_compatible_chat", boom)

    lim = SessionLimits(max_tokens=10, max_context_window=10, max_loops=3, timeout_seconds=1.0)
    cfg = SessionConfig(model="a", skills=[], security="x", limits=lim)
    sess = Session(
        session_id="s",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    ctx = Context(messages=[], current="x", intent=None, meta={})
    out = mod.run(sess, ctx)
    assert out.kind == "text"
    assert "[model]" in (out.content or "")
