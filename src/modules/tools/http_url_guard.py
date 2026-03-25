from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .network_policy import ToolNetworkPolicyConfig


class HttpUrlGuardError(ValueError):
    """工具侧 HTTP URL 未通过关卡④-a 校验。"""


def enforce_http_url_policy(url: str, policy: ToolNetworkPolicyConfig) -> None:
    """若 `policy.http_url_guard_enabled`，对 URL 执行 `assert_safe_http_tool_url`。"""
    if not policy.http_url_guard_enabled:
        return
    assert_safe_http_tool_url(url, allowed_hosts=policy.http_url_allowed_hosts)


def assert_safe_http_tool_url(url: str, *, allowed_hosts: tuple[str, ...]) -> None:
    """
    供本地/MCP HTTP 类工具在发起请求前调用（MVP）：
    - 仅允许 http/https，禁止 userinfo（user:pass@）
    - 主机为字面 IP 时拒绝私网/环回/链路本地/多播/非全局单播等
    - 主机名为域名时必须在 `allowed_hosts` 中匹配（精确或 `*.suffix`）；不做 DNS 解析，故无法防御「恶意域名解析到内网」——生产应配合解析期策略或固定出口代理
    """
    raw = (url or "").strip()
    if not raw:
        raise HttpUrlGuardError("tool_http_url_empty")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise HttpUrlGuardError("tool_http_url_bad_scheme")

    if parsed.username is not None or parsed.password is not None:
        raise HttpUrlGuardError("tool_http_url_userinfo_forbidden")

    host = parsed.hostname
    if host is None or host == "":
        raise HttpUrlGuardError("tool_http_url_missing_host")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        _check_hostname_allowed(host, allowed_hosts)
        return

    if _blocked_ip_literal(ip):
        raise HttpUrlGuardError("tool_http_url_blocked_ip")


def multimodal_image_url_host_baseline_violation(hostname: str | None) -> str | None:
    """
    用户多模态 ``image_url`` 在**未启用** ``http_url_guard`` 白名单时，对主机名的基线拦截：
    拒绝空 host、``localhost``、以及私网/环回/链路本地等与 ``assert_safe_http_tool_url`` 一致的字面 IP。
    非字面 IP 的域名不在此拒绝（DNS 侧风险由宿主与可选 ``http_url_guard`` 承担）。
    """
    if hostname is None or str(hostname).strip() == "":
        return "missing_host"
    h = str(hostname).strip()
    if h.casefold() == "localhost":
        return "localhost_forbidden"
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return None
    if _blocked_ip_literal(ip):
        return "blocked_ip_literal"
    return None


def _blocked_ip_literal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_multicast or ip.is_link_local or ip.is_loopback:
        return True
    if ip.version == 4:
        return ip.is_private or ip.is_reserved or not ip.is_global
    return ip.is_private or not ip.is_global


def _check_hostname_allowed(host: str, allowed_hosts: tuple[str, ...]) -> None:
    if not allowed_hosts:
        raise HttpUrlGuardError("tool_http_url_hostname_requires_allowlist")
    h = host.casefold()
    for entry in allowed_hosts:
        e = entry.strip().casefold()
        if not e:
            continue
        if e.startswith("*.") and len(e) > 2:
            suf = e[2:]
            if h == suf or h.endswith("." + suf):
                return
        elif h == e:
            return
    raise HttpUrlGuardError("tool_http_url_host_not_allowed")
