# Pompeii-Agent

**当前版本**：`0.4.16`（见 `src/app/version.py`；HTTP `GET /health` 返回 `version` 字段）

Pompeii-Agent 是一个面向长期演进的 **微内核 Agent 基础设施**项目：用清晰分层与严格依赖方向，把「运行时入口 / 端口边界 / 内核编排 / 模块处理 / 平台能力」解耦，便于后续扩展 HTTP/WS、真实模型、MCP、长期存储与安全策略。

## 文档入口（先看这些）

- **总览**：`docs/README.md`
- **设计索引**：`docs/design/INDEX.md`
- **开发状态与系统接口**：`docs/design/开发状态与系统接口.md`
- **架构图纸**：`docs/design/架构设计ver0.4.md`
- **项目规范（Rules）**：`docs/design/ai-rules-template/RULES.md`
- **项目状态与开发优先级**：`docs/design/STATUS.md`（当前主线：完整系统；外部对接靠后）
- **变更日志**：`docs/design/CHANGELOG.md`（项目主日志；根目录无单独 `CHANGELOG.md` 时以此为准）
- **系统测试 / API 密钥**：`docs/guides/系统测试流程.md`、`docs/guides/API密钥配置操作手册.md`

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
- `POST /input`（返回 `events` 列表，作为实验性对接的“数据流串联”输出）
- `GET /archives?user_id=...`（会话归档摘要列表；依赖 SQLite `session_archives` 表，见 `runtime.yaml` 与 `docs/design/开发状态与系统接口.md`）

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
- 仅允许在该 YAML 中声明 **`command` / `args` / `env`**，勿将用户输入拼入进程参数；生产选型请优先 [MCP Registry](https://modelcontextprotocol.io/registry) 与已审计清单。
- 仓库自带演示：`infra/mcp_demo_server.py`（工具名 `ping`、`add`），需在 `kernel_config.yaml` 的 `tool_allowlist` 中放行（默认已包含演示名）。

### 模型配置（ModelRegistry）

文件：`src/platform_layer/resources/config/model_providers.yaml`

- **`default_provider`**：与会话 `session.model` 无法匹配任一 id 时使用的回退 provider。
- **`providers.<id>`**：每个 **id** 即工程内可引用的提供方名称；`session_defaults.yaml` 里的 **`session.model`** 填这里的 id，即可切换不同 API/模型。
- **`backend`**：`stub`（占位）或 `openai_compatible`（以及兼容的 `deepseek` 别名），统一走 OpenAI Chat Completions 协议。
- **`params.api_key_env`**：声明该 provider 使用的 **环境变量名**（不要在文件里写 Key）；未设置 `api_key_env` 的 legacy `deepseek` backend 仍默认读 `DEEPSEEK_API_KEY`。
- **`params.prompt_profiles`**：按 `profile -> strategy` 配置 system prompt 模板；由会话级 `session.prompt_profile` + `session.prompt_strategy` 选择（并兼容旧字符串格式）。
- **`params.prompt_vars` / `params.prompt_vars_env`**：对 `prompt_profiles` 模板进行变量注入（静态值 + 环境变量），实现统一参数化管理。
- **`params.user_prompt_profiles`**：按 `profile -> strategy` 配置 user prompt 包装模板，用于将 `{user_input}` 以结构化形式注入到 `user` 消息。
- **`params.user_input_max_chars`**：用户输入注入模板前的字符上限（`0` 为不限制），用于长输入稳定化。
- **`params.tool_result_render`**：工具结果回流轮次的直出格式（`raw` / `short` / `short_with_reason`），可按 strategy 配置。
- **`params.tool_first_tools`**：`tool_first` 策略触发白名单（可按 strategy 配置）；未配置时默认所有工具均可触发。
- **加载期校验**：`model_providers.yaml` 中上述提示词字段在启动时做结构校验；配置错误会直接抛出加载异常，避免运行期静默失败。
- 由 `load_model_registry` 加载，在 `composition.build_core` / `http_runtime` 中注入 `ModelModuleImpl`。

本地环境变量（勿提交到 Git）：

- **PowerShell**：在仓库根目录新建 `env.ps1`（文件名已 gitignore），例如一行：`$env:DEEPSEEK_API_KEY = "your-key"`；或在本机/用户环境变量中设置 `DEEPSEEK_API_KEY`。
- **Docker / CI**：通过 `-e` 或密钥管理注入，勿写入镜像。

## 当前运行链路（简述）

- `app/http_runtime.py`：HTTP 对接入口（把请求映射为 PortInput，返回 PortEvent 列表）
- `app/cli_runtime.py`：CLI 入口（本地交互调试）
- `app/composition.py`：装配依赖图谱（core + modules + store + provider）
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







