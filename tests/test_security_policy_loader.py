from __future__ import annotations

from pathlib import Path

import pytest

from app.config_loaders.security_policy_loader import (
    SecurityPolicyLoaderError,
    SecurityPolicySource,
    load_security_policy_registry,
)


def _write_yaml(tmp_path, content: str):
    p = tmp_path / "security_policies.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_platform_baseline_declares_zone_injection_patterns() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "platform_layer"
        / "resources"
        / "config"
        / "security_policies.yaml"
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=path))
    pol = reg.policies["baseline"]
    joined = " ".join(pol.tool_output_injection_patterns).lower()
    assert "pompeii:zone-end" in joined and "pompeii:zone-begin" in joined


def test_load_security_policy_tool_output_overrides(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      tool_output_max_chars: 100
      tool_output_max_chars_overrides:
        echo: 8
        noisy_tool: 0
""",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=p))
    o = reg.policies["baseline"].tool_output_max_chars_overrides
    assert o["echo"] == 8
    assert o["noisy_tool"] == 0


def test_load_security_policy_rejects_negative_tool_output_override(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      tool_output_max_chars_overrides:
        bad: -1
""",
    )
    with pytest.raises(SecurityPolicyLoaderError):
        load_security_policy_registry(SecurityPolicySource(path=p))


def test_load_security_policy_tool_output_truncation(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      tool_output_max_chars: 4096
      tool_output_truncation_marker: "<cut>"
""",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=p))
    sp = reg.policies["baseline"]
    assert sp.tool_output_max_chars == 4096
    assert sp.tool_output_truncation_marker == "<cut>"


def test_load_security_policy_registry_ok(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns:
        - "ignore previous instructions"
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides:
        take_photo: "high"
""",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=p))
    assert "baseline" in reg.policies
    sp = reg.policies["baseline"]
    assert sp.guard_tool_output_redaction == "[guarded]"
    assert sp.guard_evaluator_ref == "builtin:default"
    assert sp.tool_output_max_chars == 0
    assert sp.tool_output_truncation_marker == "…[truncated]"
    assert sp.tool_output_max_chars_overrides == {}
    assert sp.default_tool_output_trust == "high"
    assert sp.tool_output_trust_overrides == {}
    assert sp.mcp_tool_output_trust == "low"
    assert sp.device_tool_output_trust == "low"
    assert sp.tool_output_max_chars_by_trust == {}
    assert sp.http_fetch_tool_output_trust == "low"
    assert sp.tool_output_injection_patterns == ()
    assert sp.tool_output_injection_redaction == "[tool_output_injection_blocked]"


def test_load_security_policy_injection_patterns_and_http_fetch_trust(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      http_fetch_tool_output_trust: "medium"
      tool_output_injection_patterns:
        - "<|im_start|>"
      tool_output_injection_redaction: "[x]"
""",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=p))
    sp = reg.policies["baseline"]
    assert sp.http_fetch_tool_output_trust == "medium"
    assert sp.tool_output_injection_patterns == ("<|im_start|>",)
    assert sp.tool_output_injection_redaction == "[x]"


def test_load_security_policy_tool_output_trust_caps(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      default_tool_output_trust: "medium"
      tool_output_trust_overrides:
        echo: "low"
      mcp_tool_output_trust: "high"
      device_tool_output_trust: "medium"
      tool_output_max_chars_by_trust:
        low: 100
        medium: 500
        high: 0
""",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=p))
    sp = reg.policies["baseline"]
    assert sp.default_tool_output_trust == "medium"
    assert sp.tool_output_trust_overrides == {"echo": "low"}
    assert sp.mcp_tool_output_trust == "high"
    assert sp.device_tool_output_trust == "medium"
    assert sp.tool_output_max_chars_by_trust == {"low": 100, "medium": 500, "high": 0}


def test_load_security_policy_rejects_bad_trust_cap_key(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
      tool_output_max_chars_by_trust:
        ultra: 1
""",
    )
    with pytest.raises(SecurityPolicyLoaderError):
        load_security_policy_registry(SecurityPolicySource(path=p))


def test_load_security_policy_registry_rejects_invalid_risk_level(tmp_path) -> None:
    p = _write_yaml(
        tmp_path,
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guarded]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "critical"
      tool_confirmation_level: "high"
      tool_risk_overrides: {}
""",
    )
    with pytest.raises(SecurityPolicyLoaderError):
        load_security_policy_registry(SecurityPolicySource(path=p))
