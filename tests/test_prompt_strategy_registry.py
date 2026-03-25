from __future__ import annotations

from unittest.mock import patch

import pytest

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from modules.assembly.types import Context
from modules.model.config import ModelProvider
from modules.model.prompt_strategy_registry import (
    PromptStrategyRegistryError,
    resolve_prompt_strategy,
    run_prompt_strategy,
    validate_prompt_strategy_ref_format,
)


def _session() -> Session:
    lim = SessionLimits(
        max_tokens=1,
        max_context_window=1,
        max_loops=1,
        timeout_seconds=1.0,
    )
    return Session(
        session_id="s1",
        user_id="u1",
        channel="http",
        config=SessionConfig(
            model="stub",
            skills=[],
            security="none",
            limits=lim,
            prompt_profile="default",
            prompt_strategy="default",
        ),
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


def test_validate_prompt_strategy_ref_format_ok() -> None:
    validate_prompt_strategy_ref_format("builtin:none")
    validate_prompt_strategy_ref_format("entrypoint:foo")


@pytest.mark.parametrize(
    "bad",
    ["", "  ", "builtin:other", "entrypoint:", "http://x", "foo"],
)
def test_validate_prompt_strategy_ref_format_rejects(bad: str) -> None:
    with pytest.raises(PromptStrategyRegistryError):
        validate_prompt_strategy_ref_format(bad)


def test_resolve_builtin_none() -> None:
    fn = resolve_prompt_strategy("builtin:none")
    p = ModelProvider(id="p", backend="stub", params={})
    ctx = Context(messages=[], current="", intent=None, meta={})
    assert fn(system_prompt="x", provider=p, session=_session(), context=ctx, skill_registry={}) is None


def test_run_prompt_strategy_applies_hook() -> None:
    p = ModelProvider(id="p", backend="stub", params={})
    ctx = Context(messages=[], current="", intent=None, meta={})

    def hook(
        *,
        system_prompt: str | None,
        provider: ModelProvider,
        session: Session,
        context: Context,
        skill_registry: dict,
    ) -> str | None:
        return "Z" + (system_prompt or "")

    with patch(
        "modules.model.prompt_strategy_registry.resolve_prompt_strategy",
        return_value=hook,
    ):
        out = run_prompt_strategy(
            "entrypoint:any",
            system_prompt="ab",
            provider=p,
            session=_session(),
            context=ctx,
            skill_registry={},
        )
    assert out == "Zab"


def test_run_prompt_strategy_builtin_none_unchanged() -> None:
    p = ModelProvider(id="p", backend="stub", params={})
    ctx = Context(messages=[], current="", intent=None, meta={})
    out = run_prompt_strategy(
        "builtin:none",
        system_prompt="keep",
        provider=p,
        session=_session(),
        context=ctx,
        skill_registry={},
    )
    assert out == "keep"
