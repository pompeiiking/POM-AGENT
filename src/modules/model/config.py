from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ModelProvider:
    """
    模型提供方配置基座。
    - id: 工程内唯一标识（例如 "stub" / "openai-gpt4" / "local-llm"）
    - backend: 实际后端类型（例如 "stub" / "http" / "openai" / "local"）
    - params: 与后端相关的配置（endpoint/model_name/api_key 等），由后续具体实现解释
    """

    id: str
    backend: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class ModelRegistry:
    """
    模型配置注册表。
    - providers: id -> ModelProvider 的映射
    - default_provider_id: 当会话 `SessionConfig.model` 未命中任何 id 时的回退
    """

    providers: Mapping[str, ModelProvider]
    default_provider_id: str

