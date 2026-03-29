# AgentBuilder 完整指南

`AgentBuilder` 是框架推荐的全编程式装配入口。通过链式调用替代所有 YAML 配置文件，一行 `.build()` 出完整的 `AgentCoreImpl`。

```python
from pompeii_agent import AgentBuilder

kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"])
    .kernel(core_max_loops=8, tool_allowlist=["echo", "calc"])
    .tool().register_handler("echo", my_handler).done()
    .memory().enable().retrieve_top_k(3).done()
    .security().enable_guard().done()
    .resource_access().deny("filesystem").done()
    .build()
)
```

---

## SessionBuilder — 会话配置

```python
.session(
    model="stub",                # 模型 ID（必须在 ModelRegistry 中注册）
    skills=["echo"],             # 激活的技能列表
    limits=None,                 # SessionLimitsBuilder 实例
    prompt_profile="default",     # 提示词模板 profile
    prompt_strategy="default",    # 提示策略
    security="baseline",          # 安全策略 ID
)
```

**链式方法：**

```python
AgentBuilder().session(model="stub", skills=["echo"])  # 基础

# 链式修改
s = AgentBuilder().session(model="stub", skills=["echo"])
s.model("gpt-4")                      # 换模型
s.skills(["echo", "weather"])         # 换技能
s.limits(SessionLimitsBuilder().max_tokens(50000))  # 换限制
```

---

## KernelBuilder — 内核循环配置

```python
.kernel(
    core_max_loops=8,                          # 最大循环次数
    max_tool_calls_per_run=8,                  # 每次运行最大工具调用数
    tool_allowlist=["echo", "calc"],          # 工具白名单（不在列表中不执行）
    tool_confirmation_required=[],             # 需要确认的工具
    context_isolation=True,                    # 开启上下文隔离
    tool_policy_engine_ref="builtin:default",  # 工具策略引擎
    loop_policy_engine_ref="builtin:default",  # 循环策略引擎
    prompt_strategy_ref="builtin:none",        # 提示策略
    archive_llm_summary_enabled=False,         # 归档时 LLM 摘要
    archive_llm_summary_provider_id="",        # 摘要用模型
    archive_llm_summary_max_dialogue_chars=12000,
    archive_llm_summary_max_output_chars=2000,
    archive_llm_summary_system_prompt="",
    delegate_target_allowlist=(),              # 允许的委派目标
)
```

**循环终止原因（`ResponseReason`）：**

| 原因 | 说明 |
|------|------|
| `ok` | 正常返回 |
| `max_loops` | 达到最大循环次数 |
| `max_tool_calls` | 达到最大工具调用数 |
| `repeated_tool_call` | 重复调用相同工具 |
| `tool_policy_denied` | 工具策略拒绝执行 |
| `confirmation_required` | 需用户确认 |
| `security_*` | 安全策略阻止 |
| `delegate` | 触发多 Agent 协作 |

---

## ToolBuilder — 工具子系统配置

### 方案 A：直接注册可调用对象（最简，推荐）

```python
from pompeii_agent import ToolBuilder, echo_handler, calc_handler

tb = (
    ToolBuilder()
    .register_handler("echo", echo_handler)    # Callable[[Session, ToolCall], ToolResult]
    .register_handler("calc", calc_handler)
)
```

`ToolHandler` 签名：

```python
ToolHandler = Callable[[Session, ToolCall], ToolResult]
```

### 方案 B：注册字符串引用（框架自动 import）

```python
tb = (
    ToolBuilder()
    .register("weather", "my_company.weather:weather_handler")
    .register("search", "my_company.search:search_handler")
)
```

格式：`"module.path:function_name"`

### 方案 C：注入完整 ToolModuleImpl（完全控制）

```python
from pompeii_agent import ToolModuleImpl, ToolNetworkPolicyConfig, LocalSimulatorBackend

my_tools = ToolModuleImpl(
    local_handlers={"my_tool": my_handler, "another": another_handler},
    device_routes={},
    mcp=my_mcp_bridge,
    network_policy=ToolNetworkPolicyConfig(
        enabled=False,
        http_url_guard_enabled=True,
        http_url_allowed_hosts=("localhost", "api.example.com"),
    ),
    device_backend=LocalSimulatorBackend(),
)

tb = ToolBuilder().tools_module(my_tools)
```

### 方案 D：只注入 MCP 桥接，其余走默认值

```python
from pompeii_agent import McpStdioBridge, McpServerEntry

bridge = McpStdioBridge(server=McpServerEntry(
    id="my-server",
    command="python",
    args=["-m", "my_mcp_server"],
))

tb = ToolBuilder().mcp_bridge(bridge)
```

### 工具网络策略

```python
from pompeii_agent import ToolNetworkPolicyConfig

policy = ToolNetworkPolicyConfig(
    enabled=True,                          # 开启工具网络限制
    deny_tool_names=("dangerous_tool",),   # 拒绝指定工具名
    http_url_guard_enabled=True,            # 开启 HTTP GET 工具的 URL 守卫
    http_url_allowed_hosts=("api.example.com",),
    http_blocked_content_type_prefixes=("application/octet-stream",),
    mcp_allowlist_enforced=True,          # MCP 工具白名单强制
    mcp_tool_allowlist=("weather", "search"),
)
```

### 设备路由

```python
from pompeii_agent import DeviceRoute

tb = (
    ToolBuilder()
    .device_route(
        tool="take_photo",
        device="camera",
        command="take_photo",
        quality="high",
    )
)
```

---

## MemoryBuilder — 记忆系统配置

```python
.memory()
    .enable()                                # 开启记忆（默认关闭）
    .disable()                               # 关闭
    .retrieve_top_k(6)                       # 每次检索返回的 top k 结果
    .embedding_dim(64)                        # 嵌入向量维度
    .use_openai_embedding(                    # 切换到 OpenAI 嵌入
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com",
        model="text-embedding-3-small",
    )
    .memory_db_path("path/to/memory.db")     # 自定义数据库路径
```

**构建 policy：**

```python
policy = MemoryBuilder().enable().retrieve_top_k(3).embedding_dim(64).build_policy()
```

---

## SecurityBuilder — 安全策略配置

```python
.security()
    .enable_guard(provider_id="my-model")   # 开启 Guard 模型过滤
    .tool_risk("low")                       # 全局工具风险等级
    .tool_risk_override("http_get", "high")  # 单独指定工具风险
```

内置安全策略 ID：`baseline`（默认）

---

## ResourceAccessBuilder — 资源访问控制

```python
.resource_access()
    .allow("long_term_memory", read=True, write=True)   # 允许读写
    .deny("filesystem", read=True, write=False)          # 只允许读
```

默认规则：

| 资源 | 默认读 | 默认写 |
|------|--------|--------|
| `long_term_memory` | allow | allow |
| `session_data` | allow | allow |
| `tool_execution` | allow | allow |
| `device_access` | allow | allow |
| `filesystem` | allow | **deny** |
| `external_api` | allow | **deny** |
| `multimodal_image_url` | allow | **deny** |
| `remote_retrieval` | allow | **deny** |

---

## RuntimeBuilder — 运行时配置

```python
.runtime()
    .sqlite_path("data/sessions.db")       # 会话持久化路径
    .memory_db_path("data/memory.db")      # 记忆数据库路径
```

---

## SessionLimitsBuilder — 会话预算配置

```python
from pompeii_agent import SessionBuilder, SessionLimitsBuilder

limits = (
    SessionLimitsBuilder()
    .max_tokens(100000)
    .max_context_window(128000)
    .max_loops(15)
    .timeout_seconds(300.0)
    .assembly_tail_messages(20)
    .summary_tail_messages(12)
    .summary_excerpt_chars(200)
)

kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"], limits=limits)
    .build()
)
```

---

## ModelRegistryBuilder — 模型注册表

### 添加 OpenAI 兼容模型

```python
from pompeii_agent import ModelRegistryBuilder, ModelProviderBuilder

registry = (
    ModelRegistryBuilder(default_provider="deepseek")
    .add(ModelProviderBuilder("deepseek", "openai_compatible")
        .api_base_url("https://api.deepseek.com")
        .model_name("deepseek-chat")
        .api_key_env("DEEPSEEK_API_KEY")
        .timeout(30.0)
        .failover_to("openai"))
    .add(ModelProviderBuilder("openai", "openai_compatible")
        .api_base_url("https://api.openai.com/v1")
        .model_name("gpt-4o-mini")
        .api_key_env("OPENAI_API_KEY"))
    .build()
)

kernel = AgentBuilder().model_registry(registry).build()
```

### 添加 stub 模型（测试用）

```python
registry = ModelRegistryBuilder(default_provider="stub").build()
```

---

## 完整示例

```python
from pompeii_agent import (
    AgentBuilder, ModelRegistryBuilder, ModelProviderBuilder,
    McpStdioBridge, McpServerEntry,
    invoke_kernel,
)

# ── 模型 ──────────────────────────────────────────────
registry = (
    ModelRegistryBuilder(default_provider="deepseek")
    .add(ModelProviderBuilder("deepseek", "openai_compatible")
        .api_base_url("https://api.deepseek.com")
        .model_name("deepseek-chat")
        .api_key_env("DEEPSEEK_API_KEY"))
    .build()
)

# ── MCP ──────────────────────────────────────────────
mcp_bridge = McpStdioBridge(server=McpServerEntry(
    id="demo-mcp",
    command="python",
    args=["-m", "demo_mcp_server"],
))

# ── Agent ─────────────────────────────────────────────
kernel = (
    AgentBuilder()
    .session(model="deepseek", skills=["echo", "weather"])
    .kernel(core_max_loops=12, tool_allowlist=["echo", "calc", "weather"])
    .memory().enable().retrieve_top_k(3).embedding_dim(64).done()
    .tool()
        .mcp_bridge(mcp_bridge)
        .allowlist_mcp_tools(["weather", "search"])
    .done()
    .resource_access().allow("filesystem", read=True, write=False).done()
    .model_registry(registry)
    .build()
)

# ── 调用 ──────────────────────────────────────────────
resp = invoke_kernel(kernel, user_id="u1", channel="web",
    text="上海今天天气怎么样？")
print(resp.reply_text)
```
