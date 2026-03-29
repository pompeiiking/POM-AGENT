"""
编程式配置 API：每个 YAML 配置块 → 一个 Builder 类，`build()` 产出内部 dataclass，
无需记忆任何路径或文件格式。

使用方式::

    from pompeii_agent.builders import AgentBuilder

    kernel = (
        AgentBuilder()
        .session(model="stub", skills=["echo"])
        .kernel(core_max_loops=8, tool_allowlist=["echo"])
        .build()
    )

所有 Builder 均支持链式调用（`.xxx(...)`）；不关心的配置保持默认即可。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from core import AgentCoreImpl, KernelConfig
from core.kernel_config import KernelConfig as KC
from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.resource_access import (
    KNOWN_RESOURCE_IDS,
    ResourceAccessEvaluator,
    ResourceAccessProfile,
    ResourceAccessRule,
)
from core.session.session import SessionConfig
from core.session.session_store import SessionStore
from core.types import DeviceRequest
from infra.prompt_cache import PromptCache
from modules.assembly.impl import AssemblyModuleImpl
from modules.model.archive_dialogue_summary import summarize_dialogue_for_archive
from modules.model.config import ModelProvider, ModelRegistry
from modules.model.impl import ModelModuleImpl
from modules.tools.builtin_handlers import HTTP_GET_TOOL_REF, make_http_get_handler
from modules.tools.impl import ToolModuleImpl, load_tool_handler
from modules.tools.mcp_bridge import McpToolBridge
from modules.tools.network_policy import ToolNetworkPolicyConfig
from modules.tools.plugin_discovery import assert_tool_handler_signature, discover_entrypoint_handlers
from port.agent_port import GenericAgentPort

from app.device_backend_registry import build_device_backend as _build_dev_backend
from app.guard_evaluator_registry import resolve_guard_evaluator
from app.guard_model_registry import resolve_guard_model_should_block
from app.memory_orchestrator_registry import (
    resolve_dual_memory_store,
    resolve_embedding_provider,
)
from app.session_store_registry import resolve_session_store
from app.skill_entrypoint_discovery import merge_skill_registry_with_entrypoints
from app.tool_policy_registry import resolve_tool_policy_decide
from app.loop_policy_registry import resolve_loop_governance_fn

from pompeii_agent.config import ConfigProvider, SessionConfig as SC
from pompeii_agent.config import session_provider_from_yaml as _prov_from_yaml


# ─────────────────────────────────────────────────────────────────────────────
# KernelConfig Builder
# ─────────────────────────────────────────────────────────────────────────────


class KernelBuilder:
    """
    kernel_config.yaml → 核心循环与工具治理。

    必填：无（均有默认值）。
    """

    def __init__(
        self,
        core_max_loops: int = 8,
        max_tool_calls_per_run: int = 8,
        tool_allowlist: list[str] | None = None,
        tool_confirmation_required: list[str] | None = None,
        context_isolation_enabled: bool = True,
        tool_policy_engine_ref: str = "builtin:default",
        loop_policy_engine_ref: str = "builtin:default",
        prompt_strategy_ref: str = "builtin:none",
        archive_llm_summary_enabled: bool = False,
        archive_llm_summary_provider_id: str = "",
        archive_llm_summary_max_dialogue_chars: int = 12000,
        archive_llm_summary_max_output_chars: int = 2000,
        archive_llm_summary_system_prompt: str = "",
        delegate_target_allowlist: tuple[str, ...] = (),
    ) -> None:
        self._cfg = KC(
            core_max_loops=core_max_loops,
            max_tool_calls_per_run=max_tool_calls_per_run,
            tool_allowlist=tool_allowlist or [],
            tool_confirmation_required=tool_confirmation_required or [],
            context_isolation_enabled=context_isolation_enabled,
            tool_policy_engine_ref=tool_policy_engine_ref,
            loop_policy_engine_ref=loop_policy_engine_ref,
            prompt_strategy_ref=prompt_strategy_ref,
            archive_llm_summary_enabled=archive_llm_summary_enabled,
            archive_llm_summary_provider_id=archive_llm_summary_provider_id,
            archive_llm_summary_max_dialogue_chars=archive_llm_summary_max_dialogue_chars,
            archive_llm_summary_max_output_chars=archive_llm_summary_max_output_chars,
            archive_llm_summary_system_prompt=archive_llm_summary_system_prompt,
            delegate_target_allowlist=delegate_target_allowlist,
        )

    def core_max_loops(self, v: int) -> "KernelBuilder":
        return _mk(self, core_max_loops=v)

    def max_tool_calls_per_run(self, v: int) -> "KernelBuilder":
        return _mk(self, max_tool_calls_per_run=v)

    def tool_allowlist(self, names: list[str]) -> "KernelBuilder":
        return _mk(self, tool_allowlist=names)

    def tool_confirmation_required(self, names: list[str]) -> "KernelBuilder":
        return _mk(self, tool_confirmation_required=names)

    def context_isolation(self, on: bool = True) -> "KernelBuilder":
        return _mk(self, context_isolation_enabled=on)

    def build(self) -> KC:
        return self._cfg

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


def _mk(b: KernelBuilder, **kw: Any) -> KernelBuilder:
    parent = getattr(b, "_parent", None)
    inst = KernelBuilder(**{**b._cfg.__dict__, **kw})
    object.__setattr__(inst, "_parent", parent)
    return inst


# ─────────────────────────────────────────────────────────────────────────────
# SessionLimits Builder
# ─────────────────────────────────────────────────────────────────────────────


class SessionLimitsBuilder:
    """
    session_defaults.yaml.limits → 单会话 token/循环/超时预算。

    必填：无（仓库默认值）。
    """

    def __init__(
        self,
        max_tokens: int = 100000,
        max_context_window: int = 128000,
        max_loops: int = 15,
        timeout_seconds: float = 300.0,
        assembly_tail_messages: int = 20,
        summary_tail_messages: int = 12,
        summary_excerpt_chars: int = 200,
        assembly_message_max_chars: int = 0,
        assembly_approx_context_tokens: int = 0,
        assembly_compress_tool_max_chars: int = 0,
        assembly_compress_early_turn_chars: int = 0,
        assembly_token_counter: Literal["heuristic", "tiktoken"] = "heuristic",
        assembly_tiktoken_encoding: str = "cl100k_base",
    ) -> None:
        self._vals = {
            "max_tokens": max_tokens,
            "max_context_window": max_context_window,
            "max_loops": max_loops,
            "timeout_seconds": timeout_seconds,
            "assembly_tail_messages": assembly_tail_messages,
            "summary_tail_messages": summary_tail_messages,
            "summary_excerpt_chars": summary_excerpt_chars,
            "assembly_message_max_chars": assembly_message_max_chars,
            "assembly_approx_context_tokens": assembly_approx_context_tokens,
            "assembly_compress_tool_max_chars": assembly_compress_tool_max_chars,
            "assembly_compress_early_turn_chars": assembly_compress_early_turn_chars,
            "assembly_token_counter": assembly_token_counter,
            "assembly_tiktoken_encoding": assembly_tiktoken_encoding,
        }

    def max_tokens(self, v: int) -> "SessionLimitsBuilder":
        return _sl(self, max_tokens=v)

    def max_context_window(self, v: int) -> "SessionLimitsBuilder":
        return _sl(self, max_context_window=v)

    def max_loops(self, v: int) -> "SessionLimitsBuilder":
        return _sl(self, max_loops=v)

    def timeout_seconds(self, v: float) -> "SessionLimitsBuilder":
        return _sl(self, timeout_seconds=v)

    def assembly_tail_messages(self, v: int) -> "SessionLimitsBuilder":
        return _sl(self, assembly_tail_messages=v)

    def build(self) -> SC.limits.__class__:  # type: ignore[return-value]
        from core.session.session import SessionLimits

        return SessionLimits(**self._vals)


def _sl(b: SessionLimitsBuilder, **kw: Any) -> SessionLimitsBuilder:
    return SessionLimitsBuilder(**{**b._vals, **kw})


# ─────────────────────────────────────────────────────────────────────────────
# SessionBuilder
# ─────────────────────────────────────────────────────────────────────────────


class SessionBuilder:
    """
    session_defaults.yaml → 会话默认配置（model / skills / limits / prompt_profile）。

    必填：``model``、``skills``。
    """

    def __init__(
        self,
        model: str,
        skills: list[str],
        limits: SessionLimitsBuilder | None = None,
        prompt_profile: str = "default",
        prompt_strategy: str = "default",
        security: str | dict[str, Any] = "baseline",
        config_provider: ConfigProvider | None = None,
    ) -> None:
        self._model = model
        self._skills = skills
        self._limits = limits or SessionLimitsBuilder()
        self._prompt_profile = prompt_profile
        self._prompt_strategy = prompt_strategy
        self._security = security
        self._config_provider = config_provider

    def model(self, m: str) -> "SessionBuilder":
        return SessionBuilder(
            model=m, skills=self._skills, limits=self._limits,
            prompt_profile=self._prompt_profile, prompt_strategy=self._prompt_strategy,
            security=self._security, config_provider=self._config_provider,
        )

    def skills(self, names: list[str]) -> "SessionBuilder":
        return SessionBuilder(
            model=self._model, skills=names, limits=self._limits,
            prompt_profile=self._prompt_profile, prompt_strategy=self._prompt_strategy,
            security=self._security, config_provider=self._config_provider,
        )

    def limits(self, b: SessionLimitsBuilder) -> "SessionBuilder":
        return SessionBuilder(
            model=self._model, skills=self._skills, limits=b,
            prompt_profile=self._prompt_profile, prompt_strategy=self._prompt_strategy,
            security=self._security, config_provider=self._config_provider,
        )

    def prompt_profile(self, p: str) -> "SessionBuilder":
        return SessionBuilder(
            model=self._model, skills=self._skills, limits=self._limits,
            prompt_profile=p, prompt_strategy=self._prompt_strategy,
            security=self._security, config_provider=self._config_provider,
        )

    def security(self, s: str) -> "SessionBuilder":
        return SessionBuilder(
            model=self._model, skills=self._skills, limits=self._limits,
            prompt_profile=self._prompt_profile, prompt_strategy=self._prompt_strategy,
            security=s, config_provider=self._config_provider,
        )

    def build_config_provider(self) -> ConfigProvider:
        """基于 Builder 状态构造 ConfigProvider（供 create_kernel 使用）。"""
        if self._config_provider is not None:
            return self._config_provider
        cfg = SC(
            model=self._model,
            skills=list(self._skills),
            security=self._security,
            limits=self._limits.build(),
            prompt_profile=self._prompt_profile,
            prompt_strategy=self._prompt_strategy,
        )
        return _cfg_to_provider(cfg)


def _cfg_to_provider(cfg: SC) -> ConfigProvider:
    """将 SessionConfig 转成 config_provider(user_id, channel) → SessionConfig。"""
    def provider(user_id: str, channel: str) -> SC:
        return cfg

    return provider


# ─────────────────────────────────────────────────────────────────────────────
# ModelProviderBuilder / ModelRegistryBuilder
# ─────────────────────────────────────────────────────────────────────────────


class ModelProviderBuilder:
    """
    model_providers.yaml.providers.<id> → 单个模型后端。

    必填：``provider_id``、``backend``。
    """

    def __init__(
        self,
        provider_id: str,
        backend: Literal["stub", "openai_compatible"],
        api_base_url: str = "",
        model_name: str = "",
        api_key_env: str = "",
        max_history: int = 10,
        timeout: float = 30.0,
        failover_chain: tuple[str, ...] = (),
        extra_headers: dict[str, str] | None = None,
        http_disable_connection_pool: bool = False,
        model_circuit_failure_threshold: int = 0,
        model_circuit_open_seconds: float = 60.0,
        model_rate_max_calls_per_window: int = 0,
        model_rate_window_seconds: float = 60.0,
    ) -> None:
        self.provider_id = provider_id
        self.backend = backend
        self._params: dict[str, Any] = {
            "model": model_name,
            "base_url": api_base_url,
            "api_key_env": api_key_env,
            "max_history": max_history,
            "timeout": timeout,
            "http_disable_connection_pool": http_disable_connection_pool,
            "model_circuit_failure_threshold": model_circuit_failure_threshold,
            "model_circuit_open_seconds": model_circuit_open_seconds,
            "model_rate_max_calls_per_window": model_rate_max_calls_per_window,
            "model_rate_window_seconds": model_rate_window_seconds,
        }
        if extra_headers:
            self._params["extra_headers"] = extra_headers
        self._failover_chain = failover_chain

    def api_base_url(self, url: str) -> "ModelProviderBuilder":
        return _mpb(self, api_base_url=url)

    def model_name(self, name: str) -> "ModelProviderBuilder":
        return _mpb(self, model_name=name)

    def api_key_env(self, env_var: str) -> "ModelProviderBuilder":
        return _mpb(self, api_key_env=env_var)

    def timeout(self, seconds: float) -> "ModelProviderBuilder":
        return _mpb(self, timeout=seconds)

    def failover_to(self, *provider_ids: str) -> "ModelProviderBuilder":
        p = self._params.copy()
        _KM = {"model": "model_name", "base_url": "api_base_url"}
        kwargs = {_KM.get(k, k): v for k, v in p.items()}
        return ModelProviderBuilder(
            provider_id=self.provider_id,
            backend=self.backend,
            failover_chain=provider_ids,
            **kwargs,
        )

    def build(self) -> ModelProvider:
        return ModelProvider(
            id=self.provider_id,
            backend=self.backend,
            params=self._params,
            failover_chain=self._failover_chain,
        )


def _mpb(b: ModelProviderBuilder, **kw: Any) -> ModelProviderBuilder:
    # _params keys differ from __init__ param names
    _KEY_MAP = {
        "model": "model_name",
        "base_url": "api_base_url",
    }
    p = {**b._params, **kw}
    kwargs = {_KEY_MAP.get(k, k): v for k, v in p.items()}
    return ModelProviderBuilder(
        provider_id=b.provider_id,
        backend=b.backend,
        failover_chain=b._failover_chain,
        **kwargs,
    )


class ModelRegistryBuilder:
    """
    model_providers.yaml → 模型注册表（default_provider + 多个 ModelProviderBuilder）。

    用法::

        registry = (
            ModelRegistryBuilder(default_provider="deepseek")
            .add(ModelProviderBuilder("stub", "stub"))
            .add(ModelProviderBuilder("deepseek", "openai_compatible")
                .api_base_url("https://api.deepseek.com")
                .model_name("deepseek-chat")
                .api_key_env("DEEPSEEK_API_KEY"))
            .build()
        )
    """

    def __init__(
        self,
        default_provider: str,
        providers: list[ModelProviderBuilder] | None = None,
    ) -> None:
        self._default = default_provider
        self._providers: list[ModelProviderBuilder] = providers or []

    def default_provider(self, pid: str) -> "ModelRegistryBuilder":
        return ModelRegistryBuilder(default_provider=pid, providers=self._providers)

    def add(self, pb: ModelProviderBuilder) -> "ModelRegistryBuilder":
        return ModelRegistryBuilder(default_provider=self._default, providers=[*self._providers, pb])

    def build(self) -> ModelRegistry:
        return ModelRegistry(
            providers={p.provider_id: p.build() for p in self._providers},
            default_provider_id=self._default,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MemoryBuilder
# ─────────────────────────────────────────────────────────────────────────────


class MemoryBuilder:
    """
    memory_policy.yaml → 长期记忆与向量检索配置。

    默认关闭记忆（``enabled=False``）；链式调用按需开启。
    """

    def __init__(
        self,
        enabled: bool = False,
        retrieve_top_k: int = 6,
        rrf_k: int = 60,
        rerank_enabled: bool = True,
        rerank_max_candidates: int = 24,
        chunk_max_chars: int = 512,
        chunk_overlap_chars: int = 64,
        promote_on_archive: bool = True,
        archive_chunk_max_chars: int = 8000,
        archive_trust: str = "medium",
        embedding_async: bool = True,
        embedding_dim: int = 64,
        fts_enabled: bool = True,
        vector_max_candidates: int = 200,
        channel_filter: str = "match_or_global",
        dual_store_ref: str = "builtin:dual_sqlite",
        embedding_ref: str = "builtin:hash",
        openai_embedding_api_key_env: str = "OPENAI_API_KEY",
        openai_embedding_base_url: str = "https://api.openai.com",
        openai_embedding_model: str = "text-embedding-3-small",
        openai_embedding_timeout: float = 30.0,
        remote_retrieval_url: str = "",
        remote_timeout_seconds: float = 5.0,
        memory_db_path: str = "platform_layer/resources/data/memory.db",
    ) -> None:
        self._enabled = enabled
        self._vals: dict[str, Any] = {
            "retrieve_top_k": retrieve_top_k,
            "rrf_k": rrf_k,
            "rerank_enabled": rerank_enabled,
            "rerank_max_candidates": rerank_max_candidates,
            "chunk_max_chars": chunk_max_chars,
            "chunk_overlap_chars": chunk_overlap_chars,
            "promote_on_archive": promote_on_archive,
            "archive_chunk_max_chars": archive_chunk_max_chars,
            "archive_trust": archive_trust,
            "embedding_async": embedding_async,
            "embedding_dim": embedding_dim,
            "fts_enabled": fts_enabled,
            "vector_max_candidates": vector_max_candidates,
            "channel_filter": channel_filter,
            "dual_store_ref": dual_store_ref,
            "embedding_ref": embedding_ref,
            "remote_retrieval_url": remote_retrieval_url,
            "remote_timeout_seconds": remote_timeout_seconds,
        }
        self._openai = {
            "api_key_env": openai_embedding_api_key_env,
            "base_url": openai_embedding_base_url,
            "model": openai_embedding_model,
            "timeout_seconds": openai_embedding_timeout,
        }
        self._memory_db_path = memory_db_path

    def enable(self) -> "MemoryBuilder":
        """开启记忆。"""
        return _mb(self, enabled=True)

    def disable(self) -> "MemoryBuilder":
        return _mb(self, enabled=False)

    def retrieve_top_k(self, k: int) -> "MemoryBuilder":
        return _mb(self, retrieve_top_k=k)

    def embedding_dim(self, dim: int) -> "MemoryBuilder":
        return _mb(self, embedding_dim=dim)

    def use_openai_embedding(
        self,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com",
        model: str = "text-embedding-3-small",
    ) -> "MemoryBuilder":
        """切换到 OpenAI 兼容嵌入后端（需相应安装依赖）。"""
        return _mb(self, embedding_ref="builtin:openai_compatible", _openai={
            "api_key_env": api_key_env, "base_url": base_url, "model": model,
            "timeout_seconds": self._openai["timeout_seconds"],
        })

    def memory_db_path(self, path: str) -> "MemoryBuilder":
        return _mb(self, memory_db_path=path)

    def build_policy(self) -> MemoryPolicyConfig:
        from core.memory.embedding_openai_params import OpenAICompatibleEmbeddingParams

        emb_openai: OpenAICompatibleEmbeddingParams | None = None
        if self._vals["embedding_ref"] == "builtin:openai_compatible":
            emb_openai = OpenAICompatibleEmbeddingParams(**self._openai)

        return MemoryPolicyConfig(
            enabled=self._enabled,
            embedding_openai=emb_openai,
            **self._vals,
        )

    def _storage_path(self, base: Path) -> Path:
        p = Path(self._memory_db_path)
        return p if p.is_absolute() else (base / p)

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


def _mb(b: MemoryBuilder, **kw: Any) -> MemoryBuilder:
    openai = kw.pop("_openai", None)
    parent = getattr(b, "_parent", None)
    merged = {**b._vals, **{k: v for k, v in kw.items() if k not in ("enabled", "memory_db_path")}}
    inst = MemoryBuilder(
        enabled=kw.get("enabled", b._enabled),
        memory_db_path=kw.get("memory_db_path", b._memory_db_path),
        **merged,
    )
    inst._openai = openai or b._openai
    object.__setattr__(inst, "_parent", parent)
    return inst


# ─────────────────────────────────────────────────────────────────────────────
# ToolBuilder
# ─────────────────────────────────────────────────────────────────────────────


class DeviceRoute:
    """设备工具路由（对应 tools.yaml.device_routes）。"""

    def __init__(
        self,
        tool: str,
        device: str,
        command: str,
        fixed_parameters: dict[str, Any] | None = None,
    ) -> None:
        self.tool = tool
        self.device = device
        self.command = command
        self.fixed_parameters = fixed_parameters or {}


class ToolBuilder:
    """
    tools.yaml → 本地工具注册、设备路由、网络策略。

    默认自带 ``echo``、``calc``、``now``；可按需 ``.register(tool_name, "module.path:func")``。

    外部用户推荐用法（完全不走 YAML 字符串引用）::

        from pompeii_agent import (
            ToolBuilder,
            ToolModuleImpl,
            McpStdioBridge,
            ToolNetworkPolicyConfig,
        )
        from my_company_tools import my_handler, another_handler

        # 方案 A：直接注册可调用对象（最简）
        tb = (
            ToolBuilder()
            .register_handler("my_tool", my_handler)
            .register_handler("another_tool", another_handler)
        )

        # 方案 B：注入完整工具模块（完全控制）
        my_tools = ToolModuleImpl(
            local_handlers={"my_tool": my_handler, "another_tool": another_handler},
            mcp=McpStdioBridge(server=McpServerEntry(...)),
            network_policy=ToolNetworkPolicyConfig(),
            device_backend=LocalSimulatorBackend(),
        )
        tb = ToolBuilder().tools_module(my_tools)

    """

    def __init__(
        self,
        local_handlers: dict[str, str] | None = None,
        device_routes: list[DeviceRoute] | None = None,
        enable_entrypoints: bool = True,
        entrypoint_group: str = "pompeii_agent.tools",
        device_backend_refs: tuple[str, ...] = ("builtin:simulator",),
        network_policy: ToolNetworkPolicyConfig | None = None,
    ) -> None:
        self._handlers = dict(local_handlers) if local_handlers else {
            "echo": "modules.tools.builtin_handlers:echo_handler",
            "calc": "modules.tools.builtin_handlers:calc_handler",
            "now": "modules.tools.builtin_handlers:now_handler",
        }
        self._device_routes = list(device_routes) if device_routes else []
        self._enable_entrypoints = enable_entrypoints
        self._entrypoint_group = entrypoint_group
        self._device_backend_refs = device_backend_refs
        self._network_policy = network_policy or ToolNetworkPolicyConfig()
        self._custom_mcp_bridge: McpToolBridge | None = None
        self._custom_tools_module: ToolModuleImpl | None = None

    def register(self, name: str, entrypoint: str) -> "ToolBuilder":
        """注册一个本地工具处理器（格式："module.path:func_name"）。"""
        self._handlers[name] = entrypoint; return self

    def register_handler(self, name: str, handler: Any) -> "ToolBuilder":
        """
        注册一个本地工具处理器（直接可调用对象，签名：Callable[[Session, ToolCall], ToolResult]）。

        与 ``.register(name, "module.path:func")`` 的区别：
        - 这里接受已经导入的函数/lambda/类实例，不需要字符串解析
        - 推荐用于外部包中的工具或闭包封装的工具
        """
        if callable(handler):
            # 与 .register() 共用同一 dict，但存 None placeholder 标记为"直接 handler"
            # _build_tools 中将遍历 self._direct_handlers 做区分
            if not hasattr(self, "_direct_handlers"):
                object.__setattr__(self, "_direct_handlers", {})
            self._direct_handlers[name] = handler
        return self

    def device_route(self, tool: str, device: str, command: str, **fixed: Any) -> "ToolBuilder":
        """添加设备路由。"""
        self._device_routes.append(DeviceRoute(tool=tool, device=device, command=command, fixed_parameters=fixed)); return self

    def mcp_bridge(self, bridge: McpToolBridge) -> "ToolBuilder":
        """
        注入一个预构建的 MCP 桥接器（完全替换 YAML 路径的 MCP 注入）。

        用法::

            from pompeii_agent import McpStdioBridge, McpServerEntry

            bridge = McpStdioBridge(server=McpServerEntry(
                id="my-server",
                command="python",
                args=["-m", "my_mcp_server"],
            ))
            tb = ToolBuilder().mcp_bridge(bridge)

        等价于让 ToolBuilder 不走 mcp_servers.yaml 中的配置。
        """
        self._custom_mcp_bridge = bridge
        return self

    def tools_module(self, module: ToolModuleImpl) -> "ToolBuilder":
        """
        直接注入一个完整的 ToolModuleImpl（完全替换 Builder 的工具装配逻辑）。

        当用户需要：
        - 完全自定义 local_handlers、device_routes、mcp、network_policy、device_backend
        - 不走 Builder 的 YAML fallback 和 entrypoint discovery

        时，使用此方法。AgentBuilder.build() 将直接使用注入的 module，跳过内部 _build_tools()。

        用法::

            from pompeii_agent import ToolModuleImpl, ToolNetworkPolicyConfig

            my_module = ToolModuleImpl(
                local_handlers={"my_tool": my_handler},
                device_routes={},
                mcp=None,
                network_policy=ToolNetworkPolicyConfig(),
                device_backend=LocalSimulatorBackend(),
            )
            tb = ToolBuilder().tools_module(my_module)
        """
        self._custom_tools_module = module
        return self

    def allowlist_mcp_tools(self, names: list[str]) -> "ToolBuilder":
        """MCP 工具白名单（需同时开启 network_policy）。"""
        self._network_policy = ToolNetworkPolicyConfig(
            enabled=True,
            mcp_allowlist_enforced=True,
            mcp_tool_allowlist=tuple(names),
            deny_tool_names=self._network_policy.deny_tool_names,
            http_url_guard_enabled=self._network_policy.http_url_guard_enabled,
            http_url_allowed_hosts=self._network_policy.http_url_allowed_hosts,
            http_blocked_content_type_prefixes=self._network_policy.http_blocked_content_type_prefixes,
        ); return self

    def build_config(self) -> tuple[dict[str, str], list[DeviceRoute], ToolNetworkPolicyConfig]:
        return self._handlers, self._device_routes, self._network_policy

    def build_module(self) -> ToolModuleImpl | None:
        """
        基于当前 Builder 状态构建 ToolModuleImpl。

        供外部用户在注入前预览或做单元测试。
        不走 YAML，不走 entrypoint discovery，仅用 Builder 状态。
        如已调用 ``.tools_module()`` 则返回注入的 module。
        """
        if self._custom_tools_module is not None:
            return self._custom_tools_module
        from app.device_backend_registry import build_device_backend as _build_dev_backend
        from modules.tools.mcp_bridge import McpToolBridge

        # 合并 string refs 和 direct handlers
        direct: dict[str, Any] = getattr(self, "_direct_handlers", {})
        resolved: dict[str, Any] = {}
        for name, ref in self._handlers.items():
            if ref == HTTP_GET_TOOL_REF:
                resolved[name] = make_http_get_handler(self._network_policy)
            else:
                resolved[name] = load_tool_handler(ref)
        resolved = {**direct, **resolved}

        device_requests = {
            r.tool: DeviceRequest(device=r.device, command=r.command, parameters=r.fixed_parameters)
            for r in self._device_routes
        }
        device_backend = _build_dev_backend(
            list(self._device_backend_refs) if self._device_backend_refs else None,
            fallback_to_simulator=True,
        )
        mcp = self._custom_mcp_bridge
        return ToolModuleImpl(
            local_handlers=resolved,
            device_routes=device_requests,
            mcp=mcp,
            network_policy=self._network_policy,
            device_backend=device_backend,
        )

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# SecurityBuilder
# ─────────────────────────────────────────────────────────────────────────────


class SecurityBuilder:
    """
    security_policies.yaml → 安全守卫（输入限流、工具风险、guard 模型）。

    默认 ``baseline`` 策略（与仓库一致）。
    """

    def __init__(
        self,
        policy_id: str = "baseline",
        input_max_chars: int = 12000,
        max_requests_per_minute: int = 60,
        guard_enabled: bool = False,
        guard_block_patterns: list[str] | None = None,
        guard_tool_output_redaction: str = "[guard_blocked_tool_output]",
        guard_evaluator_ref: str = "builtin:default",
        guard_model_ref: str = "builtin:none",
        guard_model_provider_id: str | None = None,
        default_tool_risk_level: str = "low",
        tool_confirmation_level: str = "high",
        tool_risk_overrides: dict[str, str] | None = None,
        tool_output_max_chars: int = 0,
        tool_output_truncation_marker: str = "…[truncated]",
        tool_output_injection_patterns: list[str] | None = None,
        tool_output_injection_redaction: str = "[tool_output_injection_blocked]",
        tool_output_max_chars_by_trust: dict[str, int] | None = None,
        default_tool_output_trust: str = "high",
        tool_output_trust_overrides: dict[str, str] | None = None,
        mcp_tool_output_trust: str = "low",
        device_tool_output_trust: str = "low",
        http_fetch_tool_output_trust: str = "low",
        # 资源访问规则（resource_access.yaml）
        resource_access_profile_id: str = "default",
        resource_access_rules: dict[str, dict[str, str | bool]] | None = None,
    ) -> None:
        self._policy_id = policy_id
        self._vals: dict[str, Any] = {
            "input_max_chars": input_max_chars,
            "max_requests_per_minute": max_requests_per_minute,
            "guard_enabled": guard_enabled,
            "guard_block_patterns": guard_block_patterns or [],
            "guard_tool_output_redaction": guard_tool_output_redaction,
            "guard_evaluator_ref": guard_evaluator_ref,
            "guard_model_ref": guard_model_ref,
            "guard_model_provider_id": guard_model_provider_id,
            "default_tool_risk_level": default_tool_risk_level,
            "tool_confirmation_level": tool_confirmation_level,
            "tool_risk_overrides": tool_risk_overrides or {},
            "tool_output_max_chars": tool_output_max_chars,
            "tool_output_truncation_marker": tool_output_truncation_marker,
            "tool_output_injection_patterns": tuple(tool_output_injection_patterns or [
                "<!-- pompeii:zone-end", "<!-- pompeii:zone-begin",
            ]),
            "tool_output_injection_redaction": tool_output_injection_redaction,
            "tool_output_max_chars_by_trust": tool_output_max_chars_by_trust or {},
            "default_tool_output_trust": default_tool_output_trust,
            "tool_output_trust_overrides": tool_output_trust_overrides or {},
            "mcp_tool_output_trust": mcp_tool_output_trust,
            "device_tool_output_trust": device_tool_output_trust,
            "http_fetch_tool_output_trust": http_fetch_tool_output_trust,
        }
        self._resource_access_profile_id = resource_access_profile_id
        self._resource_access_rules = resource_access_rules or {
            "long_term_memory": {"read": "allow", "write": "allow"},
            "session_data": {"read": "allow", "write": "allow"},
            "tool_execution": {"read": "allow", "write": "allow"},
            "device_access": {"read": "allow", "write": "allow"},
            "filesystem": {"read": "allow", "write": "deny"},
            "external_api": {"read": "allow", "write": "deny"},
            "multimodal_image_url": {"read": "allow", "write": "deny"},
            "remote_retrieval": {"read": "allow", "write": "deny"},
        }

    def enable_guard(self, provider_id: str | None = None) -> "SecurityBuilder":
        """开启 Guard 模型过滤。"""
        return _sb(self, guard_enabled=True, guard_model_ref="builtin:default",
                   guard_model_provider_id=provider_id)

    def tool_risk(self, level: str = "low") -> "SecurityBuilder":
        return _sb(self, default_tool_risk_level=level)

    def tool_risk_override(self, tool: str, level: str) -> "SecurityBuilder":
        overrides = dict(self._vals["tool_risk_overrides"])
        overrides[tool] = level
        return _sb(self, tool_risk_overrides=overrides)

    def build_security_policy(self) -> "SecurityPolicySpec":
        from app.config_loaders.security_policy_loader import SecurityPolicySpec

        return SecurityPolicySpec(
            id=self._policy_id,
            input_max_chars=self._vals["input_max_chars"],
            max_requests_per_minute=self._vals["max_requests_per_minute"],
            guard_enabled=self._vals["guard_enabled"],
            guard_block_patterns=tuple(self._vals["guard_block_patterns"]),
            guard_tool_output_redaction=self._vals["guard_tool_output_redaction"],
            guard_evaluator_ref=self._vals["guard_evaluator_ref"],
            guard_model_ref=self._vals["guard_model_ref"],
            guard_model_provider_id=self._vals["guard_model_provider_id"],
            default_tool_risk_level=self._vals["default_tool_risk_level"],
            tool_confirmation_level=self._vals["tool_confirmation_level"],
            tool_risk_overrides=self._vals["tool_risk_overrides"],
            tool_output_max_chars=self._vals["tool_output_max_chars"],
            tool_output_truncation_marker=self._vals["tool_output_truncation_marker"],
            tool_output_injection_patterns=self._vals["tool_output_injection_patterns"],
            tool_output_injection_redaction=self._vals["tool_output_injection_redaction"],
            tool_output_max_chars_by_trust=self._vals["tool_output_max_chars_by_trust"],
            default_tool_output_trust=self._vals["default_tool_output_trust"],
            tool_output_trust_overrides=self._vals["tool_output_trust_overrides"],
            mcp_tool_output_trust=self._vals["mcp_tool_output_trust"],
            device_tool_output_trust=self._vals["device_tool_output_trust"],
            http_fetch_tool_output_trust=self._vals["http_fetch_tool_output_trust"],
        )

    def build_resource_access(self) -> tuple[str, ResourceAccessEvaluator]:
        """返回 (profile_id, evaluator)。"""
        rules: dict[str, ResourceAccessRule] = {}
        for rid, spec in self._resource_access_rules.items():
            if not isinstance(rid, str):
                continue
            rules[rid] = ResourceAccessRule(
                read=spec.get("read", "allow"),
                write=spec.get("write", "allow"),
                read_requires_approval=bool(spec.get("read_requires_approval", False)),
                write_requires_approval=bool(spec.get("write_requires_approval", False)),
            )
        profile = ResourceAccessProfile(rules=rules)
        return self._resource_access_profile_id, ResourceAccessEvaluator(profile)

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


def _sb(b: SecurityBuilder, **kw: Any) -> SecurityBuilder:
    parent = getattr(b, "_parent", None)
    v = {**b._vals, **kw}
    inst = SecurityBuilder(
        policy_id=b._policy_id,
        resource_access_profile_id=b._resource_access_profile_id,
        resource_access_rules=b._resource_access_rules,
        **v,
    )
    object.__setattr__(inst, "_parent", parent)
    return inst


# ─────────────────────────────────────────────────────────────────────────────
# RuntimeBuilder
# ─────────────────────────────────────────────────────────────────────────────


class RuntimeBuilder:
    """
    runtime.yaml + storage_profiles.yaml → 会话存储路径。

    默认 SQLite（路径相对于 base src_root）。
    """

    def __init__(
        self,
        sqlite_path: str = "platform_layer/resources/data/sessions.db",
        memory_db_path: str = "platform_layer/resources/data/memory.db",
        port_interaction_mode_ref: str = "builtin:cli",
        pending_state_backend: Literal["memory", "sqlite_shared"] = "memory",
        pending_state_sqlite_path: str = "platform_layer/resources/data/port_pending.db",
    ) -> None:
        self._sqlite_path = sqlite_path
        self._memory_db_path = memory_db_path
        self._port_mode = port_interaction_mode_ref
        self._pending_backend = pending_state_backend
        self._pending_path = pending_state_sqlite_path

    def sqlite_path(self, path: str) -> "AgentBuilder":
        object.__setattr__(self, "_sqlite_path", path); return self._parent or self

    def build_session_store(self, base: Path) -> SessionStore:
        p = Path(self._sqlite_path)
        resolved = p if p.is_absolute() else (base / p)
        return resolve_session_store("builtin:sqlite", sqlite_path=resolved)

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# ResourceAccessEvaluator helper (standalone, no YAML)
# ─────────────────────────────────────────────────────────────────────────────


class ResourceAccessBuilder:
    """
    resource_access.yaml → 数据访问权限（read/write allow/deny + approval）。

    默认全 allow，适合快速原型；生产用 ``.deny(tool_execution_write=True)`` 收紧。
    """

    def __init__(
        self,
        profile_id: str = "default",
        rules: dict[str, dict[str, str | bool]] | None = None,
    ) -> None:
        self._profile_id = profile_id
        self._rules = rules or {
            "long_term_memory": {"read": "allow", "write": "allow"},
            "session_data": {"read": "allow", "write": "allow"},
            "tool_execution": {"read": "allow", "write": "allow"},
            "device_access": {"read": "allow", "write": "allow"},
            "filesystem": {"read": "allow", "write": "deny"},
            "external_api": {"read": "allow", "write": "deny"},
            "multimodal_image_url": {"read": "allow", "write": "deny"},
            "remote_retrieval": {"read": "allow", "write": "deny"},
        }

    def allow(self, resource: str, read: bool = True, write: bool = True) -> "ResourceAccessBuilder":
        self._rule(resource, read=("allow" if read else "deny"), write=("allow" if write else "deny")); return self

    def deny(self, resource: str, read: bool = False, write: bool = False) -> "ResourceAccessBuilder":
        self._rule(resource, read=("allow" if read else "deny"), write=("allow" if write else "deny")); return self

    def _rule(
        self, resource: str, read: str, write: str, read_req: bool = False, write_req: bool = False
    ) -> "ResourceAccessBuilder":
        r = dict(self._rules)
        r[resource] = {"read": read, "write": write,
                       "read_requires_approval": read_req, "write_requires_approval": write_req}
        return ResourceAccessBuilder(profile_id=self._profile_id, rules=r)

    def build(self) -> tuple[str, ResourceAccessEvaluator]:
        rules: dict[str, ResourceAccessRule] = {}
        for rid, spec in self._rules.items():
            rules[rid] = ResourceAccessRule(
                read=spec.get("read", "allow"),
                write=spec.get("write", "allow"),
                read_requires_approval=bool(spec.get("read_requires_approval", False)),
                write_requires_approval=bool(spec.get("write_requires_approval", False)),
            )
        return self._profile_id, ResourceAccessEvaluator(ResourceAccessProfile(rules=rules))

    def done(self) -> "AgentBuilder":
        """结束子配置，返回 AgentBuilder 继续链式调用。"""
        return getattr(self, "_parent", None) or self  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# AgentBuilder — 聚合所有 Builder，一次 build() 出 kernel
# ─────────────────────────────────────────────────────────────────────────────


class AgentBuilder:
    """
    聚合式 Builder：替代所有 YAML 配置，一行 ``.build()`` 出 ``AgentCoreImpl``。

    用法::

        kernel = (
            AgentBuilder()
            .session(model="stub", skills=["echo"])
            .kernel(core_max_loops=8, tool_allowlist=["echo"])
            .memory().enable().retrieve_top_k(6)
            .tool().register("my_tool", "mypackage.tools:my_handler")
            .build()
        )

    - ``.session(...)`` / ``.kernel(...)`` / ``.memory()`` / ``.tool(...)`` / ``.security(...)``
      等均为链式配置，返回 self（可直接连续调用）。
    - ``.build()`` 使用 Builder 状态构造内核，完全不走 YAML。
    """

    def __init__(self) -> None:
        self._session: SessionBuilder | None = None
        self._kernel: KernelBuilder | None = None
        self._memory: MemoryBuilder = MemoryBuilder()
        self._tool: ToolBuilder = ToolBuilder()
        self._security: SecurityBuilder = SecurityBuilder()
        self._runtime: RuntimeBuilder = RuntimeBuilder()
        self._resource_access: ResourceAccessBuilder = ResourceAccessBuilder()
        self._model_registry: ModelRegistry | None = None
        self._src_root: Path | None = None
        # inject parent so chain methods can return AgentBuilder
        for _b in (self._memory, self._tool, self._security, self._runtime, self._resource_access):
            object.__setattr__(_b, "_parent", self)
        # KernelBuilder default (will be replaced by .kernel() call)
        self._kernel = KernelBuilder()
        object.__setattr__(self._kernel, "_parent", self)

    # ── 子 Builder 访问 ─────────────────────────────────────────────────────

    def session(
        self,
        model: str,
        skills: list[str],
        limits: SessionLimitsBuilder | None = None,
        prompt_profile: str = "default",
        prompt_strategy: str = "default",
        security: str = "baseline",
    ) -> "AgentBuilder":
        self._session = SessionBuilder(
            model=model,
            skills=skills,
            limits=limits,
            prompt_profile=prompt_profile,
            prompt_strategy=prompt_strategy,
            security=security,
        )
        return self

    def kernel(
        self,
        core_max_loops: int = 8,
        max_tool_calls_per_run: int = 8,
        tool_allowlist: list[str] | None = None,
        tool_confirmation_required: list[str] | None = None,
        context_isolation: bool = True,
        tool_policy_engine_ref: str = "builtin:default",
        loop_policy_engine_ref: str = "builtin:default",
        prompt_strategy_ref: str = "builtin:none",
    ) -> "AgentBuilder":
        self._kernel = KernelBuilder(
            core_max_loops=core_max_loops,
            max_tool_calls_per_run=max_tool_calls_per_run,
            tool_allowlist=tool_allowlist or [],
            tool_confirmation_required=tool_confirmation_required or [],
            context_isolation_enabled=context_isolation,
            tool_policy_engine_ref=tool_policy_engine_ref,
            loop_policy_engine_ref=loop_policy_engine_ref,
            prompt_strategy_ref=prompt_strategy_ref,
        )
        object.__setattr__(self._kernel, "_parent", self)
        return self

    def memory(self) -> "MemoryBuilder":
        return self._memory

    def tool(self) -> "ToolBuilder":
        return self._tool

    def security(self) -> "SecurityBuilder":
        return self._security

    def runtime(self) -> "RuntimeBuilder":
        return self._runtime

    def resource_access(self) -> "ResourceAccessBuilder":
        return self._resource_access

    def model_registry(self, registry: ModelRegistry) -> "AgentBuilder":
        self._model_registry = registry
        return self

    def src_root(self, path: Path | str) -> "AgentBuilder":
        self._src_root = Path(path)
        return self

    def model_registry(self, registry: ModelRegistry) -> "AgentBuilder":
        self._model_registry = registry
        return self

    def src_root(self, path: Path | str) -> "AgentBuilder":
        self._src_root = Path(path)
        return self

    # ── build() ─────────────────────────────────────────────────────────────

    def build(self) -> AgentCoreImpl:
        """
        基于 Builder 状态装配 AgentCoreImpl，完全不走 YAML。
        如未调用 ``.session()`` / ``.kernel()`` 使用仓库默认。
        """
        import tempfile
        from app.config_loaders.security_policy_loader import SecurityPolicyRegistry

        # base：若未指定 src_root 且有 session/kernel 配置（走 Builder），用临时目录兜底（避免 YAML 缺失报错）
        base: Path
        if self._src_root is not None:
            base = self._src_root
        else:
            # 有 Builder 配置 → 用仓库根（有完整 YAML，Builders 覆盖值）
            from platform_layer.bundled_root import framework_root
            base = framework_root()

        # ── session ──────────────────────────────────────────────────────
        if self._session is None:
            from pathlib import Path as P
            from pompeii_agent.config import bundled_session_defaults_path
            from pompeii_agent.config import session_provider_from_yaml
            session_yaml = bundled_session_defaults_path(base)
            provider: ConfigProvider = session_provider_from_yaml(session_yaml, override_model="stub")
        else:
            provider = self._session.build_config_provider()

        # ── kernel ────────────────────────────────────────────────────────
        kernel_cfg: KC = self._kernel.build() if self._kernel else _default_kernel_config()

        # ── model registry ───────────────────────────────────────────────
        if self._model_registry is not None:
            model_registry = self._model_registry
        else:
            model_registry = _load_model_registry_from_yaml(base)

        # ── session store ─────────────────────────────────────────────────
        store = self._runtime.build_session_store(base)

        # ── memory orchestrator ───────────────────────────────────────────
        memory_orch: MemoryOrchestrator | None = self._build_memory_orchestrator(base)

        # ── resource access ──────────────────────────────────────────────
        if self._resource_access is not None:
            _ra_profile_id, resource_gate = self._resource_access.build()
        else:
            from app.config_loaders.resource_index_loader import ResourceIndex
            from app.config_loaders.resource_access_loader import ResourceAccessRegistry
            _ra_profile_id, resource_gate = _load_resource_access_from_yaml(base)

        # ── tools ─────────────────────────────────────────────────────────
        tools_mod = self._build_tools(base, memory_orch)

        # ── security ──────────────────────────────────────────────────────
        sec_policy: SecurityPolicySpec
        if self._security is not None:
            sec_policy = self._security.build_security_policy()
            sec_profile_id = self._security._policy_id
        else:
            sec_policy, sec_profile_id = _load_security_policy_from_yaml(base)

        security_registry = SecurityPolicyRegistry(policies={sec_policy.id: sec_policy})
        guard_evaluator = resolve_guard_evaluator(evaluator_ref=sec_policy.guard_evaluator_ref)
        guard_model_should_block = resolve_guard_model_should_block(
            guard_model_ref=sec_policy.guard_model_ref,
            guard_model_provider_id=sec_policy.guard_model_provider_id,
            model_registry=model_registry,
        )

        # ── assembly ─────────────────────────────────────────────────────
        tool_policy_decide = resolve_tool_policy_decide(kernel_cfg.tool_policy_engine_ref)
        loop_governance_fn = resolve_loop_governance_fn(kernel_cfg.loop_policy_engine_ref)

        _, tool_handlers, tool_np = self._tool.build_config()
        tool_registry_cfg = _make_tool_registry_config(tool_handlers, tool_np, self._tool)

        assembly_mod = AssemblyModuleImpl(
            memory_orchestrator=memory_orch,
            resource_access=resource_gate,
            context_isolation_enabled=kernel_cfg.context_isolation_enabled,
            tool_network_policy=tool_np,
        )

        # ── model module ─────────────────────────────────────────────────
        skill_registry = _load_skill_registry_from_yaml(base)
        merged_skill_registry = merge_skill_registry_with_entrypoints(skill_registry)
        model = ModelModuleImpl(
            registry=model_registry,
            skill_registry=merged_skill_registry.skills,
            prompt_cache=PromptCache(),
            default_prompt_strategy_ref=kernel_cfg.prompt_strategy_ref,
        )

        # ── archive LLM binding ───────────────────────────────────────────
        archive_llm = self._build_archive_llm(kernel_cfg, model_registry)

        # ── session manager ───────────────────────────────────────────────
        from core import SessionManagerImpl
        manager = SessionManagerImpl(store)

        return AgentCoreImpl(
            session_manager=manager,
            assembly=assembly_mod,
            model=model,
            tools=tools_mod,
            config_provider=provider,
            kernel_config=kernel_cfg,
            security_policies=security_registry.policies,
            guard_evaluator=guard_evaluator,
            guard_model_should_block=guard_model_should_block,
            memory_orchestrator=memory_orch,
            archive_llm=archive_llm,
            resource_access=resource_gate,
            tool_policy_decide=tool_policy_decide,
            loop_governance_fn=loop_governance_fn,
        )

    # ── internal helpers ───────────────────────────────────────────────────

    def _build_memory_orchestrator(self, base: Path) -> MemoryOrchestrator | None:
        policy = self._memory.build_policy()
        if not policy.enabled:
            return None

        # storage path
        mp = self._memory._storage_path(base)
        mp.parent.mkdir(parents=True, exist_ok=True)
        store = resolve_dual_memory_store(policy.dual_store_ref, memory_db_path=mp)
        emb = resolve_embedding_provider(policy.embedding_ref, embedding_dim=policy.embedding_dim, policy=policy)
        _, gate = self._resource_access.build()
        return MemoryOrchestrator(store=store, embedding=emb, policy=policy, resource_access=gate)

    def _build_tools(self, base: Path, memory_orch: MemoryOrchestrator | None) -> ToolModuleImpl:
        # 完全自定义工具模块路径：直接注入，无任何 YAML / entrypoint 处理
        if self._tool._custom_tools_module is not None:
            return self._tool._custom_tools_module

        handlers, device_routes, net_policy = self._tool.build_config()
        direct: dict[str, Any] = getattr(self._tool, "_direct_handlers", {})
        local_handlers: dict[str, Any] = {}
        for name, ref in handlers.items():
            if ref == HTTP_GET_TOOL_REF:
                local_handlers[name] = make_http_get_handler(net_policy)
            else:
                local_handlers[name] = load_tool_handler(ref)
        # 直接注册的可调用对象优先级更高（覆盖同名的 string-ref handler）
        local_handlers = {**local_handlers, **direct}

        if self._tool._enable_entrypoints:
            ep = discover_entrypoint_handlers(group=self._tool._entrypoint_group)
            for n, h in ep.items():
                assert_tool_handler_signature(h, path=f"entrypoint:{self._tool._entrypoint_group}:{n}")
            local_handlers = {**ep, **local_handlers}
        local_handlers["search_memory"] = _make_memory_search_handler(memory_orch)

        device_requests = {
            r.tool: DeviceRequest(device=r.device, command=r.command, parameters=r.fixed_parameters)
            for r in device_routes
        }
        device_backend = _build_dev_backend(
            list(self._tool._device_backend_refs) if self._tool._device_backend_refs else None,
            fallback_to_simulator=True,
        )
        mcp = self._tool._custom_mcp_bridge or _load_mcp_bridge(base)
        return ToolModuleImpl(
            local_handlers=local_handlers,
            device_routes=device_requests,
            mcp=mcp,
            network_policy=net_policy,
            device_backend=device_backend,
        )

    def _build_archive_llm(
        self, kernel_cfg: KC, model_registry: ModelRegistry
    ) -> "ArchiveLlmSummaryBinding | None":
        if not kernel_cfg.archive_llm_summary_enabled:
            return None
        pid = kernel_cfg.archive_llm_summary_provider_id or model_registry.default_provider_id

        def summarize(*, provider_id: str, dialogue_plain: str, max_output_chars: int, system_prompt: str) -> str:
            return summarize_dialogue_for_archive(
                registry=model_registry,
                provider_id=provider_id,
                dialogue_plain=dialogue_plain,
                max_output_chars=max_output_chars,
                system_prompt=system_prompt,
            )

        from core.archive_llm_summary import ArchiveLlmSummaryBinding
        return ArchiveLlmSummaryBinding(
            provider_id=pid,
            max_dialogue_chars=kernel_cfg.archive_llm_summary_max_dialogue_chars,
            max_output_chars=kernel_cfg.archive_llm_summary_max_output_chars,
            system_prompt=kernel_cfg.archive_llm_summary_system_prompt,
            summarize=summarize,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers (replaces YAML loaders for Builder path)
# ─────────────────────────────────────────────────────────────────────────────

from app.config_loaders.kernel_config_loader import KernelConfigSource, load_kernel_config
from app.config_loaders.model_provider_loader import ModelProviderSource, load_model_registry
from app.config_loaders.prompt_config_loader import (
    PromptConfigSource, load_prompt_config, merge_prompt_config_into_registry,
)
from app.config_loaders.skill_registry_loader import SkillRegistrySource, load_skill_registry
from app.config_loaders.resource_index_loader import ResourceIndex
from app.config_loaders.resource_access_loader import ResourceAccessRegistry
from app.config_loaders.security_policy_loader import SecurityPolicySource, load_security_policy_registry


def _default_kernel_config() -> KC:
    from platform_layer.bundled_root import framework_root
    base = framework_root()
    return load_kernel_config(KernelConfigSource(path=base / "platform_layer" / "resources" / "config" / "kernel_config.yaml"))


def _load_model_registry_from_yaml(base: Path) -> ModelRegistry:
    cfg = base / "platform_layer" / "resources" / "config"
    reg = load_model_registry(ModelProviderSource(path=cfg / "model_providers.yaml"))
    pcfg = load_prompt_config(PromptConfigSource(path=cfg / "prompts.yaml"))
    return merge_prompt_config_into_registry(registry=reg, prompt_config=pcfg)


def _load_skill_registry_from_yaml(base: Path):
    cfg = base / "platform_layer" / "resources" / "config"
    return load_skill_registry(SkillRegistrySource(path=cfg / "skills.yaml"))


def _load_security_policy_from_yaml(base: Path) -> tuple[Any, str]:
    cfg = base / "platform_layer" / "resources" / "config"
    index = ResourceIndex(
        active_security_policy="baseline",
        active_storage_profile="default",
        active_resource_access_profile="default",
    )
    reg = load_security_policy_registry(SecurityPolicySource(path=cfg / "security_policies.yaml"))
    policy = reg.policies[index.active_security_policy]
    return policy, index.active_security_policy


def _load_resource_access_from_yaml(base: Path) -> tuple[str, ResourceAccessEvaluator]:
    from app.config_loaders.resource_access_loader import load_resource_access_registry
    from app.config_loaders.resource_index_loader import load_resource_index, ResourceIndexSource
    cfg = base / "platform_layer" / "resources" / "config"
    index = load_resource_index(ResourceIndexSource(path=cfg / "resource_index.yaml"))
    reg = load_resource_access_registry(cfg / "resource_access.yaml")
    profile = reg.profiles.get(index.active_resource_access_profile) or list(reg.profiles.values())[0]
    return index.active_resource_access_profile, ResourceAccessEvaluator(profile)


def _make_tool_registry_config(
    handlers: dict[str, str],
    net_policy: ToolNetworkPolicyConfig,
    tool: ToolBuilder,
) -> "ToolRegistryConfig":
    from modules.tools.network_policy import ToolNetworkPolicyConfig
    from app.config_loaders.tool_registry_loader import DeviceToolRoute, ToolRegistryConfig
    return ToolRegistryConfig(
        local_handlers=handlers,
        device_routes={r.tool: DeviceToolRoute(
            tool=r.tool, device=r.device, command=r.command, fixed_parameters=r.fixed_parameters
        ) for r in tool._device_routes},
        enable_entrypoints=tool._enable_entrypoints,
        entrypoint_group=tool._entrypoint_group,
        network_policy=net_policy,
        device_backend_refs=tool._device_backend_refs,
    )


def _load_mcp_bridge(src_root: Path) -> McpToolBridge | None:
    try:
        from infra.mcp_config_loader import McpConfigSource, load_mcp_config
        from app.mcp_bridge_registry import resolve_mcp_bridge
        cfg = load_mcp_config(
            McpConfigSource(path=src_root / "platform_layer" / "resources" / "config" / "mcp_servers.yaml"),
            src_root=src_root,
        )
        if not cfg.enabled or not cfg.servers:
            return None
        return resolve_mcp_bridge(cfg=cfg, src_root=src_root)
    except Exception:
        return None


def _make_memory_search_handler(memory_orch: MemoryOrchestrator | None):
    from core.session.session import Session
    from core.types import ToolCall, ToolResult
    def handler(session: Session, tool_call: ToolCall) -> ToolResult:
        q = str(tool_call.arguments.get("query", ""))
        if memory_orch is None:
            return ToolResult(name=tool_call.name, output={"hits": [], "disabled": True, "query": q})
        hits = memory_orch.retrieve_as_tool_json(user_id=session.user_id, channel=session.channel, query_text=q)
        return ToolResult(name=tool_call.name, output={"hits": hits, "query": q})
    return handler


# ─────────────────────────────────────────────────────────────────────────────
# Re-export types for convenience
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Builders
    "AgentBuilder",
    "DeviceRoute",
    "KernelBuilder",
    "MemoryBuilder",
    "ModelProviderBuilder",
    "ModelRegistryBuilder",
    "ResourceAccessBuilder",
    "RuntimeBuilder",
    "SecurityBuilder",
    "SessionBuilder",
    "SessionLimitsBuilder",
    "ToolBuilder",
    # Tool subsystem types (re-exported for convenience)
    "ToolModuleImpl",
    "ToolNetworkPolicyConfig",
    "McpToolBridge",
]
