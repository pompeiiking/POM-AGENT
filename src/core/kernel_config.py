from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KernelConfig:
    """
    内核长期配置（Kernel Governance）。

    设计意图：
    - 会话级策略（model/skills/limits/security）属于 SessionConfig，由 ConfigProvider 提供
    - 内核级兜底与治理参数属于 KernelConfig，由装配层读取并注入 Core
    """

    core_max_loops: int
    max_tool_calls_per_run: int
    tool_allowlist: list[str]
    tool_confirmation_required: list[str]
    # 归档后异步 LLM 摘要（写入 session_archives.llm_*；密钥仍走 model provider 的 api_key_env）
    archive_llm_summary_enabled: bool = False
    archive_llm_summary_provider_id: str = ""
    archive_llm_summary_max_dialogue_chars: int = 12000
    archive_llm_summary_max_output_chars: int = 2000
    archive_llm_summary_system_prompt: str = ""
    # 关卡②：对送入 LLM 的文本加结构化分区标记（组装部 + 模型部 history/system）
    context_isolation_enabled: bool = True
    # 可插拔策略：见 app.tool_policy_registry / app.loop_policy_registry
    tool_policy_engine_ref: str = "builtin:default"
    loop_policy_engine_ref: str = "builtin:default"
    # 系统提示词后处理：builtin:none 或 entrypoint:<name> → pompeii_agent.prompt_strategies
    prompt_strategy_ref: str = "builtin:none"
    # /delegate 子代理目标白名单；空元组表示不限制（与 intent 解析 token 规则一致）
    delegate_target_allowlist: tuple[str, ...] = ()

