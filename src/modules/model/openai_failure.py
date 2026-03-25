"""OpenAI 兼容路径上「文本形态失败」的启发式判定（与 failover / 熔断共用）。"""

from __future__ import annotations

from .interface import ModelOutput

OPENAI_SOFT_FAILURE_MARKERS = (
    "调用失败",
    "流式调用失败",
    "未配置 api_key_env",
    "未配置：请在环境变量",
    "返回结果为空",
    "流式返回为空",
    "熔断中",  # 与 model_circuit_precheck 文案一致，便于 failover_chain 换用备用 provider
    "调用过于频繁",  # 与 model_rate_precheck 文案一致
)


def openai_output_suggests_failover(out: ModelOutput) -> bool:
    if out.kind != "text":
        return False
    content = str(out.content or "")
    return any(m in content for m in OPENAI_SOFT_FAILURE_MARKERS)
