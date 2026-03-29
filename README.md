# Pompeii-Agent

> 面向 AI 应用的微内核式 Agent 运行时框架

**版本:** 0.5.4 | **Python:** >= 3.11

---

## 什么是 Pompeii-Agent

Pompeii-Agent 是一个基于**微内核架构**的通用 Agent 运行时框架。它将 Agent 的核心能力（会话管理、模型调用、工具执行、记忆系统）抽象为独立模块，通过**端口层（Port）** 与外部环境（CLI / HTTP / WebSocket）解耦，允许开发者在不改动内核的前提下自由替换交互渠道和扩展功能。

**设计原则：**
- **零内部泄露**：`pompeii_agent` 是唯一公共接口，无需记忆任何 `core.*`、`modules.*` 或 `app.*` 路径
- **全编程式装配**：全部配置通过 Python Builder 链式 API 完成，无需手工编写 YAML
- **可插拔扩展**：工具（MCP）、模型后端、记忆存储、会话持久化均可按需替换

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **多模型路由** | 内置 stub / OpenAI-compatible 模型后端，支持 failover 链 |
| **工具子系统** | 本地工具注册 + MCP（Stdio/HTTP）桥接 + 设备后端抽象 |
| **工具网络策略** | HTTP URL 白名单、内容类型过滤、MCP 工具白名单 |
| **记忆系统** | SQLite 双存储（短期 + 长期）+ RRF 混合检索 + OpenAI 兼容嵌入 |
| **会话管理** | 有状态会话，支持消息归档、LLM 摘要、多会话并行 |
| **安全策略** | 输入限流、Guard 模型过滤、工具风险分级、输出注入防护 |
| **端口抽象** | CLI / HTTP / WebSocket 三种交互模式，任意切换 |
| **流式输出** | OpenAI SSE 兼容流式推理，支持 delta 回调 |
| **资源访问控制** | 细粒度 read/write 权限，支持审批流程 |

---

## 安装

```bash
pip install pompeii-agent
```

**依赖：** PyYAML, fastapi, uvicorn, httpx, mcp, tiktoken

**开发安装：**

```bash
pip install "pompeii-agent[dev]"
pytest   # 运行测试
```

**或从源码安装：**

```bash
git clone <repo-url>
cd Pompeii-Agent
pip install -e .
```

---

## 快速开始

### 5 分钟上手

```python
from pompeii_agent import (
    AgentBuilder,
    ModelRegistryBuilder,
    ModelProviderBuilder,
    invoke_kernel,
)

# ── 1. 构建 Agent ───────────────────────────────────────────
kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"])
    .kernel(
        core_max_loops=8,
        tool_allowlist=["echo", "calc", "now"],
    )
    .build()
)

# ── 2. 单次对话（内置 echo 工具演示）────────────────────────
resp = invoke_kernel(
    kernel,
    user_id="user-001",
    channel="quickstart",
    text="Hello, how are you?",
)
print(resp.reply_text)
# → "Hello! I'm doing well..."
```

### 带 MCP 工具的完整示例

```python
from pompeii_agent import (
    AgentBuilder,
    ModelRegistryBuilder,
    ModelProviderBuilder,
    McpStdioBridge,
    McpServerEntry,
    invoke_kernel,
)

registry = (
    ModelRegistryBuilder(default_provider="my-model")
    .add(ModelProviderBuilder("my-model", "openai_compatible")
        .api_base_url("https://api.openai.com/v1")
        .model_name("gpt-4o-mini")
        .api_key_env("OPENAI_API_KEY"))
    .build()
)

# MCP 服务器桥接
mcp_bridge = McpStdioBridge(server=McpServerEntry(
    id="my-mcp-server",
    command="python",
    args=["-m", "my_mcp_server_package"],
))

kernel = (
    AgentBuilder()
    .session(model="my-model", skills=["weather", "search"])
    .kernel(
        core_max_loops=12,
        tool_allowlist=["weather", "search", "echo", "calc"],
    )
    .tool()
        .mcp_bridge(mcp_bridge)
        .register_handler("echo", lambda s, tc: {"echo": tc.arguments})
    .done()
    .model_registry(registry)
    .build()
)

resp = invoke_kernel(kernel, user_id="u1", channel="web", text="What's the weather in Shanghai?")
print(resp.reply_text)
```

### 启用记忆系统

```python
from pompeii_agent import AgentBuilder, invoke_kernel

kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"])
    .kernel(core_max_loops=8, tool_allowlist=["echo", "search_memory"])
    .memory()
        .enable()
        .retrieve_top_k(6)
        .embedding_dim(64)
    .done()
    .build()
)

# 第一轮：触发 /remember
invoke_kernel(kernel, user_id="u1", channel="c1",
    text="/remember 我的名字是张三")

# 第二轮：查询记忆
resp = invoke_kernel(kernel, user_id="u1", channel="c1",
    text="搜索我记住的信息")
```

### HTTP 服务

```python
from pompeii_agent import (
    create_http_service,
    ModelRegistryBuilder,
    ModelProviderBuilder,
    AgentBuilder,
)
import uvicorn

registry = ModelRegistryBuilder(default_provider="stub").build()
kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()

service = create_http_service(kernel=kernel)
# POST /chat   {"user_id":"u1","channel":"c1","text":"Hello"}
# GET  /health
uvicorn.run(service.app, host="0.0.0.0", port=8000)
```

### CLI 交互

```bash
pip install pompeii-agent
pompeii-cli

# 输入: 你好
# 输入: /help        # 查看系统指令
# 输入: /summary     # 总结当前会话
# 输入: /archive      # 归档会话
# 输入: exit
```

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                        用户 / 客户端                        │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP / CLI / WebSocket
┌─────────────────────▼───────────────────────────────────┐
│              Port 层（交互渠道抽象）                        │
│   GenericAgentPort · CliEmitter · HttpEmitter · WsMode   │
└─────────────────────┬───────────────────────────────────┘
                      │ AgentRequest / AgentResponse / PortEvent
┌─────────────────────▼───────────────────────────────────┐
│                  Pompeii-Agent 内核                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐  │
│  │ Assembly │  │  Model   │  │  Tools   │  │Memory │  │
│  │  Module  │  │  Module  │  │  Module  │  │Orchest.│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────┘  │
│  ┌──────────────────────────────────────────────────┐    │
│  │   Session Manager · Loop Policy · Guard 策略      │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 公共 API 一览

全部从 `pompeii_agent` 导入，无需接触任何内部路径：

| 模块 | 主要符号 |
|------|---------|
| **装配** | `AgentBuilder`, `create_kernel`, `create_http_service`, `create_interactive_port`, `invoke_kernel` |
| **工具** | `ToolBuilder`, `ToolModuleImpl`, `ToolHandler`, `echo_handler`, `calc_handler`, `now_handler`, `make_http_get_handler` |
| **模型** | `ModelRegistryBuilder`, `ModelProviderBuilder` |
| **会话** | `SessionBuilder`, `SessionLimitsBuilder`, `MemoryBuilder` |
| **安全** | `SecurityBuilder`, `ResourceAccessBuilder` |
| **MCP** | `McpStdioBridge`, `McpHttpBridge`, `McpMultiStdioBridge`, `resolve_mcp_bridge` |
| **设备后端** | `LocalSimulatorBackend`, `CompositeDeviceBackend`, `NoopDeviceBackend`, `build_device_backend` |
| **类型** | `AgentCoreImpl`, `AgentRequest`, `AgentResponse`, `ToolCall`, `ToolResult`, `Session`, `UserIntent` |
| **Port** | `CliMode`, `HttpEmitter`, `parse_user_intent`, `PortEvent` |
| **配置** | `ConfigProvider`, `session_provider_from_yaml`, `bundled_config_dir` |

完整导出列表见 `pompeii_agent.__all__`。

---

## 命令行工具

安装后自动注册三个可执行命令：

```bash
pompeii-cli              # 交互式 CLI 会话
pompeii-http             # HTTP/WS 服务（默认 8000 端口）
pompeii-resource-migrate # 资源数据迁移工具
```

---

## 许可

MIT License
