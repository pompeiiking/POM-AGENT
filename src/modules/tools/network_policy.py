from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolNetworkPolicyConfig:
    """
    关卡④-a 网络策略（MVP）：约束经 MCP 的外联工具名；可选按工具名拒绝；
    可选 HTTP URL 校验（`http_url_guard`），供工具在发起请求前调用。
    """

    enabled: bool = False
    deny_tool_names: tuple[str, ...] = ()
    mcp_allowlist_enforced: bool = False
    mcp_tool_allowlist: tuple[str, ...] = ()
    http_url_guard_enabled: bool = False
    http_url_allowed_hosts: tuple[str, ...] = ()
    # ④-a：http_get 等工具在收到响应后校验 Content-Type 主类型（小写、去参数）；空前缀列表表示不启用
    http_blocked_content_type_prefixes: tuple[str, ...] = ()
