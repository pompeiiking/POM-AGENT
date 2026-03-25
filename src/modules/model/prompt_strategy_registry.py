"""可插拔系统提示词后处理：``builtin:none`` 或 ``entrypoint:<name>``（组 ``pompeii_agent.prompt_strategies``）。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import Any, Protocol

from core.session.session import Session
from modules.assembly.types import Context
from modules.model.config import ModelProvider


class PromptStrategyRegistryError(ValueError):
    pass


class PromptStrategyFn(Protocol):
    def __call__(
        self,
        *,
        system_prompt: str | None,
        provider: ModelProvider,
        session: Session,
        context: Context,
        skill_registry: Mapping[str, Any],
    ) -> str | None:
        """
        返回 ``None`` 表示保持 ``system_prompt`` 不变（含保持 ``None``）。
        返回 ``str`` 则替换为新的系统提示词（可为空串）。
        """


def validate_prompt_strategy_ref_format(ref: str) -> None:
    r = str(ref).strip()
    if not r:
        raise PromptStrategyRegistryError("prompt_strategy_ref must be non-empty")
    if r == "builtin:none":
        return
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise PromptStrategyRegistryError("prompt_strategy entrypoint name must be non-empty")
        return
    raise PromptStrategyRegistryError(
        "prompt_strategy_ref must be 'builtin:none' or 'entrypoint:<name>'"
    )


def resolve_prompt_strategy(
    ref: str,
    *,
    entrypoint_group: str = "pompeii_agent.prompt_strategies",
) -> PromptStrategyFn:
    validate_prompt_strategy_ref_format(ref)
    r = str(ref).strip()
    if r == "builtin:none":

        def _noop(
            *,
            system_prompt: str | None,
            provider: ModelProvider,
            session: Session,
            context: Context,
            skill_registry: Mapping[str, Any],
        ) -> str | None:
            return None

        return _noop
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        eps = entry_points()
        selected = eps.select(group=entrypoint_group) if hasattr(eps, "select") else [e for e in eps if e.group == entrypoint_group]
        for ep in selected:
            if str(ep.name).strip() == name:
                fn = ep.load()
                if not callable(fn):
                    raise PromptStrategyRegistryError(f"prompt strategy {name!r} is not callable")
                return fn  # type: ignore[return-value]
        raise PromptStrategyRegistryError(
            f"prompt strategy entrypoint {name!r} not found in group {entrypoint_group!r}"
        )
    raise PromptStrategyRegistryError("unreachable prompt_strategy_ref")


def run_prompt_strategy(
    ref: str,
    *,
    system_prompt: str | None,
    provider: ModelProvider,
    session: Session,
    context: Context,
    skill_registry: Mapping[str, Any],
) -> str | None:
    fn: Callable[..., Any] = resolve_prompt_strategy(ref)
    out = fn(
        system_prompt=system_prompt,
        provider=provider,
        session=session,
        context=context,
        skill_registry=skill_registry,
    )
    return system_prompt if out is None else out
