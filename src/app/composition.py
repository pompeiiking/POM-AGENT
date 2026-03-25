from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core import AgentCoreImpl, KernelConfig, SessionConfig, SessionManagerImpl
from core.archive_llm_summary import ArchiveLlmSummaryBinding
from core.memory.orchestrator import MemoryOrchestrator
from core.resource_access import ResourceAccessEvaluator
from core.session.session import Session
from core.session.session_store import SessionStore
from core.types import ToolCall, ToolResult
from modules.assembly.impl import AssemblyModuleImpl
from modules.assembly.interface import AssemblyModule
from modules.model.impl import ModelModuleImpl
from modules.tools.builtin_handlers import HTTP_GET_TOOL_REF, make_http_get_handler
from modules.tools.impl import ToolModuleImpl, load_tool_handler
from modules.tools.plugin_discovery import assert_tool_handler_signature, discover_entrypoint_handlers
from app.config_provider import yaml_file_config_provider
from port.agent_port import GenericAgentPort, InteractionMode, PortEmitter
from port.request_factory import RequestFactory
from app.config_loaders.memory_policy_loader import MemoryPolicySource, load_memory_policy
from app.config_loaders.kernel_config_loader import KernelConfigSource, load_kernel_config
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.prompt_config_loader import (
    PromptConfigSource,
    load_prompt_config,
    merge_prompt_config_into_registry,
)
from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from app.config_loaders.resource_access_loader import ResourceAccessSource, load_resource_access_registry
from app.config_loaders.resource_index_loader import ResourceIndexSource, load_resource_index
from app.config_loaders.security_policy_loader import SecurityPolicySource, load_security_policy_registry
from app.config_loaders.storage_profile_loader import StorageProfileSource, load_storage_profile_registry
from app.config_loaders.skill_registry_loader import SkillRegistrySource, load_skill_registry
from app.config_loaders.tool_registry_loader import ToolRegistryConfig, ToolRegistrySource, load_tool_registry_config
from app.config_loaders.resource_validation import validate_resource_configs
from app.guard_evaluator_registry import resolve_guard_evaluator
from app.guard_model_registry import resolve_guard_model_should_block
from app.memory_orchestrator_registry import resolve_dual_memory_store, resolve_embedding_provider
from app.session_store_registry import resolve_session_store
from app.loop_policy_registry import resolve_loop_governance_fn
from app.mcp_bridge_registry import resolve_mcp_bridge
from app.skill_entrypoint_discovery import merge_skill_registry_with_entrypoints
from app.tool_policy_registry import resolve_tool_policy_decide
from modules.model.archive_dialogue_summary import summarize_dialogue_for_archive
from modules.model.config import ModelRegistry
from modules.tools.mcp_bridge import McpToolBridge
from core.types import DeviceRequest
from infra.prompt_cache import PromptCache


ConfigProvider = Callable[[str, str], SessionConfig]


def build_core(
    config_provider: ConfigProvider,
    model_registry: ModelRegistry | None = None,
    *,
    src_root: Path | None = None,
    assembly: AssemblyModule | None = None,
) -> AgentCoreImpl:
    """
    装配 ``AgentCoreImpl``。

    ``assembly``：若传入则使用该 ``AssemblyModule``（须自行处理记忆注入、预算等）；
    若为 ``None`` 则使用默认 ``AssemblyModuleImpl``（绑定本仓库加载的 ``MemoryOrchestrator`` 与资源门）。
    自定义组装实现应在 ``Context.meta`` 中设置 ``context_isolation_enabled``（与 ``kernel.context_isolation_enabled`` 对齐），否则 OpenAI 兼容路径默认视为开启关卡② 包装。
    """
    base = src_root if src_root is not None else Path(__file__).resolve().parents[1]
    _ = validate_resource_configs(src_root=base)
    store = _load_session_store(base)
    manager = SessionManagerImpl(store)
    kernel_config = _load_kernel_config()
    tool_policy_decide = resolve_tool_policy_decide(kernel_config.tool_policy_engine_ref)
    loop_governance_fn = resolve_loop_governance_fn(kernel_config.loop_policy_engine_ref)
    memory_orch = _try_build_memory_orchestrator(base)
    resource_gate = _load_resource_access_evaluator(base)
    tool_registry_cfg = load_tool_registry_config(
        ToolRegistrySource(path=base / "platform_layer" / "resources" / "config" / "tools.yaml")
    )
    assembly_mod = assembly or AssemblyModuleImpl(
        memory_orchestrator=memory_orch,
        resource_access=resource_gate,
        context_isolation_enabled=kernel_config.context_isolation_enabled,
        tool_network_policy=tool_registry_cfg.network_policy,
    )
    merged_registry = model_registry if model_registry is not None else _load_model_registry(base)
    model = _build_model(
        merged_registry,
        base=base,
        prompt_strategy_ref=kernel_config.prompt_strategy_ref,
    )
    tools = _build_tools(base, memory_orchestrator=memory_orch, tool_registry_cfg=tool_registry_cfg)
    security_registry = load_security_policy_registry(
        SecurityPolicySource(path=base / "platform_layer" / "resources" / "config" / "security_policies.yaml")
    )
    resource_index = load_resource_index(
        ResourceIndexSource(path=base / "platform_layer" / "resources" / "config" / "resource_index.yaml")
    )
    active_policy = security_registry.policies[resource_index.active_security_policy]
    guard_evaluator = resolve_guard_evaluator(evaluator_ref=active_policy.guard_evaluator_ref)
    guard_model_should_block = resolve_guard_model_should_block(
        guard_model_ref=active_policy.guard_model_ref,
        guard_model_provider_id=active_policy.guard_model_provider_id,
        model_registry=merged_registry,
    )
    archive_llm = _build_archive_llm_binding(kernel_config, merged_registry)
    return AgentCoreImpl(
        session_manager=manager,
        assembly=assembly_mod,
        model=model,
        tools=tools,
        config_provider=config_provider,
        kernel_config=kernel_config,
        security_policies=security_registry.policies,
        guard_evaluator=guard_evaluator,
        guard_model_should_block=guard_model_should_block,
        memory_orchestrator=memory_orch,
        archive_llm=archive_llm,
        resource_access=resource_gate,
        tool_policy_decide=tool_policy_decide,
        loop_governance_fn=loop_governance_fn,
    )


def _load_resource_access_evaluator(base: Path) -> ResourceAccessEvaluator:
    cfg = base / "platform_layer" / "resources" / "config"
    index = load_resource_index(ResourceIndexSource(path=cfg / "resource_index.yaml"))
    reg = load_resource_access_registry(ResourceAccessSource(path=cfg / "resource_access.yaml"))
    profile = reg.profiles[index.active_resource_access_profile]
    return ResourceAccessEvaluator(profile)


def _build_archive_llm_binding(
    kernel_config: KernelConfig,
    model_registry: ModelRegistry,
) -> ArchiveLlmSummaryBinding | None:
    if not kernel_config.archive_llm_summary_enabled:
        return None
    pid = kernel_config.archive_llm_summary_provider_id.strip() or model_registry.default_provider_id

    def summarize(
        *,
        provider_id: str,
        dialogue_plain: str,
        max_output_chars: int,
        system_prompt: str,
    ) -> str:
        return summarize_dialogue_for_archive(
            registry=model_registry,
            provider_id=provider_id,
            dialogue_plain=dialogue_plain,
            max_output_chars=max_output_chars,
            system_prompt=system_prompt,
        )

    return ArchiveLlmSummaryBinding(
        provider_id=pid,
        max_dialogue_chars=kernel_config.archive_llm_summary_max_dialogue_chars,
        max_output_chars=kernel_config.archive_llm_summary_max_output_chars,
        system_prompt=kernel_config.archive_llm_summary_system_prompt,
        summarize=summarize,
    )


def build_port(mode: InteractionMode, request_factory: RequestFactory, emitter: PortEmitter) -> GenericAgentPort:
    base = Path(__file__).resolve().parents[1]  # .../<repo>/src
    config_path = base / "platform_layer" / "resources" / "config" / "session_defaults.yaml"
    model_registry = _load_model_registry(base)
    core = build_core(
        config_provider=yaml_file_config_provider(config_path),
        model_registry=model_registry,
        src_root=base,
    )
    return GenericAgentPort(mode=mode, core=core, request_factory=request_factory, emitter=emitter)


def _load_kernel_config() -> KernelConfig:
    base = Path(__file__).resolve().parents[1]  # .../<repo>/src
    config_path = base / "platform_layer" / "resources" / "config" / "kernel_config.yaml"
    return load_kernel_config(KernelConfigSource(path=config_path))


def _load_model_registry(base: Path) -> ModelRegistry:
    config_path = base / "platform_layer" / "resources" / "config" / "model_providers.yaml"
    registry = load_model_registry(ModelProviderSource(path=config_path))
    prompt_cfg = load_prompt_config(
        PromptConfigSource(path=base / "platform_layer" / "resources" / "config" / "prompts.yaml")
    )
    return merge_prompt_config_into_registry(registry=registry, prompt_config=prompt_cfg)


def _build_model(
    model_registry: ModelRegistry | None,
    *,
    base: Path,
    prompt_strategy_ref: str = "builtin:none",
) -> ModelModuleImpl:
    skill_registry = load_skill_registry(
        SkillRegistrySource(path=base / "platform_layer" / "resources" / "config" / "skills.yaml")
    )
    skill_registry = merge_skill_registry_with_entrypoints(skill_registry)
    prompt_cache = PromptCache()
    ps_ref = str(prompt_strategy_ref).strip() or "builtin:none"
    if model_registry is None:
        return ModelModuleImpl(
            skill_registry=skill_registry.skills,
            prompt_cache=prompt_cache,
            default_prompt_strategy_ref=ps_ref,
        )
    return ModelModuleImpl(
        registry=model_registry,
        skill_registry=skill_registry.skills,
        prompt_cache=prompt_cache,
        default_prompt_strategy_ref=ps_ref,
    )


def _load_mcp_bridge(src_root: Path) -> McpToolBridge | None:
    from infra.mcp_config_loader import McpConfigSource, load_mcp_config

    cfg = load_mcp_config(
        McpConfigSource(path=src_root / "platform_layer" / "resources" / "config" / "mcp_servers.yaml"),
        src_root=src_root,
    )
    if not cfg.enabled or not cfg.servers:
        return None
    return resolve_mcp_bridge(cfg=cfg, src_root=src_root)


def _load_session_store(src_root: Path) -> SessionStore:
    cfg_root = src_root / "platform_layer" / "resources" / "config"
    path = cfg_root / "runtime.yaml"
    rc = load_runtime_config(RuntimeConfigSource(path=path))
    index = load_resource_index(ResourceIndexSource(path=cfg_root / "resource_index.yaml"))
    storage_registry = load_storage_profile_registry(StorageProfileSource(path=cfg_root / "storage_profiles.yaml"))
    selected = storage_registry.profiles[index.active_storage_profile]
    sqlite_rel = selected.archive_path if selected.archive_backend == "sqlite" else rc.sqlite_path
    resolved = sqlite_rel if sqlite_rel.is_absolute() else (src_root / sqlite_rel)
    return resolve_session_store(selected.archive_store_ref, sqlite_path=resolved)


def _try_build_memory_orchestrator(base: Path) -> MemoryOrchestrator | None:
    cfg_path = base / "platform_layer" / "resources" / "config" / "memory_policy.yaml"
    policy = load_memory_policy(MemoryPolicySource(path=cfg_path))
    if not policy.enabled:
        return None
    cfg_root = base / "platform_layer" / "resources" / "config"
    index = load_resource_index(ResourceIndexSource(path=cfg_root / "resource_index.yaml"))
    storage_registry = load_storage_profile_registry(StorageProfileSource(path=cfg_root / "storage_profiles.yaml"))
    selected = storage_registry.profiles[index.active_storage_profile]
    mpath = selected.memory_path
    resolved = mpath if mpath.is_absolute() else (base / mpath)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    store = resolve_dual_memory_store(policy.dual_store_ref, memory_db_path=resolved)
    emb = resolve_embedding_provider(
        policy.embedding_ref,
        embedding_dim=policy.embedding_dim,
        policy=policy,
    )
    return MemoryOrchestrator(store=store, embedding=emb, policy=policy)


def _memory_search_tool_handler(memory_orchestrator: MemoryOrchestrator | None):
    def handler(session: Session, tool_call: ToolCall) -> ToolResult:
        q = str(tool_call.arguments.get("query", ""))
        if memory_orchestrator is None:
            return ToolResult(
                name=tool_call.name,
                output={"hits": [], "disabled": True, "query": q},
            )
        hits = memory_orchestrator.retrieve_as_tool_json(
            user_id=session.user_id,
            channel=session.channel,
            query_text=q,
        )
        return ToolResult(name=tool_call.name, output={"hits": hits, "query": q})

    return handler


def _build_tools(
    src_root: Path,
    memory_orchestrator: MemoryOrchestrator | None = None,
    *,
    tool_registry_cfg: ToolRegistryConfig | None = None,
) -> ToolModuleImpl:
    cfg = tool_registry_cfg or load_tool_registry_config(
        ToolRegistrySource(path=src_root / "platform_layer" / "resources" / "config" / "tools.yaml")
    )
    local_handlers: dict[str, Any] = {}
    for name, ref in cfg.local_handlers.items():
        if ref == HTTP_GET_TOOL_REF:
            local_handlers[name] = make_http_get_handler(cfg.network_policy)
        else:
            local_handlers[name] = load_tool_handler(ref)
    if cfg.enable_entrypoints:
        ep_handlers = discover_entrypoint_handlers(group=cfg.entrypoint_group)
        for n, h in ep_handlers.items():
            assert_tool_handler_signature(h, path=f"entrypoint:{cfg.entrypoint_group}:{n}")
        # 显式配置优先级更高：同名时覆盖 entrypoint
        local_handlers = {**ep_handlers, **local_handlers}
    local_handlers["search_memory"] = _memory_search_tool_handler(memory_orchestrator)
    device_routes = {
        name: DeviceRequest(device=route.device, command=route.command, parameters=route.fixed_parameters)
        for name, route in cfg.device_routes.items()
    }
    return ToolModuleImpl(
        local_handlers=local_handlers,
        device_routes=device_routes,
        mcp=_load_mcp_bridge(src_root),
        network_policy=cfg.network_policy,
    )

