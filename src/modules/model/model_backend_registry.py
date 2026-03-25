from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Protocol

from modules.model.config import ModelProvider
from modules.assembly.types import Context
from core.session.session import Session
from infra.prompt_cache import PromptCache
from modules.model.interface import ModelOutput


class ModelChatBackend(Protocol):
    """
    统一聊天推理后端入口。
    业界常见做法（如 LiteLLM、OpenRouter、各类 Gateway）是：
    - 用少数「协议适配器」（OpenAI 兼容、Anthropic Messages 等）覆盖多供应商；
    - 用配置（base_url、model、鉴权）区分路由，而不是每个供应商一份手写分支。
    """

    def __call__(
        self,
        provider: ModelProvider,
        session: Session,
        context: Context,
        message: str,
        *,
        skill_registry: dict[str, Any] | None,
        prompt_cache: PromptCache | None,
    ) -> ModelOutput:
        ...


class ModelBackendRegistryError(ValueError):
    pass


def resolve_model_chat_backend(
    ref: str,
    *,
    entrypoint_group: str = "pompeii_agent.model_backends",
) -> ModelChatBackend:
    r = str(ref).strip()
    if not r:
        r = "builtin:openai_chat"
    if r == "builtin:openai_chat":
        from modules.model.impl import run_openai_compatible_chat_impl

        return run_openai_compatible_chat_impl
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise ModelBackendRegistryError("model backend entrypoint name must be non-empty")
        eps = entry_points()
        selected = eps.select(group=entrypoint_group) if hasattr(eps, "select") else [e for e in eps if e.group == entrypoint_group]
        for ep in selected:
            if str(ep.name).strip() == name:
                fn = ep.load()
                if not callable(fn):
                    raise ModelBackendRegistryError(f"model backend {name!r} is not callable")
                return fn  # type: ignore[return-value]
        raise ModelBackendRegistryError(
            f"model backend entrypoint {name!r} not found in group {entrypoint_group!r}"
        )
    raise ModelBackendRegistryError("model_backend_ref must be 'builtin:openai_chat' or 'entrypoint:<name>'")
