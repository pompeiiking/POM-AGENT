"""
最小内核示例：装配一次 ``AgentCoreImpl``，使用 **stub** 模型发一条对话（无需 API Key）。

在**仓库根目录**执行::

    python examples/minimal_kernel.py

依赖：已安装本仓库依赖（``pip install -r requirements.txt`` 或 ``pip install -e .``），且 ``PYTHONPATH`` 含 ``src``（可编辑安装后从任意目录运行亦可，只要包可导入）。
"""
from __future__ import annotations

from pathlib import Path

from app.composition import build_core
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.session_config_loader import SessionConfigSource, load_session_config
from app.config_provider import in_memory_mapping_config_provider
from core.agent_types import AgentRequest
from core.user_intent import Chat


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    src_root = repo_root / "src"
    session_path = src_root / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
    model_path = src_root / "platform_layer" / "resources" / "config" / "model_providers.yaml"

    cfg = load_session_config(SessionConfigSource(path=session_path))
    cfg.model = "stub"
    session_mapping = {
        "session": {
            "model": cfg.model,
            "prompt_profile": cfg.prompt_profile,
            "prompt_strategy": cfg.prompt_strategy,
            "skills": list(cfg.skills),
            "security": cfg.security if isinstance(cfg.security, str) else "baseline",
            "limits": {
                "max_tokens": cfg.limits.max_tokens,
                "max_context_window": cfg.limits.max_context_window,
                "max_loops": cfg.limits.max_loops,
                "timeout_seconds": cfg.limits.timeout_seconds,
            },
        }
    }
    config_provider = in_memory_mapping_config_provider(session_mapping)

    core = build_core(
        config_provider=config_provider,
        model_registry=load_model_registry(ModelProviderSource(path=model_path)),
        src_root=src_root,
    )
    req = AgentRequest(
        request_id="minimal-ex-1",
        user_id="minimal-user",
        channel="minimal",
        payload="hello",
        intent=Chat(text="hello"),
    )
    resp = core.handle(req)
    print(resp.reply_text)


if __name__ == "__main__":
    main()
