# Pompeii-Agent

**Microkernel-style agent runtime in Python — clear layers, pluggable modules, production-minded guardrails.**

Pompeii-Agent 是一套面向**长期演进**的 **Agent 基础设施**：用 **微内核 + 三处理模块（组装 / 模型 / 工具）** 组织运行时，以 **AgentPort** 作为对外唯一边界，配合声明式配置与可替换的存储、模型、MCP 与安全策略，适合作为自建对话智能体、内部 Copilot 或网关后端的**核心引擎**。

**当前版本**：见 [`src/app/version.py`](src/app/version.py)（HTTP `GET /health` 同步返回 `version`）。

---

## 为什么选择 Pompeii-Agent

| 维度 | 说明 |
|------|------|
| **边界清晰** | `port`（协议）→ `core`（编排）→ `modules`（能力）→ `app`（装配）→ `infra`（实现），避免「一把梭」式脚本 |
| **配置驱动** | 模型提供方、工具、技能、内核治理、记忆策略等多由 YAML 描述；密钥只走环境变量 |
| **安全分层** | 五道关卡（入口、上下文隔离、工具门、执行与净化、资源访问）在架构书与代码中有对应落点 |
| **可观测闭环** | Loop 治理（循环上限、工具预算、重复 `tool_call` 检测等）+ 归档与可选长期记忆 |

**非目标（当前主线）**：本仓库优先把 **单进程内闭环** 做稳；多租户 SaaS 控制台、完整 WS 网关、远程向量集群等放在契约稳定后再扩展（见 [`docs/design/STATUS.md`](docs/design/STATUS.md)）。

---

## 核心特性

- **微内核 Loop**：文本回复与 `tool_call` 交替；确认流、设备请求、`/delegate` 等经 Port 事件表达。
- **OpenAI 兼容 Chat**：**声明式路由**（`base_url` / `model` / `model_id` 前缀推断等），便于对接多家兼容 API，**不依赖**第三方 LLM 网关库。
- **会话持久化**：默认 SQLite `SessionStore`；支持归档摘要与可选异步 LLM 摘要。
- **长期记忆（双库思路）**：`MemoryOrchestrator` + SQLite 标准主数据与向量投影、RRF 等；组装路径注入 + `search_memory` 工具。
- **工具生态**：本地 handler、entrypoint 发现、可选 **MCP stdio**；网络策略与资源守门与配置联动。
- **测试**：`pytest` 覆盖核心策略与模块（建议 PR 前本地全量跑通）。

---

## 架构一览

**依赖方向（纯文本，任意阅读器均可看）**：

```
外部 HTTP/CLI → app/http_runtime|cli_runtime → port/GenericAgentPort
              → core/AgentCoreImpl ⇄ modules/{assembly, model, tools}
              → infra（SQLite · httpx · MCP …）

启动：platform_layer/*.yaml → app/config_loaders → app/*_registry → app/composition → 上述实例
```

| 层 | 路径 | 作用 |
|----|------|------|
| app | `src/app` | HTTP/CLI 入口、YAML 加载、装配 `AgentCore` + `Port` |
| port | `src/port` | 唯一边界：`handle` / `emit` |
| core | `src/core` | 会话、`_run_loop`、策略与守门 |
| modules | `src/modules/*` | 组装上下文、模型推理、工具执行 |
| infra / platform | `src/infra`、`src/platform_layer` | 存储、出网、静态配置 |

更完整的设计说明见 **[架构设计 ver0.6](docs/design/架构设计ver0.5.md)**（表格化运转流程、双库记忆子系统§9、系统接口清单§12）；条文级五关卡原文见 [ver0.4 归档](docs/design/archive/架构设计ver0.4.md)。

---

## 技术栈

- **语言**：Python 3（具体下限见 `requirements.txt` / 团队约定）
- **HTTP**：`httpx` 等；运行时入口 `app.http_runtime`
- **存储**：默认 SQLite（会话、归档、长期记忆表等）
- **配置**：`platform_layer/resources/config/*.yaml` + `app/config_loaders`

---

## 文档导航（GitHub 上建议从这里深入）

| 文档 | 内容 |
|------|------|
| [docs/README.md](docs/README.md) | 文档总索引 |
| [docs/design/INDEX.md](docs/design/INDEX.md) | 设计文档目录 |
| [docs/design/架构设计ver0.5.md](docs/design/架构设计ver0.5.md) | **当前架构主文档（ver0.6）**；含接口清单、记忆子系统 |
| [docs/design/STATUS.md](docs/design/STATUS.md) | 快照、STUB、优先级 |
| [docs/design/CHANGELOG.md](docs/design/CHANGELOG.md) | 主变更日志 |
| [docs/design/ai-rules-template/RULES.md](docs/design/ai-rules-template/RULES.md) | 协作与代码规范 |
| [docs/guides/系统测试流程.md](docs/guides/系统测试流程.md) | 系统测试 |
| [docs/guides/API密钥配置操作手册.md](docs/guides/API密钥配置操作手册.md) | API Key 配置 |

---

## 以库方式安装（可选）

在仓库根目录：

```powershell
pip install -e .
```

安装后可直接 `import core`、`import app` 等（包 discovery 自 `src/`）。**最小闭环示例**（**stub** 模型，无需 API Key；须在仓库根执行以便读取 `src/platform_layer/...` 配置）：

```powershell
python examples/minimal_kernel.py
```

---

## 快速启动（HTTP，对接用）

在 PowerShell 中，若已在**仓库根目录**创建本地 **`env.ps1`**（已加入 `.gitignore`，勿提交），`run-http` / `run-cli` 会自动加载并注入 `DEEPSEEK_API_KEY`。也可在系统中直接设置环境变量 `DEEPSEEK_API_KEY`。若提示「禁止运行脚本」，请用 **`run-http.cmd`**（不依赖执行策略）：

```powershell
cd C:\Users\22271\Desktop\Agent
.\scripts\run-http.cmd
```

或：

```powershell
cd C:\Users\22271\Desktop\Agent
.\scripts\run-http.ps1
```

或手动：

```powershell
cd C:\Users\22271\Desktop\Agent
$env:PYTHONPATH="src"
python -m app.http_runtime
```

启动后访问：

- `GET /health`
- `POST /input`（返回 `events` 列表，作为实验性对接的“数据流串联”输出；含 `policy_notice` 等事件）
- `WS /ws`（每条入站 JSON 与 `/input` 同构；每条出站为 `{"events":[...]}`）
- `GET /archives?user_id=...`（会话归档摘要列表；依赖 SQLite `session_archives` 表，见 `runtime.yaml` 与 `docs/design/架构设计ver0.5.md` §12）

示例：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/input -ContentType "application/json" -Body '{"kind":"user_message","user_id":"u1","channel":"http","text":"hi"}'
```

### CLI（保留，用于本地交互调试）

```powershell
cd C:\Users\22271\Desktop\Agent
.\scripts\run-cli.cmd
```

### CLI 试运行指令

- 普通输入：`hi`
- 触发工具调用：`/tool echo hello`
  - 若 `kernel_config.yaml` 将该工具标记为需要确认，会先出现确认事件：
    - 输入 `yes/no`
    - 或使用：`/confirm <id> yes|no`
- 触发设备请求：`/tool take_photo`
  - 确认通过后会 emit `device_request`，按提示使用 `/device_result {...}` 回传 JSON

## 目录结构（概览）

> 以 `src/` 为代码根目录。文档见 `docs/`（`README.md` 索引）。API Key 仅通过本机环境变量或根目录 `env.ps1` 加载，**不在仓库中提供示例密钥文件**。

```
src/
  app/        # 应用运行时 + 装配层（组合根）
  port/       # 唯一边界：handle + emit，交互模式与事件协议
  core/       # 微内核：会话 + loop 编排 + 安全门（不依赖 app/port）
  modules/    # 处理模块：assembly / model / tools
  platform_layer/   # 静态配置与本地数据路径（如会话库）
  infra/      # 基础设施实现（如 SQLite 会话存储）
```

## 配置（长期保存）

### 运行时（会话存储）

文件：`src/platform_layer/resources/config/runtime.yaml`

- `session_store.backend`：仅 **`sqlite`**（会话落盘，路径见 `sqlite_path`；进程重启后同一 `user_id`+`channel` 可恢复对话）。测试可使用 `SqliteSessionStore.ephemeral()`（`:memory:`）。
- `session_store.sqlite_path`：相对路径时相对于 `src/` 目录；默认 `platform_layer/resources/data/sessions.db`（已将 `*.db` 加入 `.gitignore`）。
- `port.pending_state_backend`：`memory`（默认）或 `sqlite_shared`；后者会把待确认/待设备状态写入 `port.pending_state_sqlite_path`，用于多 worker 共享。

### 内核长期配置（KernelConfig）

文件：`src/platform_layer/resources/config/kernel_config.yaml`

- `core_max_loops`：内核全局 loop 上限（与会话级 `SessionConfig.limits.max_loops` 取 min）
- `max_tool_calls_per_run`：单次 run 内允许的工具调用次数上限
- `tool_allowlist`：允许的工具名列表
- `tool_confirmation_required`：需要人工确认的工具名列表

### 会话配置（SessionConfig）

文件：`src/platform_layer/resources/config/session_defaults.yaml`

由 `ConfigProvider(user_id, channel)` 读取并注入到 core，用于创建/管理 session。
- `session.prompt_profile`：提示词档位（默认 `default`），用于选择 `model_providers.yaml` 中 `params.prompt_profiles` 的模板。
- `session.prompt_strategy`：提示词策略（默认 `default`），用于在 `prompt_profile` 下选择子策略模板（如 `concise`、`tool_first`）。

### MCP（可选，stdio）

文件：`src/platform_layer/resources/config/mcp_servers.yaml`

- 默认 **`enabled: true`**（便于本地 `/tool ping`、`/tool add` 演示）；不需要 MCP 时在 YAML 中改为 **`false`** 并重启。需已 `pip install` 本仓库 `requirements.txt` 中的 `mcp`。
- `bridge_ref` 支持 `builtin:stdio`（默认）与 `builtin:http_json`（通过 `http_servers` 调用 `POST {base_url}/tools/call`）。
- 仅允许在该 YAML 中声明 **`command` / `args` / `env`**，勿将用户输入拼入进程参数；生产选型请优先 [MCP Registry](https://modelcontextprotocol.io/registry) 与已审计清单。
- 仓库自带演示：`infra/mcp_demo_server.py`（工具名 `ping`、`add`），需在 `kernel_config.yaml` 的 `tool_allowlist` 中放行（默认已包含演示名）。

### 工具注册配置（ToolRegistry）

文件：`src/platform_layer/resources/config/tools.yaml`

- **`tools.local_handlers`**：本地工具注册表（`tool_name -> "module.path:function_name"`），启动时动态加载。
- **`tools.device_routes`**：设备工具路由声明（`tool/device/command/fixed_parameters`），命中后走 device_request 流程。
- **`tools.enable_entrypoints` / `tools.entrypoint_group`**：启用 Python entry_points 自动发现，支持安装插件包后自动注册工具（显式配置同名优先）。
- 通过该文件可新增或替换本地/设备工具，无需修改 core 编排代码；`ToolModuleImpl` 仅负责按注册结果分发执行。

### 模型配置（ModelRegistry）

文件：`src/platform_layer/resources/config/model_providers.yaml`

- **`default_provider`**：与会话 `session.model` 无法匹配任一 id 时使用的回退 provider。
- **`providers.<id>`**：每个 **id** 即工程内可引用的提供方名称；`session_defaults.yaml` 里的 **`session.model`** 填这里的 id，即可切换不同 API/模型。
- **`backend`**：`stub`（占位）或 `openai_compatible`（以及兼容的 `deepseek` 别名），统一走 OpenAI Chat Completions 协议。
- **`params.api_key_env`**：声明该 provider 使用的 **环境变量名**（不要在文件里写 Key）；未设置 `api_key_env` 的 legacy `deepseek` backend 仍默认读 `DEEPSEEK_API_KEY`。
- **声明式路由**：可选 `model`、`model_id`（如 `deepseek/deepseek-chat`）、`base_url`、`chat_completions_path`、`extra_headers` 等；详见文件顶部注释与 `modules/model/openai_provider_route.py`。
- 仅承载 provider 连接参数；提示词与回流策略字段在 `prompts.yaml`（启动时按 provider id 合并注入）。
- 由 `load_model_registry` 加载，在 `composition.build_core` / `http_runtime` 中注入 `ModelModuleImpl`。

### 提示词配置（PromptRegistry）

文件：`src/platform_layer/resources/config/prompts.yaml`

- **`prompts.providers.<id>.prompt_profiles`**：system prompt 分层模板（`profile -> strategy`）。
- **`prompts.providers.<id>.prompt_vars` / `prompt_vars_env`**：system 模板变量注入。
- **`prompts.providers.<id>.user_prompt_profiles`**：user 模板包裹（注入 `{user_input}`）。
- **`prompts.providers.<id>.user_input_max_chars`**：用户输入注入前限长。
- **`prompts.providers.<id>.tool_result_render` / `tool_first_tools`**：工具回流渲染与触发范围。

### 技能注册配置（SkillRegistry）

文件：`src/platform_layer/resources/config/skills.yaml`

- **`skills.items[]`**：技能定义条目，包含 `id/index/title/summary/content/quality_tier/enabled/tags`。
- 会话的 `session.skills` 按 id 引用技能；模型层会把命中的技能内容注入 `system prompt` 的 `active_skills` 区块。
- 启动阶段做一致性校验：`session.skills` 中的 id 必须在 `skills.yaml` 中存在。

本地环境变量（勿提交到 Git）：

- **PowerShell**：在仓库根目录新建 `env.ps1`（文件名已 gitignore），例如一行：`$env:DEEPSEEK_API_KEY = "your-key"`；或在本机/用户环境变量中设置 `DEEPSEEK_API_KEY`。
- **Docker / CI**：通过 `-e` 或密钥管理注入，勿写入镜像。

## 当前运行链路（简述）

- `app/http_runtime.py`：HTTP 对接入口（把请求映射为 PortInput，返回 PortEvent 列表）
- `app/cli_runtime.py`：CLI 入口（本地交互调试）
- `app/composition.py`：装配依赖图谱（core + modules + store + memory + resource gate + provider）
- `app/config_loaders/resource_validation.py`：统一资源区校验入口（启动阶段校验 model/session/kernel/runtime/tools/mcp）
- `port/agent_port.py`：把 raw 输入适配为 `AgentRequest`，调用 core，再把 `AgentResponse` 翻译为 `PortEvent` 并 `emit`
- `core/agent_core.py`：微内核 loop 编排（text/tool_call）

## 团队协作与联调（Docker + 组网）

- **服务角色**：本项目作为 Agent 核心服务，默认监听 `0.0.0.0:8000`（HTTP）。
- **本地开发**：
  - `PYTHONPATH="src" python -m app.http_runtime`
- **Docker 运行**：
  - `docker build -t pompeii-agent:dev .`
  - `docker run -it --rm -p 8000:8000 pompeii-agent:dev`
- **组网协作**：
  - 通过虚拟局域网（如 Tailscale/ZeroTier/Oray 等）获得组网 IP，例如 `172.16.x.x`
  - 服务提供者在本机运行容器后，其他成员用：`http://<组网IP>:8000/health` 进行联调
  - 所有 HTTP 对接统一走 `/health` 与 `/input` 接口，返回 `events` 列表作为数据流串联结果

## 自动化测试（可选）

```powershell
cd C:\Users\22271\Desktop\Agent
pip install -r requirements-dev.txt
pytest
```

## 开发规则（必须遵守）

- 所有规则在：`docs/design/ai-rules-template/RULES.md`
- 占位实现必须按 STUB 规范标注：`// STUB(YYYY-MM-DD): 原因 — 替换计划`
- 每次变更必须追加记录到：`docs/design/CHANGELOG.md`（无记录视为未发生）
