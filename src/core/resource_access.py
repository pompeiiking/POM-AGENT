from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

# 与 resource_access.yaml 中 resources 键一致
RESOURCE_LONG_TERM_MEMORY = "long_term_memory"
# 用户多模态消息中 image_url 是否允许进入模型载荷（关卡⑤）
RESOURCE_MULTIMODAL_IMAGE_URL = "multimodal_image_url"

# 配置校验：`resource_access.profiles.*.resources` 的键须在此集合内（防静默拼写错误）
KNOWN_RESOURCE_IDS: frozenset[str] = frozenset(
    {
        RESOURCE_LONG_TERM_MEMORY,
        RESOURCE_MULTIMODAL_IMAGE_URL,
    }
)

ResourceAccessMode = Literal["allow", "deny"]
ResourceOperation = Literal["read", "write"]


@dataclass(frozen=True, slots=True)
class ResourceAccessRule:
    read: ResourceAccessMode
    write: ResourceAccessMode


@dataclass(frozen=True, slots=True)
class ResourceAccessProfile:
    """关卡⑤：按资源维度的读/写策略；未声明的资源默认允许。"""

    rules: Mapping[str, ResourceAccessRule]


class ResourceAccessEvaluator:
    def __init__(self, profile: ResourceAccessProfile) -> None:
        self._profile = profile

    def is_allowed(self, resource_id: str, operation: ResourceOperation) -> bool:
        rule = self._profile.rules.get(resource_id)
        if rule is None:
            return True
        mode = rule.read if operation == "read" else rule.write
        return mode == "allow"
