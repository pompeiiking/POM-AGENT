# 安全策略

## 概览

安全体系分为三层：

```
输入
  │
  ▼
1. 输入安全（InputGuard）
  │   • 字符长度限制（input_max_chars）
  │   • 限流（max_requests_per_minute）
  │   • Guard 模型过滤（可选）
  │
  ▼
2. 工具执行安全（ToolPolicy）
  │   • 工具风险分级（low/medium/high）
  │   • 确认机制（tool_confirmation_required）
  │
  ▼
3. 输出安全（OutputGuard）
      • 注入防护（HTML/JS 过滤）
      • 输出长度限制（按信任级别）
      • Guard 模型过滤（可选）
```

---

## SecurityBuilder — 安全策略配置

```python
from pompeii_agent import SecurityBuilder

sb = (
    SecurityBuilder()
    .enable_guard(provider_id="my-guard-model")
    .tool_risk("low")
    .tool_risk_override("http_get", "high")
)
```

### 内置安全策略 ID

| ID | 说明 |
|----|------|
| `baseline` | 默认策略（框架内置） |

---

## 输入安全

### 字符长度限制

```python
SecurityBuilder(
    policy_id="strict",
    input_max_chars=12000,   # 默认 12000
)
```

### 限流

```python
SecurityBuilder(
    policy_id="strict",
    max_requests_per_minute=60,  # 默认 60
)
```

---

## 工具安全

### 风险分级

```python
SecurityBuilder(
    policy_id="strict",
    default_tool_risk_level="low",  # 默认 "low"
    tool_confirmation_level="high", # 需要确认的级别
)
```

风险级别：`low` / `medium` / `high`

### 单独指定工具风险

```python
SecurityBuilder().tool_risk_override("http_get", "high")
SecurityBuilder().tool_risk_override("echo", "low")
```

### 需要确认的工具

```python
.kernel(tool_confirmation_required=["http_get", "shell"])
```

触发确认时，Agent 返回 `ResponseReason.CONFIRMATION_REQUIRED`，`ConfirmationEvent` 发送确认请求，用户输入 `yes`/`no` 继续或拒绝。

---

## Guard 模型过滤

Guard 模型用于在输入进入 Agent 前/输出离开 Agent 后进行内容安全检测：

```python
from pompeii_agent import SecurityBuilder, ModelRegistryBuilder, ModelProviderBuilder

registry = (
    ModelRegistryBuilder(default_provider="gpt-4")
    .add(ModelProviderBuilder("gpt-4", "openai_compatible")
        .api_base_url("https://api.openai.com/v1")
        .model_name("gpt-4o-mini")
        .api_key_env("OPENAI_API_KEY"))
    .build()
)

sb = (
    SecurityBuilder()
    .enable_guard(provider_id="gpt-4")   # 指定 guard 用模型
)
```

Guard 配置项：

```python
SecurityBuilder(
    guard_enabled=True,
    guard_evaluator_ref="builtin:default",
    guard_model_ref="builtin:default",     # 或 "builtin:none" 关闭
    guard_model_provider_id="my-model",
    guard_block_patterns=["<script>", "javascript:"],  # 内置正则阻止
    guard_tool_output_redaction="[guard_blocked]",
)
```

---

## 输出安全

### 输出注入防护

```python
SecurityBuilder(
    tool_output_injection_patterns=["<!-- pompeii:zone-end", "<!-- pompeii:zone-begin"],
    tool_output_injection_redaction="[tool_output_injection_blocked]",
)
```

### 按信任级别的输出长度限制

```python
SecurityBuilder(
    tool_output_max_chars_by_trust={
        "high": 0,      # 0 = 无限制
        "medium": 50000,
        "low": 1024,
    },
    default_tool_output_trust="high",
)
```

### 工具输出信任覆盖

```python
SecurityBuilder(
    tool_output_trust_overrides={
        "echo": "high",
        "http_get": "low",
    },
    mcp_tool_output_trust="low",         # MCP 工具默认 "low"
    device_tool_output_trust="low",       # 设备工具默认 "low"
    http_fetch_tool_output_trust="low",  # HTTP GET 默认 "low"
)
```

---

## 资源访问控制（ResourceAccessBuilder）

```python
from pompeii_agent import ResourceAccessBuilder

kernel = (
    AgentBuilder()
    .resource_access()
        .allow("long_term_memory", read=True, write=True)
        .allow("session_data", read=True, write=True)
        .deny("filesystem", read=True, write=False)   # 只读
        .deny("external_api", read=False, write=True)  # 不允许
    .done()
    .build()
)
```

**权限规则：**

| 权限值 | 说明 |
|--------|------|
| `allow` | 允许 |
| `deny` | 拒绝 |
| `"allow"` + `read_requires_approval=True` | 需审批才能读 |
| `"allow"` + `write_requires_approval=True` | 需审批才能写 |

### 自定义规则

```python
ResourceAccessBuilder()._rule(
    "my_resource",
    read="allow",
    write="allow",
    read_req=True,    # 读需要审批
    write_req=False,
)
```

---

## 完整安全配置示例

```python
from pompeii_agent import (
    AgentBuilder,
    SecurityBuilder,
    ResourceAccessBuilder,
    ModelRegistryBuilder,
    ModelProviderBuilder,
)

guard_registry = (
    ModelRegistryBuilder(default_provider="guard-model")
    .add(ModelProviderBuilder("guard-model", "openai_compatible")
        .api_base_url("https://api.openai.com/v1")
        .model_name("gpt-4o-mini")
        .api_key_env("OPENAI_API_KEY"))
    .build()
)

kernel = (
    AgentBuilder()
    .session(model="my-model", skills=["echo", "weather"])
    .kernel(
        core_max_loops=12,
        tool_allowlist=["echo", "weather", "calc"],
        tool_confirmation_required=["http_get", "external_api"],
    )
    .security()
        .enable_guard(provider_id="guard-model")
        .tool_risk("low")
        .tool_risk_override("http_get", "high")
        .tool_output_trust_overrides={"echo": "high", "http_get": "low"}
    .done()
    .resource_access()
        .allow("long_term_memory")
        .allow("session_data")
        .deny("filesystem")
        .deny("external_api")
    .done()
    .model_registry(guard_registry)
    .build()
)
```
