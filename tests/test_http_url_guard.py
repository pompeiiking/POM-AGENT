from __future__ import annotations

import pytest

from app.config_loaders.tool_registry_loader import ToolRegistrySource, load_tool_registry_config
from modules.tools.http_url_guard import (
    HttpUrlGuardError,
    assert_safe_http_tool_url,
    enforce_http_url_policy,
    multimodal_image_url_host_baseline_violation,
)
from modules.tools.network_policy import ToolNetworkPolicyConfig


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://example.com/x", ("example.com",)),
        ("http://EXAMPLE.com/", ("example.com",)),
        ("https://api.example.com/", ("*.example.com",)),
        ("https://example.com/", ("*.example.com",)),
    ],
)
def test_hostname_allowlist_ok(url: str, allowed: tuple[str, ...]) -> None:
    assert_safe_http_tool_url(url, allowed_hosts=allowed)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/",
        "https://sub.example.com/",
    ],
)
def test_hostname_not_in_allowlist(url: str) -> None:
    with pytest.raises(HttpUrlGuardError, match="tool_http_url_host_not_allowed"):
        assert_safe_http_tool_url(url, allowed_hosts=("example.com",))


def test_hostname_requires_allowlist_when_non_ip() -> None:
    with pytest.raises(HttpUrlGuardError, match="tool_http_url_hostname_requires_allowlist"):
        assert_safe_http_tool_url("https://example.com/", allowed_hosts=())


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://192.168.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://[fe80::1]/",
    ],
)
def test_literal_ip_blocked(url: str) -> None:
    with pytest.raises(HttpUrlGuardError, match="tool_http_url_blocked_ip"):
        assert_safe_http_tool_url(url, allowed_hosts=())


def test_public_ip_allowed_without_hostname_allowlist() -> None:
    assert_safe_http_tool_url("http://8.8.8.8/path", allowed_hosts=())


def test_bad_scheme() -> None:
    with pytest.raises(HttpUrlGuardError, match="tool_http_url_bad_scheme"):
        assert_safe_http_tool_url("ftp://example.com/", allowed_hosts=("example.com",))


def test_userinfo_forbidden() -> None:
    with pytest.raises(HttpUrlGuardError, match="tool_http_url_userinfo_forbidden"):
        assert_safe_http_tool_url("http://user:pass@example.com/", allowed_hosts=("example.com",))


def test_enforce_respects_policy_flag() -> None:
    pol = ToolNetworkPolicyConfig(http_url_guard_enabled=False)
    enforce_http_url_policy("http://127.0.0.1/", pol)

    pol_on = ToolNetworkPolicyConfig(http_url_guard_enabled=True, http_url_allowed_hosts=("example.com",))
    enforce_http_url_policy("https://example.com/a", pol_on)
    with pytest.raises(HttpUrlGuardError):
        enforce_http_url_policy("https://127.0.0.1/", pol_on)


def test_load_yaml_http_url_fields(tmp_path) -> None:
    p = tmp_path / "tools.yaml"
    p.write_text(
        """
tools:
  local_handlers: {}
  device_routes: []
  network_policy:
    http_url_guard_enabled: true
    http_url_allowed_hosts: ["api.example.com", "*.openai.com"]
""",
        encoding="utf-8",
    )
    cfg = load_tool_registry_config(ToolRegistrySource(path=p))
    assert cfg.network_policy.http_url_guard_enabled is True
    assert cfg.network_policy.http_url_allowed_hosts == ("api.example.com", "*.openai.com")


def test_multimodal_image_url_host_baseline_localhost() -> None:
    assert multimodal_image_url_host_baseline_violation("localhost") == "localhost_forbidden"


def test_multimodal_image_url_host_baseline_private_ip() -> None:
    assert multimodal_image_url_host_baseline_violation("127.0.0.1") == "blocked_ip_literal"
    assert multimodal_image_url_host_baseline_violation("192.168.1.1") == "blocked_ip_literal"


def test_multimodal_image_url_host_baseline_public_ip_ok() -> None:
    assert multimodal_image_url_host_baseline_violation("8.8.8.8") is None


def test_multimodal_image_url_host_baseline_domain_ok() -> None:
    assert multimodal_image_url_host_baseline_violation("example.com") is None
