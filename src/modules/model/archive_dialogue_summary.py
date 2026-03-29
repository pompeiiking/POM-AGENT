from __future__ import annotations

import os
from typing import Any

import httpx

from modules.model.config import ModelProvider, ModelRegistry

_DEFAULT_SYSTEM_PROMPT = (
    "你是会话归档助手。根据下面给出的对话摘录，用简洁中文总结主题、关键决定与待办（若有）。"
    "不要编造对话中不存在的事实。篇幅控制在约 200 字以内，除非对话极长可适当加长。"
)


def _effective_backend(provider: ModelProvider) -> str:
    b = provider.backend.strip().lower()
    return b if b in ("stub", "openai_compatible") else "stub"


def _api_key_env_name(provider: ModelProvider) -> str | None:
    raw = provider.params.get("api_key_env")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def summarize_dialogue_for_archive(
    *,
    registry: ModelRegistry,
    provider_id: str,
    dialogue_plain: str,
    max_output_chars: int,
    system_prompt: str,
) -> str:
    """
    为已归档会话生成 LLM 摘要（OpenAI 兼容 chat/completions）；stub 后端则返回确定性占位文本。
    """
    pid = provider_id.strip() or registry.default_provider_id
    provider = registry.providers.get(pid) or registry.providers.get(registry.default_provider_id)
    if provider is None:
        raise RuntimeError("archive_llm_summary: no model provider resolved")

    sys_p = system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT
    dialogue = dialogue_plain.strip()
    if not dialogue:
        return ""

    backend = _effective_backend(provider)
    if backend == "stub":
        cap = max(1, min(max_output_chars, 800))
        frag = dialogue[:cap]
        out = f"[stub归档摘要] {frag}"
        return out[:max_output_chars]

    env_name = _api_key_env_name(provider)
    if not env_name or not os.environ.get(env_name, "").strip():
        raise RuntimeError(f"archive_llm_summary: missing API key for provider {provider.id!r} (env {env_name!r})")

    default_base = "https://api.openai.com"
    base_url = str(provider.params.get("base_url", default_base)).rstrip("/")
    url = f"{base_url}/v1/chat/completions"
    api_key = os.environ[env_name].strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    user_block = f"以下是对话摘录：\n\n{dialogue_plain}"
    default_model = "gpt-4o-mini"
    payload: dict[str, Any] = {
        "model": provider.params.get("model", default_model),
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_block},
        ],
        "max_tokens": min(2048, max(256, max_output_chars // 2)),
    }
    timeout = provider.params.get("timeout", 60.0)
    timeout_f = float(timeout) if isinstance(timeout, (int, float)) else 60.0

    with httpx.Client(timeout=timeout_f) as client:
        resp = client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("archive_llm_summary: empty choices from API")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"archive_llm_summary: unexpected message content: {content!r}")
    text = content.strip()
    if len(text) > max_output_chars:
        return text[:max_output_chars]
    return text
