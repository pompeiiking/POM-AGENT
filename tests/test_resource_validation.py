from __future__ import annotations

import pytest

from app.config_loaders.resource_validation import ResourceValidationError, validate_resource_configs


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _prepare_minimal_config_tree(tmp_path):
    src_root = tmp_path / "src"
    cfg = src_root / "platform_layer" / "resources" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    _write(
        cfg / "resource_manifest.yaml",
        """
schema_version: 1
""",
    )
    _write(
        cfg / "resource_index.yaml",
        """
resource_index:
  active_security_policy: "baseline"
  active_storage_profile: "default"
  active_resource_access_profile: "default"
""",
    )
    _write(
        cfg / "resource_access.yaml",
        """
resource_access:
  profiles:
    default:
      resources:
        long_term_memory:
          read: allow
          write: allow
""",
    )
    _write(
        cfg / "security_policies.yaml",
        """
security_policies:
  items:
    - id: "baseline"
      input_max_chars: 8000
      max_requests_per_minute: 60
      guard_enabled: false
      guard_block_patterns: []
      guard_tool_output_redaction: "[guard]"
      guard_evaluator_ref: "builtin:default"
      guard_model_ref: "builtin:none"
      default_tool_risk_level: "low"
      tool_confirmation_level: "high"
      tool_risk_overrides:
        take_photo: "high"
""",
    )
    _write(
        cfg / "storage_profiles.yaml",
        """
storage_profiles:
  items:
    - id: "default"
      archive:
        backend: "sqlite"
        path: "platform_layer/resources/data/sessions.db"
      memory:
        backend: "sqlite"
        path: "platform_layer/resources/data/memory.db"
""",
    )
    _write(
        cfg / "model_providers.yaml",
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params: {}
""",
    )
    _write(
        cfg / "prompts.yaml",
        """
prompts:
  providers:
    deepseek:
      prompt_profiles:
        default:
          default: "sys"
""",
    )
    _write(
        cfg / "session_defaults.yaml",
        """
session:
  model: "deepseek"
  prompt_profile: "default"
  prompt_strategy: "default"
  skills: ["echo"]
  security: "baseline"
  limits:
    max_tokens: 100
    max_context_window: 100
    max_loops: 3
    timeout_seconds: 10.0
""",
    )
    _write(
        cfg / "kernel_config.yaml",
        """
kernel:
  core_max_loops: 8
  max_tool_calls_per_run: 8
  tool_allowlist: ["echo"]
  tool_confirmation_required: []
""",
    )
    _write(
        cfg / "runtime.yaml",
        """
session_store:
  backend: sqlite
  sqlite_path: platform_layer/resources/data/sessions.db
""",
    )
    _write(
        cfg / "skills.yaml",
        """
skills:
  items:
    - id: "echo"
      index: "SKILL-001"
      title: "Echo"
      summary: "s"
      content: "c"
      quality_tier: "gold"
      enabled: true
      tags: ["a"]
""",
    )
    _write(
        cfg / "tools.yaml",
        """
tools:
  local_handlers:
    echo: "modules.tools.builtin_handlers:echo_handler"
  device_routes: []
""",
    )
    _write(
        cfg / "mcp_servers.yaml",
        """
enabled: false
servers: []
""",
    )
    _write(
        cfg / "memory_policy.yaml",
        """
memory_policy:
  dual_store_ref: "builtin:dual_sqlite"
  embedding_ref: "builtin:hash"
  enabled: false
  retrieve_top_k: 6
  rrf_k: 60
  rerank_enabled: false
  rerank_max_candidates: 24
  chunk_max_chars: 512
  chunk_overlap_chars: 64
  promote_on_archive: false
  archive_chunk_max_chars: 8000
  archive_trust: medium
  embedding_async: false
  embedding_dim: 64
  fts_enabled: false
  vector_max_candidates: 200
  channel_filter: any
""",
    )
    return src_root


def test_validate_rejects_legacy_memory_store_ref_when_memory_enabled(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "memory_policy.yaml"
    _write(
        cfg,
        """
memory_policy:
  dual_store_ref: "builtin:dual_sqlite"
  embedding_ref: "builtin:hash"
  enabled: true
  retrieve_top_k: 6
  rrf_k: 60
  rerank_enabled: false
  rerank_max_candidates: 24
  chunk_max_chars: 512
  chunk_overlap_chars: 64
  promote_on_archive: false
  archive_chunk_max_chars: 8000
  archive_trust: medium
  embedding_async: false
  embedding_dim: 64
  fts_enabled: false
  vector_max_candidates: 200
  channel_filter: any
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_ok(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    report = validate_resource_configs(src_root=src_root)
    assert report.manifest_ok is True
    assert report.tools_ok is True


def test_validate_resource_configs_rejects_local_device_overlap(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "tools.yaml"
    _write(
        cfg,
        """
tools:
  local_handlers:
    take_photo: "modules.tools.builtin_handlers:echo_handler"
  device_routes:
    - tool: "take_photo"
      device: "camera"
      command: "take_photo"
      fixed_parameters: {}
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_unknown_session_skill(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
    _write(
        cfg,
        """
session:
  model: "deepseek"
  prompt_profile: "default"
  prompt_strategy: "default"
  skills: ["missing_skill"]
  security: "baseline"
  limits:
    max_tokens: 100
    max_context_window: 100
    max_loops: 3
    timeout_seconds: 10.0
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_unknown_resource_access_profile(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "resource_index.yaml"
    _write(
        cfg,
        """
resource_index:
  active_security_policy: "baseline"
  active_storage_profile: "default"
  active_resource_access_profile: "missing_profile"
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_unknown_resource_access_resource_id(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    _write(
        src_root / "platform_layer" / "resources" / "config" / "resource_access.yaml",
        """
resource_access:
  profiles:
    default:
      resources:
        long_term_memory:
          read: allow
          write: allow
        typo_multimodal:
          read: allow
          write: deny
""",
    )
    with pytest.raises(ResourceValidationError) as exc:
        validate_resource_configs(src_root=src_root)
    assert "unknown resource id" in str(exc.value).lower()
    assert "typo_multimodal" in str(exc.value)


def test_validate_resource_configs_rejects_unknown_active_security_policy(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "resource_index.yaml"
    _write(
        cfg,
        """
resource_index:
  active_security_policy: "missing"
  active_storage_profile: "default"
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_mcp_network_allowlist_not_in_kernel(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "tools.yaml"
    _write(
        cfg,
        """
tools:
  local_handlers:
    echo: "modules.tools.builtin_handlers:echo_handler"
  device_routes: []
  network_policy:
    enabled: true
    mcp_allowlist_enforced: true
    mcp_tool_allowlist: ["ping"]
""",
    )
    with pytest.raises(ResourceValidationError) as exc:
        validate_resource_configs(src_root=src_root)
    assert "mcp_tool_allowlist" in str(exc.value)
    assert "ping" in str(exc.value)


def test_validate_resource_configs_rejects_bad_kernel_prompt_strategy_ref(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    _write(
        src_root / "platform_layer" / "resources" / "config" / "kernel_config.yaml",
        """
kernel:
  core_max_loops: 8
  max_tool_calls_per_run: 8
  tool_allowlist: ["echo"]
  tool_confirmation_required: []
  prompt_strategy_ref: "not-a-valid-ref"
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_bad_provider_prompt_strategy_ref(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    _write(
        src_root / "platform_layer" / "resources" / "config" / "model_providers.yaml",
        """
default_provider: deepseek
providers:
  deepseek:
    backend: openai_compatible
    params:
      prompt_strategy_ref: "bad:"
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)


def test_validate_resource_configs_rejects_bad_port_interaction_mode_ref(tmp_path) -> None:
    src_root = _prepare_minimal_config_tree(tmp_path)
    cfg = src_root / "platform_layer" / "resources" / "config" / "runtime.yaml"
    _write(
        cfg,
        """
session_store:
  backend: sqlite
  sqlite_path: platform_layer/resources/data/sessions.db
port:
  interaction_mode_ref: "builtin:unknown"
""",
    )
    with pytest.raises(ResourceValidationError):
        validate_resource_configs(src_root=src_root)
