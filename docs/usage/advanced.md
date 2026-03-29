# 高级用法

## 什么时候使用 `advanced`

`pompeii_agent.advanced` 暴露底层完整能力，用于：

- 自定义 `AssemblyModule` 实现
- 自定义 `ModelModule` 实现
- 绕过 Builder，直接调用 `build_core`
- 注册表和策略的底层细节

日常使用推荐 `AgentBuilder`，advanced 仅在你需要深度定制时使用。

---

## 底层 API 一览

| 符号 | 说明 |
|------|------|
| `build_core(...)` | 直接构造 AgentCoreImpl，跳过 Builder |
| `build_port(...)` | 直接构造 GenericAgentPort |
| `build_http_agent_service(...)` | 直接构造 FastAPI app |
| `AgentCore` | 内核协议（Protocol） |
| `AgentCoreImpl` | 内核实现（与 build_core 等价） |
| `AssemblyModule` | 对话组装模块协议 |
| `ModelModule` | 模型调用模块协议 |
| `ToolModule` | 工具子系统模块协议 |

---

## build_core — 直接构造内核

```python
from pompeii_agent.advanced import (
    build_core,
    AssemblyModuleImpl,
    ModelModuleImpl,
    ToolModuleImpl,
    MemoryOrchestrator,
    SessionManagerImpl,
    ConfigProvider,
    KernelConfig,
)

kernel = build_core(
    config_provider=my_provider,
    model_registry=my_registry,
    assembly=my_assembly,
    tools=my_tools,
    memory_orchestrator=my_memory,
    src_root=root_path,
)
```

参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `config_provider` | `ConfigProvider` | 会话配置提供者 |
| `model_registry` | `ModelRegistry | None` | 模型注册表 |
| `assembly` | `AssemblyModule | None` | 自定义 Assembly 模块 |
| `tools` | `ToolModule | None` | 自定义工具模块 |
| `memory_orchestrator` | `MemoryOrchestrator | None` | 记忆编排器 |
| `src_root` | `Path | None` | 源码根路径 |

---

## 自定义 AssemblyModule

```python
from pompeii_agent.advanced import AssemblyModule, AssemblyModuleImpl
from core.memory.policy_config import MemoryPolicyConfig

class MyAssembly(AssemblyModule):
    """自定义对话组装逻辑"""
    def assemble(self, session, memory_context, tools_context):
        ...

my_assembly = MyAssembly(...)
kernel = build_core(config_provider=..., assembly=my_assembly)
```

---

## 自定义 ModelModule

```python
from pompeii_agent.advanced import ModelModule, ModelModuleImpl

class MyModel(ModelModule):
    def call(self, request, stream_delta=None):
        ...

my_model = MyModel(registry=my_registry)
kernel = build_core(config_provider=..., model=my_model)
```

---

## SessionManager — 手动管理会话

```python
from pompeii_agent.advanced import SessionManagerImpl

store = resolve_session_store("builtin:sqlite", sqlite_path="data/sessions.db")
manager = SessionManagerImpl(store)

# 创建会话
session = manager.create_session(user_id="u1", channel="web")

# 获取会话
sess = manager.get_session("sess-123")

# 归档会话
manager.archive_session("sess-123")

# 删除会话
manager.delete_session("sess-123")
```

---

## resolve_session_store — 会话存储

```python
from pompeii_agent.advanced import resolve_session_store

store = resolve_session_store(
    "builtin:sqlite",
    sqlite_path="data/sessions.db",
)
```

---

## 设备后端注册表

```python
from pompeii_agent.advanced import (
    resolve_device_backend,
    build_device_backend,
)

# 从 ref 字符串解析
backend = resolve_device_backend("builtin:simulator")

# 直接构建
backend = build_device_backend(
    refs=["builtin:simulator"],
    fallback_to_simulator=True,
)
```

内置 refs：

| ref | 说明 |
|-----|------|
| `builtin:noop` | 空实现 |
| `builtin:simulator` | 本地模拟设备 |
| 其他 | 用户自定义注册 |

---

## MCP 桥接器注册表

```python
from pompeii_agent.advanced import resolve_mcp_bridge

bridge = resolve_mcp_bridge(cfg=mcp_runtime_config, src_root=root)
```

---

## 配置加载器（底层）

```python
from pompeii_agent.advanced import (
    load_model_registry,
    load_session_config,
    load_kernel_config,
    load_security_policy_registry,
    load_mcp_config,
    load_skill_registry,
    ModelProviderSource,
    SessionConfigSource,
    KernelConfigSource,
    McpConfigSource,
    SkillRegistrySource,
)
```

示例：

```python
from pathlib import Path

root = Path("path/to/project")

reg = load_model_registry(
    ModelProviderSource(path=root / "config" / "model_providers.yaml")
)

cfg = load_kernel_config(
    KernelConfigSource(path=root / "config" / "kernel_config.yaml")
)
```

---

## 工具策略与循环策略

```python
from pompeii_agent.advanced import (
    resolve_tool_policy_decide,
    resolve_loop_governance_fn,
)

# 获取策略函数
tool_decide = resolve_tool_policy_decide("builtin:default")
loop_govern = resolve_loop_governance_fn("builtin:default")
```

---

## PromptCache — 提示词缓存

```python
from infra import PromptCache

cache = PromptCache()

# 读取缓存
cached = cache.get("prompt-key")

# 写入缓存
cache.set("prompt-key", "cached content")
```

---

## YAML 配置加载（作为 Builder 的替代）

框架提供独立 YAML 配置加载函数：

```python
from pompeii_agent import (
    bundled_config_dir,
    bundled_session_defaults_path,
    bundled_model_providers_path,
    load_session_config_yaml,
    load_model_registry_yaml,
    session_provider_from_yaml,
)

# 配置目录
cfg_dir = bundled_config_dir()
# → Path(".../platform_layer/resources/config")

# 从 YAML 加载
cfg = load_session_config_yaml("path/to/session_defaults.yaml")
registry = load_model_registry_yaml("path/to/model_providers.yaml")

# 构造 provider
provider = session_provider_from_yaml(
    "path/to/session_defaults.yaml",
    override_model="stub",
)

kernel = create_kernel(provider)
```
