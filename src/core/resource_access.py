from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping

# 与 resource_access.yaml 中 resources 键一致
RESOURCE_LONG_TERM_MEMORY = "long_term_memory"
# 用户多模态消息中 image_url 是否允许进入模型载荷（关卡⑤）
RESOURCE_MULTIMODAL_IMAGE_URL = "multimodal_image_url"
# 远端检索/向量服务调用（HTTP）
RESOURCE_REMOTE_RETRIEVAL = "remote_retrieval"
# 会话数据访问
RESOURCE_SESSION_DATA = "session_data"
# 工具执行权限
RESOURCE_TOOL_EXECUTION = "tool_execution"
# 设备访问权限
RESOURCE_DEVICE_ACCESS = "device_access"
# 外部 API 调用
RESOURCE_EXTERNAL_API = "external_api"
# 文件系统访问
RESOURCE_FILESYSTEM = "filesystem"

# 配置校验：`resource_access.profiles.*.resources` 的键须在此集合内（防静默拼写错误）
KNOWN_RESOURCE_IDS: frozenset[str] = frozenset(
    {
        RESOURCE_LONG_TERM_MEMORY,
        RESOURCE_MULTIMODAL_IMAGE_URL,
        RESOURCE_REMOTE_RETRIEVAL,
        RESOURCE_SESSION_DATA,
        RESOURCE_TOOL_EXECUTION,
        RESOURCE_DEVICE_ACCESS,
        RESOURCE_EXTERNAL_API,
        RESOURCE_FILESYSTEM,
    }
)

_audit_logger = logging.getLogger("pompeii.resource_audit")

ResourceAccessMode = Literal["allow", "deny"]
ResourceOperation = Literal["read", "write"]


@dataclass(frozen=True, slots=True)
class ResourceAccessRule:
    read: ResourceAccessMode
    write: ResourceAccessMode
    read_requires_approval: bool = False
    write_requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class ResourceAccessProfile:
    """关卡⑤：按资源维度的读/写策略；未声明的资源默认允许。"""

    rules: Mapping[str, ResourceAccessRule]


@dataclass(frozen=True, slots=True)
class ResourceAccessEvent:
    """资源访问审计事件"""
    resource_id: str
    operation: ResourceOperation
    allowed: bool
    requires_approval: bool
    user_id: str | None
    session_id: str | None
    timestamp: datetime
    context: str | None = None


class ResourceAccessEvaluator:
    """
    关卡⑤ 资源访问评估器
    
    职责：
    - 评估资源访问权限（读/写）
    - 检查是否需要审批
    - 记录审计日志
    """

    def __init__(
        self,
        profile: ResourceAccessProfile,
        *,
        audit_enabled: bool = True,
    ) -> None:
        self._profile = profile
        self._audit_enabled = audit_enabled

    def is_allowed(self, resource_id: str, operation: ResourceOperation) -> bool:
        rule = self._profile.rules.get(resource_id)
        if rule is None:
            return True
        mode = rule.read if operation == "read" else rule.write
        return mode == "allow"

    def requires_approval(self, resource_id: str, operation: ResourceOperation) -> bool:
        rule = self._profile.rules.get(resource_id)
        if rule is None:
            return False
        if not self.is_allowed(resource_id, operation):
            return False
        return rule.read_requires_approval if operation == "read" else rule.write_requires_approval

    def check_and_audit(
        self,
        resource_id: str,
        operation: ResourceOperation,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        context: str | None = None,
    ) -> bool:
        """
        检查资源访问权限并记录审计日志。
        
        Args:
            resource_id: 资源 ID
            operation: 操作类型（read/write）
            user_id: 用户 ID（可选）
            session_id: 会话 ID（可选）
            context: 上下文说明（可选）
        
        Returns:
            是否允许访问
        """
        allowed = self.is_allowed(resource_id, operation)
        requires_approval = self.requires_approval(resource_id, operation)
        
        if self._audit_enabled:
            event = ResourceAccessEvent(
                resource_id=resource_id,
                operation=operation,
                allowed=allowed,
                requires_approval=requires_approval,
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.now(),
                context=context,
            )
            self._log_audit_event(event)
        
        return allowed

    def _log_audit_event(self, event: ResourceAccessEvent) -> None:
        """记录审计事件到日志"""
        status = "ALLOWED" if event.allowed else "DENIED"
        approval = " (requires_approval)" if event.requires_approval else ""
        
        log_data = {
            "resource_id": event.resource_id,
            "operation": event.operation,
            "status": status,
            "user_id": event.user_id,
            "session_id": event.session_id,
            "timestamp": event.timestamp.isoformat(),
            "context": event.context,
        }
        
        if event.allowed:
            _audit_logger.info(
                "Resource access %s%s: %s %s",
                status,
                approval,
                event.operation,
                event.resource_id,
                extra=log_data,
            )
        else:
            _audit_logger.warning(
                "Resource access %s: %s %s",
                status,
                event.operation,
                event.resource_id,
                extra=log_data,
            )
