# Getting Started

## 安装

```bash
pip install pompeii-agent
```

或从源码安装：

```bash
git clone <repo-url>
cd Pompeii-Agent
pip install -e .
```

**依赖：** PyYAML >= 6.0, fastapi >= 0.110, uvicorn[standard] >= 0.27, httpx >= 0.27, mcp >= 1.2.0, tiktoken >= 0.5.0

**Python 版本：** >= 3.11

---

## 项目结构

```
pompeii-agent/
├── src/
│   ├── pompeii_agent/          ← 唯一公共接口（勿 import 内部模块）
│   │   ├── __init__.py        ← 公共 API 全部导出
│   │   ├── facade.py          ← 推荐高层 API（create_kernel / invoke_kernel）
│   │   ├── builders.py        ← 链式 Builder 装配
│   │   ├── config.py          ← 配置加载工具
│   │   └── advanced.py        ← 底层完整开放能力
│   ├── app/                   ← 应用层（配置加载、注册中心、运行时）
│   ├── core/                  ← 核心域（AgentCore、会话、记忆、策略）
│   ├── modules/               ← 领域模块（Assembly / Model / Tools）
│   ├── port/                  ← 端口抽象（CLI / HTTP / WebSocket）
│   ├── infra/                 ← 基础设施（MCP Bridge / SQLite / PromptCache）
│   └── platform_layer/        ← 随包资源（YAML 默认配置）
├── pyproject.toml
└── README.md
```

---

## 核心概念

### Pompeii-Agent 微内核

```
用户/客户端
    │
    ▼
Port 层（CLI / HTTP / WebSocket）
    │  AgentRequest / PortEvent
    ▼
Pompeii-Agent 内核（AgentCoreImpl）
  ├── AssemblyModule      ← 消息裁剪、上下文隔离、token 预算
  ├── ModelModule        ← 模型调用、流式推理、工具解析
  ├── ToolModule         ← 本地工具、MCP 桥接、设备后端
  ├── MemoryOrchestrator ← 长期 + 短期记忆混合检索
  ├── SessionManager      ← 有状态会话、消息历史
  └── Security / Guard   ← 输入限流、工具风险、输出防护
```

### 三大核心对象

| 对象 | 说明 |
|------|------|
| `AgentCoreImpl` | Agent 微内核实例，由 `AgentBuilder.build()` 产生 |
| `GenericAgentPort` | 交互端口，连接内核与外部（CLI/HTTP/WS） |
| `AgentResponse` | 内核处理结果，含 `reply_text`、`tool_calls`、`reason` 等 |

### 用户意图（UserIntent）

外部输入经 `parse_user_intent()` 在 Port 层解析为结构化 `UserIntent`，内核只消费 intent，不再判断原始字符串：

| Intent | 触发条件 |
|--------|---------|
| `Chat(text)` | 普通对话 |
| `SystemHelp()` | `/help` |
| `SystemSummary()` | `/summary` |
| `SystemArchive()` | `/archive` |
| `SystemRemember(text)` | `/remember <内容>` |
| `SystemForget(phrase)` | `/forget <短语>` |
| `SystemPreference(action, ...)` | `/preference ...` |
| `SystemFact(action, ...)` | `/fact ...` |
| `SystemDelegate(target, payload)` | 跨 Agent 协作 |

---

## 第一个 Agent

### 方式一：`AgentBuilder`（推荐，完全编程式）

```python
from pompeii_agent import AgentBuilder, invoke_kernel

kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"])
    .kernel(core_max_loops=8, tool_allowlist=["echo"])
    .build()
)

resp = invoke_kernel(kernel, user_id="u1", channel="c1", text="Hello")
print(resp.reply_text)
```

### 方式二：`create_kernel`（从 YAML 配置）

```python
from pompeii_agent import create_kernel, session_provider_from_yaml

provider = session_provider_from_yaml(
    "path/to/session_defaults.yaml",
    override_model="stub",
)
kernel = create_kernel(provider)
```

### 方式三：HTTP 服务

```python
from pompeii_agent import create_http_service, AgentBuilder
import uvicorn

kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
service = create_http_service(kernel=kernel)
uvicorn.run(service.app, port=8000)
# POST /chat  {"user_id":"u1","channel":"c1","text":"Hello"}
```

---

## 内置工具一览

框架默认注册三个内置工具，无需任何配置即可使用：

| 工具名 | 参数 | 说明 |
|--------|------|------|
| `echo` | `text` | 回显输入，返回 session_id |
| `calc` | `expression` | 安全数学计算（+ - * / // % **），支持 AST 解析 |
| `now` | — | 返回当前 UTC 时间戳和 ISO 格式时间 |

使用示例：

```python
resp = invoke_kernel(kernel, user_id="u1", channel="c1",
    text="用 calc 工具帮我算 2**10")
resp = invoke_kernel(kernel, user_id="u1", channel="c1",
    text="现在几点了？")
```

---

## 系统指令

在 CLI 或 HTTP 接口中可直接使用以下指令：

| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/summary` | 总结当前会话内容 |
| `/archive` | 将会话标记为已归档 |
| `/remember <内容>` | 写入长期记忆 |
| `/forget <短语>` | 从长期记忆中删除 |
| `/preference list` | 列出用户偏好 |
| `/preference set <key>=<value>` | 设置偏好 |
| `/fact add <陈述>` | 添加事实记录 |
| `/fact list` | 列出已记录的事实 |
| `exit` / `quit` | 退出 CLI |

---

## 下一步

- [AgentBuilder 完整指南](./agent-builder.md) — 深入了解所有 Builder 的配置选项
- [工具子系统](./tool-system.md) — 注册自定义工具、配置网络策略
- [MCP 集成](./mcp-integration.md) — 接入 MCP 服务器
- [记忆系统](./memory-system.md) — 启用混合检索记忆
- [端口层](./port-layer.md) — 理解 Port 抽象与事件体系
