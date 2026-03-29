"""
OpenAI 兼容 Chat 的「声明式路由」解析（自研，不依赖 LiteLLM 等第三方）。

与常见 LLM 网关类项目一致的核心思想：
- **单一协议适配器**：只认 OpenAI Chat Completions 形态；
- **配置驱动路由**：用 base_url、model、鉴权环境变量区分供应商，而不是为每家写死分支；
- **可选统一 model 字符串**：`model_id: "厂商前缀/远端模型名"`，在省略 `base_url` 时按前缀选用内置默认根 URL
  （仅覆盖常见兼容端点；未知前缀必须显式写 `base_url`）。

详见 model_providers.yaml 顶部说明。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from modules.model.config import ModelProvider

# 与 LiteLLM/OpenRouter 等文档中常见前缀对齐的默认根 URL（不含 path）。
# 若你的网关路径非 /v1/chat/completions，请用 params.chat_completions_path 覆盖。
_VENDOR_DEFAULT_BASE_URL: dict[str, str] = {
    "openai": "https://api.openai.com",
    "deepseek": "https://api.deepseek.com",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "xai": "https://api.x.ai/v1",
    "perplexity": "https://api.perplexity.ai",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}


@dataclass(frozen=True, slots=True)
class OpenAiChatRoute:
    """一次解析结果，供单次 HTTP 调用使用（不含密钥明文）。"""

    provider_id: str
    api_key_env: str
    base_url: str
    chat_completions_path: str
    model: str
    timeout_seconds: float
    http_disable_connection_pool: bool
    vendor_hint: str | None


@dataclass(frozen=True, slots=True)
class OpenAiRouteResolution:
    route: OpenAiChatRoute | None
    error_message: str | None

    @property
    def ok(self) -> bool:
        return self.route is not None and self.error_message is None


def chat_completions_url(route: OpenAiChatRoute) -> str:
    root = route.base_url.rstrip("/")
    path = route.chat_completions_path if route.chat_completions_path.startswith("/") else f"/{route.chat_completions_path}"
    return f"{root}{path}"


def _boolish(params: Mapping[str, Any], key: str) -> bool:
    v = params.get(key)
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"):
        return True
    return False


def _timeout_seconds(params: Mapping[str, Any]) -> float:
    t = params.get("timeout", 30.0)
    if isinstance(t, (int, float)) and not isinstance(t, bool):
        return float(t)
    return 30.0


def _chat_completions_path(params: Mapping[str, Any]) -> str:
    raw = params.get("chat_completions_path")
    if raw is None:
        raw = params.get("api_path")
    if isinstance(raw, str) and raw.strip():
        p = raw.strip()
        return p if p.startswith("/") else f"/{p}"
    return "/v1/chat/completions"


def _resolve_api_model_name(params: Mapping[str, Any]) -> str:
    m = params.get("model")
    if isinstance(m, str) and m.strip():
        return m.strip()
    mid = params.get("model_id")
    if isinstance(mid, str) and mid.strip():
        s = mid.strip()
        if "/" in s:
            _, _, rest = s.partition("/")
            return (rest.strip() or s.strip())
        return s
    return "gpt-4o-mini"


def _resolve_base_url_and_vendor(
    params: Mapping[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """
    返回 (base_url, vendor_hint, error)。
    vendor_hint 仅作观测/文档；error 非空时应中止请求。
    """
    explicit = params.get("base_url")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().rstrip("/"), None, None

    mid = params.get("model_id")
    if isinstance(mid, str) and mid.strip() and "/" in mid:
        vendor = mid.strip().split("/", 1)[0].strip().lower()
        base = _VENDOR_DEFAULT_BASE_URL.get(vendor)
        if base:
            return base.rstrip("/"), vendor, None
        return (
            None,
            vendor,
            f"model_id 使用未知厂商前缀 {vendor!r}，请在 params 中设置 base_url（或改用已支持前缀："
            f"{', '.join(sorted(_VENDOR_DEFAULT_BASE_URL.keys()))}）。",
        )

    return "https://api.openai.com", None, None


def _api_key_env(params: Mapping[str, Any]) -> str | None:
    raw = params.get("api_key_env")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def build_openai_chat_route(provider: ModelProvider) -> OpenAiRouteResolution:
    params = provider.params
    env_name = _api_key_env(params)
    if not env_name:
        return OpenAiRouteResolution(
            route=None,
            error_message=(
                f"模型 [{provider.id}] 未配置 api_key_env：请在 model_providers.yaml 的 params 中设置 "
                "api_key_env（环境变量名），并在运行环境中导出对应 API Key。"
            ),
        )

    base_url, vendor, err = _resolve_base_url_and_vendor(params)
    if err or not base_url:
        return OpenAiRouteResolution(route=None, error_message=err or "无法解析 base_url")

    model = _resolve_api_model_name(params)
    route = OpenAiChatRoute(
        provider_id=provider.id,
        api_key_env=env_name,
        base_url=base_url,
        chat_completions_path=_chat_completions_path(params),
        model=model,
        timeout_seconds=_timeout_seconds(params),
        http_disable_connection_pool=_boolish(params, "http_disable_connection_pool"),
        vendor_hint=vendor,
    )
    return OpenAiRouteResolution(route=route, error_message=None)


_route_lock = threading.Lock()
_route_cache: dict[tuple[str, str], OpenAiChatRoute] = {}


def get_openai_chat_route(provider: ModelProvider) -> OpenAiRouteResolution:
    """
    带轻量缓存：同一 provider id + params 快照不变时复用解析结果（避免每轮请求重复拼 URL/模型名）。
    配置热更新需重启进程或变更 params 键值以失效缓存。
    """
    sig = json.dumps(dict(provider.params), sort_keys=True, default=str)
    key = (provider.id, sig)
    with _route_lock:
        hit = _route_cache.get(key)
        if hit is not None:
            return OpenAiRouteResolution(route=hit, error_message=None)

    res = build_openai_chat_route(provider)
    if res.route is not None:
        with _route_lock:
            _route_cache[key] = res.route
    return res


def clear_openai_chat_route_cache() -> None:
    """单测或动态改参后清空缓存。"""
    with _route_lock:
        _route_cache.clear()
