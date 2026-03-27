from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config_loaders.kernel_config_loader import KernelConfigSource, load_kernel_config
from app.config_loaders.memory_policy_loader import MemoryPolicySource, load_memory_policy
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.prompt_config_loader import (
    PromptConfigSource,
    load_prompt_config,
    merge_prompt_config_into_registry,
)
from app.config_loaders.resource_access_loader import ResourceAccessSource, load_resource_access_registry
from app.config_loaders.resource_index_loader import ResourceIndexSource, load_resource_index
from app.config_loaders.resource_manifest_loader import ResourceManifestSource, load_resource_manifest
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from app.config_loaders.security_policy_loader import SecurityPolicySource, load_security_policy_registry
from app.config_loaders.skill_registry_loader import SkillRegistrySource, load_skill_registry
from app.port_mode_registry import PortModeRegistryError, validate_interaction_mode_ref_format
from app.skill_entrypoint_discovery import merge_skill_registry_with_entrypoints
from app.config_loaders.storage_profile_loader import StorageProfileSource, load_storage_profile_registry
from app.config_loaders.session_config_loader import SessionConfigSource, load_session_config
from app.config_loaders.tool_registry_loader import ToolRegistrySource, load_tool_registry_config
from core.resource_access import KNOWN_RESOURCE_IDS
from infra.mcp_config_loader import McpConfigSource, load_mcp_config
from modules.model.prompt_strategy_registry import PromptStrategyRegistryError, validate_prompt_strategy_ref_format


class ResourceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceValidationReport:
    manifest_ok: bool
    resource_index_ok: bool
    security_policies_ok: bool
    storage_profiles_ok: bool
    model_providers_ok: bool
    prompts_ok: bool
    session_defaults_ok: bool
    kernel_ok: bool
    runtime_ok: bool
    skills_ok: bool
    tools_ok: bool
    mcp_ok: bool


def validate_resource_configs(*, src_root: Path) -> ResourceValidationReport:
    base = src_root.resolve()
    cfg_root = base / "platform_layer" / "resources" / "config"
    _ = load_resource_manifest(ResourceManifestSource(path=cfg_root / "resource_manifest.yaml"))
    resource_index = load_resource_index(ResourceIndexSource(path=cfg_root / "resource_index.yaml"))
    resource_access_registry = load_resource_access_registry(ResourceAccessSource(path=cfg_root / "resource_access.yaml"))
    if resource_index.active_resource_access_profile not in resource_access_registry.profiles:
        raise ResourceValidationError(
            f"resource_index.active_resource_access_profile={resource_index.active_resource_access_profile!r} "
            "not found in resource_access.profiles"
        )
    for pname, profile in resource_access_registry.profiles.items():
        unknown = set(profile.rules) - KNOWN_RESOURCE_IDS
        if unknown:
            bad = ", ".join(sorted(unknown))
            raise ResourceValidationError(
                f"resource_access.profiles[{pname!r}] declares unknown resource id(s): {bad}"
            )
    security_policies = load_security_policy_registry(SecurityPolicySource(path=cfg_root / "security_policies.yaml"))
    storage_profiles = load_storage_profile_registry(StorageProfileSource(path=cfg_root / "storage_profiles.yaml"))
    model_registry = load_model_registry(ModelProviderSource(path=cfg_root / "model_providers.yaml"))
    prompt_cfg = load_prompt_config(PromptConfigSource(path=cfg_root / "prompts.yaml"))
    model_registry = merge_prompt_config_into_registry(registry=model_registry, prompt_config=prompt_cfg)
    session_cfg = load_session_config(SessionConfigSource(path=cfg_root / "session_defaults.yaml"))
    kernel_cfg = load_kernel_config(KernelConfigSource(path=cfg_root / "kernel_config.yaml"))
    rc = load_runtime_config(RuntimeConfigSource(path=cfg_root / "runtime.yaml"))
    try:
        validate_interaction_mode_ref_format(rc.port_interaction_mode_ref)
    except PortModeRegistryError as exc:
        raise ResourceValidationError(str(exc)) from exc
    skill_registry = load_skill_registry(SkillRegistrySource(path=cfg_root / "skills.yaml"))
    skill_registry = merge_skill_registry_with_entrypoints(skill_registry)
    tools_cfg = load_tool_registry_config(ToolRegistrySource(path=cfg_root / "tools.yaml"))
    _ = load_mcp_config(McpConfigSource(path=cfg_root / "mcp_servers.yaml"), src_root=base)
    memory_policy_cfg = load_memory_policy(MemoryPolicySource(path=cfg_root / "memory_policy.yaml"))

    if session_cfg.model not in model_registry.providers:
        raise ResourceValidationError(
            f"session_defaults.session.model={session_cfg.model!r} is not in model_providers.providers"
        )
    allowset = set(kernel_cfg.tool_allowlist)
    for t in kernel_cfg.tool_confirmation_required:
        if t not in allowset:
            raise ResourceValidationError(f"kernel.tool_confirmation_required contains non-allowlisted tool: {t!r}")
    if kernel_cfg.archive_llm_summary_enabled:
        apid = kernel_cfg.archive_llm_summary_provider_id.strip() or model_registry.default_provider_id
        if apid not in model_registry.providers:
            raise ResourceValidationError(
                f"kernel.archive_llm_summary enabled but provider {apid!r} not in model_providers"
            )
    overlap = set(tools_cfg.local_handlers.keys()) & set(tools_cfg.device_routes.keys())
    if overlap:
        names = ", ".join(sorted(overlap))
        raise ResourceValidationError(f"tools.local_handlers and tools.device_routes overlap: {names}")
    np = tools_cfg.network_policy
    if np.enabled and np.mcp_allowlist_enforced:
        for n in np.mcp_tool_allowlist:
            if n not in allowset:
                raise ResourceValidationError(
                    f"tools.network_policy.mcp_tool_allowlist: {n!r} is not in kernel.tool_allowlist"
                )
    unknown_skills = [s for s in session_cfg.skills if s not in skill_registry.skills]
    if unknown_skills:
        names = ", ".join(sorted(unknown_skills))
        raise ResourceValidationError(f"session.skills contains unknown ids: {names}")

    if resource_index.active_security_policy not in security_policies.policies:
        raise ResourceValidationError(
            f"resource_index.active_security_policy={resource_index.active_security_policy!r} is not defined"
        )
    if resource_index.active_storage_profile not in storage_profiles.profiles:
        raise ResourceValidationError(
            f"resource_index.active_storage_profile={resource_index.active_storage_profile!r} is not defined"
        )
    active_storage = storage_profiles.profiles[resource_index.active_storage_profile]
    if memory_policy_cfg.enabled:
        mref = active_storage.memory_store_ref.strip().lower()
        if mref != "builtin:noop":
            raise ResourceValidationError(
                "memory_policy.enabled=true requires storage_profiles.memory.store_ref to be "
                "'builtin:noop'. The composed long-term memory path is MemoryOrchestrator + "
                "memory_policy.dual_store_ref writing to memory.path (DualMemoryStore). "
                "LongTermMemoryStore via memory_store_ref is not wired into composition; "
                "a non-noop ref risks a second SQLite consumer on the same path. "
                "See docs/design/架构设计ver0.5.md §9.8 (legacy line)."
            )
    if isinstance(session_cfg.security, str) and session_cfg.security not in security_policies.policies:
        raise ResourceValidationError(f"session.security contains unknown policy id: {session_cfg.security!r}")

    active_sec = security_policies.policies[resource_index.active_security_policy]
    try:
        validate_prompt_strategy_ref_format(kernel_cfg.prompt_strategy_ref)
    except PromptStrategyRegistryError as exc:
        raise ResourceValidationError(str(exc)) from exc
    for prov in model_registry.providers.values():
        raw_ps = prov.params.get("prompt_strategy_ref")
        if raw_ps is None:
            continue
        if not isinstance(raw_ps, str):
            raise ResourceValidationError(
                f"model_providers / prompts merged: provider {prov.id!r} prompt_strategy_ref must be string"
            )
        try:
            validate_prompt_strategy_ref_format(raw_ps)
        except PromptStrategyRegistryError as exc:
            raise ResourceValidationError(
                f"model_providers / prompts merged: provider {prov.id!r}: {exc}"
            ) from exc

    if str(active_sec.guard_model_ref).strip() == "builtin:llm_judge":
        pid = active_sec.guard_model_provider_id
        if not pid or pid not in model_registry.providers:
            raise ResourceValidationError(
                "security_policies: guard_model_ref=builtin:llm_judge requires guard_model_provider_id "
                "to reference an existing model_providers id"
            )
        prov = model_registry.providers[pid]
        if str(prov.backend).strip().lower() != "openai_compatible":
            raise ResourceValidationError(
                f"guard model provider {pid!r} must use backend openai_compatible, got {prov.backend!r}"
            )

    return ResourceValidationReport(
        manifest_ok=True,
        resource_index_ok=True,
        security_policies_ok=True,
        storage_profiles_ok=True,
        model_providers_ok=True,
        prompts_ok=True,
        session_defaults_ok=True,
        kernel_ok=True,
        runtime_ok=True,
        skills_ok=True,
        tools_ok=True,
        mcp_ok=True,
    )
