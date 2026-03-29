"""
会话与模型注册表加载：对外仅从 ``pompeii_agent`` 导入，内部再调用 ``app.config_*``。

集成方不必 ``import app...`` 即可完成常见 YAML 配置装配。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.session_config_loader import SessionConfigSource, load_session_config
from app.config_provider import in_memory_mapping_config_provider, yaml_file_config_provider
from core.session.session import SessionConfig
from modules.model.config import ModelRegistry
from platform_layer.bundled_root import framework_root as _bundled_resources_root

ConfigProvider = Callable[[str, str], SessionConfig]


def bundled_config_dir(src_root: Path | None = None) -> Path:
    """默认配置目录：``<src_root>/platform_layer/resources/config``。"""
    base = src_root if src_root is not None else _bundled_resources_root()
    return base / "platform_layer" / "resources" / "config"


def bundled_session_defaults_path(src_root: Path | None = None) -> Path:
    return bundled_config_dir(src_root) / "session_defaults.yaml"


def bundled_model_providers_path(src_root: Path | None = None) -> Path:
    return bundled_config_dir(src_root) / "model_providers.yaml"


def load_session_config_yaml(path: Path | str) -> SessionConfig:
    """从 ``session_defaults.yaml`` 同类文件加载 ``SessionConfig``。"""
    return load_session_config(SessionConfigSource(path=Path(path)))


def load_model_registry_yaml(path: Path | str) -> ModelRegistry:
    """从 ``model_providers.yaml`` 同类文件加载模型注册表。"""
    return load_model_registry(ModelProviderSource(path=Path(path)))


def _session_config_to_mapping(cfg: SessionConfig) -> dict[str, Any]:
    sec = cfg.security if isinstance(cfg.security, str) else "baseline"
    lim = cfg.limits
    return {
        "session": {
            "model": cfg.model,
            "prompt_profile": cfg.prompt_profile,
            "prompt_strategy": cfg.prompt_strategy,
            "skills": list(cfg.skills),
            "security": sec,
            "limits": {
                "max_tokens": lim.max_tokens,
                "max_context_window": lim.max_context_window,
                "max_loops": lim.max_loops,
                "timeout_seconds": lim.timeout_seconds,
                "assembly_tail_messages": lim.assembly_tail_messages,
                "summary_tail_messages": lim.summary_tail_messages,
                "summary_excerpt_chars": lim.summary_excerpt_chars,
                "assembly_message_max_chars": lim.assembly_message_max_chars,
                "assembly_approx_context_tokens": lim.assembly_approx_context_tokens,
                "assembly_compress_tool_max_chars": lim.assembly_compress_tool_max_chars,
                "assembly_compress_early_turn_chars": lim.assembly_compress_early_turn_chars,
                "assembly_token_counter": lim.assembly_token_counter,
                "assembly_tiktoken_encoding": lim.assembly_tiktoken_encoding,
            },
        },
    }


def session_provider_from_yaml(
    path: Path | str,
    *,
    override_model: str | None = None,
) -> ConfigProvider:
    """
    基于会话 YAML 构造 ``config_provider``（供 ``create_kernel`` 使用）。

    - ``override_model`` 为 ``None``：始终从磁盘读文件（各 user/channel 同一份模板逻辑上由 YAML 决定）。
    - 非 ``None``：先加载 YAML 再覆盖 ``model``（常用于本地 ``stub``、无 API Key）。
    """
    p = Path(path)
    if override_model is None:
        return yaml_file_config_provider(p)
    cfg = load_session_config(SessionConfigSource(path=p))
    cfg = replace(cfg, model=override_model)
    return in_memory_mapping_config_provider(_session_config_to_mapping(cfg))


__all__ = [
    "ConfigProvider",
    "SessionConfig",
    "ModelRegistry",
    "bundled_config_dir",
    "bundled_model_providers_path",
    "bundled_session_defaults_path",
    "load_model_registry_yaml",
    "load_session_config_yaml",
    "session_provider_from_yaml",
]
