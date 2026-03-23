## CHANGELOG

### Release 0.4.5（2026-03-23）

**版本号**：`0.4.5`。

- **仓库布局**：去掉 **`POMPEII/`** 中间层，将原 **`POMPEII/pompeii`** 下全部内容提升至 **Git 仓库根目录**（`src/`、`docs/`、`config/`、`scripts/` 等与 README 同级）；文档与脚本中的 `cd` 路径已同步更新。

---

### Release 0.4.4（2026-03-23）

**版本号**：`0.4.4`。

- **仓库布局**：删除仓库根目录重复的 **`设计/Pompeii/`**；其中与 `docs/design/架构设计ver0.4.md` 重复的 **`架构设计ver0.4.md`** 已移除；历史草案 **`架构设计ver0.2` / `ver0.3`** 迁入 **`docs/design/archive/`** 并补 `.md` 后缀；根目录随笔 **`架构设计ver0.1`** 重命名并迁入 **`docs/design/archive/早期随笔-市场与Agent技术观察.md`**（内容非架构规格，仅作备忘）。根目录 **`README.md`** 曾临时指向子路径 **`POMPEII/pompeii`** 的导航说明（**0.4.5** 起已取消该子路径）。

---

### Release 0.4.3（2026-03-23）

**版本号**：`0.4.3`。

- **文档与仓库布局**：原 `desigh_docs/` 目录并入 **`docs/design/`**；运维类文档在 **`docs/guides/`**；新增 **`docs/README.md`** 作为文档入口；修正旧目录名拼写（`desigh_docs` → `docs/design`）。
- **配置模板**：`config/env.ps1.example`、`.env.example` 迁至 **`config/`**；`scripts/load_env.ps1` 优先加载 `config/env.ps1`，兼容仓库根目录 `env.ps1`。
- **测试**：`pytest` 配置迁至根目录 **`pyproject.toml`**（删除根目录 `pytest.ini`）。

---

### Release 0.4.2（2026-03-24）

**版本号**：`0.4.2`。

- **文档**：全库同步——`README` 变更日志路径指向 `docs/design/CHANGELOG.md`；补全 `docs/design/会话存储与归档实现说明.md`；恢复/补全 `docs/design/现有结构与调用链图.md`（摘要版）；`STATUS` / `docs/guides/系统测试流程.md` / `docs/guides/API密钥配置操作手册.md` / `开发状态与系统接口.md` 与当前 **仅 SQLite 会话存储** 一致；修正下文 **0.4.0** 条目中已被 **0.4.1** 取代的表述；历史条目中 **GET /archives** 与 `memory` 后端相关描述已更正。
- **版本**：与 `src/app/version.py` 对齐。

---

### Release 0.4.1（2026-03-24）

**版本号**：`0.4.1`。

- **会话存储**：移除 `InMemorySessionStore`（内存 dict demo）；**唯一实现**为 `infra/SqliteSessionStore`（文件路径或 `SqliteSessionStore.ephemeral()` 使用 `:memory:`，供测试）。
- **运行时**：`runtime.yaml` 仅支持 `session_store.backend: sqlite`；`memory` 已删除（旧配置将触发 `RuntimeConfigLoaderError`）。
- **组合根**：`build_core` 始终按 `sqlite_path` 构造 `SqliteSessionStore`。
- **测试**：`test_memory_archives.py` 更名为 `test_sqlite_archives.py`，改用 `ephemeral()`。

---

### Release 0.4.0（2026-03-24）

**版本号**：`0.4.0`。

**P1（组装部上下文）**

- `SessionLimits.assembly_approx_context_tokens`：按启发式近似 token（`len(text)//4`）从**最新**消息向旧裁剪，使纳入 `Context.messages` 的总量不超过预算；`0` 关闭。
- `modules/assembly/token_budget.py`：`approximate_message_tokens`、`trim_messages_to_approx_token_budget`。
- `session_defaults.yaml` 默认 `assembly_approx_context_tokens: 24000`；loader / `session_json_codec` 已支持。

**P3（归档与长期摘要表）**

- `SqliteSessionStore`：会话 `ARCHIVED` 时写入 `session_archives`（规则摘要；**0.4.1** 起移除独立 `InMemorySessionStore`）。
- `core/session/session_archive.py`：`build_archive_row_dict`。

**P4（会话存储策略化）**

- `core/session/session_store_ops.py`：`append_message_inplace`，供 `SqliteSessionStore.append_message` 使用。

**测试**：`tests/test_token_budget.py`、`tests/test_sqlite_archives.py`（原 `test_memory_archives`）；既有 JSON codec 测试扩展。

---

### Release 0.3.7（2026-03-24）

**版本号**：`0.3.7`。

- **组装部上下文压缩（字符级）**：`SessionLimits.assembly_message_max_chars`（0=不截断）；纳入 `Context.messages` 前对单条消息按 `render_message_plain_text` 截断并加 `...`，不修改会话内原始 `Message`（`modules/assembly/message_clip.py`）。
- **配置**：`session_defaults.yaml` 默认 `assembly_message_max_chars: 12000`；`session_config_loader` / `session_json_codec` 支持读写。
- **测试**：`tests/test_assembly_impl.py`（截断用例）、`tests/test_session_json_codec.py`。

---

### Release 0.3.6（2026-03-24）

**版本号**：`0.3.6`。

- **组装部**：`modules/assembly/formatting.py`（`ModelOutput` 文本提取、工具结果 JSON 序列化写入 `Context.current`）；`Context.meta` 增加 `phase`（`user_turn` / `post_tool`）与 `intent_type`；`format_final_reply` 接收完整 `ModelOutput`。
- **内核**：`_build_text_response` 向组装部传入 `ModelOutput` 而非仅 `content`。
- **工具部**：`modules/tools/device_backend.py`（`DeviceToolBackend` 协议 + `NullDeviceBackend`）；`ToolModuleImpl` 可选 `device_backend`，在本地 handler 之前尝试 `try_local`（供测试桩 / 未来内联设备）。
- **会话**：`SessionManagerImpl.find_session_for_user` 使用 `_active_sessions_for_user` 辅助函数，意图更清晰。
- **测试**：`tests/test_assembly_impl.py`、`tests/test_device_backend.py`。

---

### Release 0.3.5（2026-03-24）

**版本号**：`0.3.5`。

- **Port 请求工厂**：`session_request_factory(user_id, channel)` 为每条用户消息生成独立 `request_id`（UUID）；`GenericAgentPort.handle(..., user_id=..., channel=...)` 改用该工厂，避免 HTTP 等多请求场景误用固定 `cli-1`。`http_request_factory` / `ws_request_factory` 已实现为对 `session_request_factory` 的默认参数封装（不再抛 `NotImplementedError`）。
- **`HttpMode` / `WsMode`**：明确文档化「由 Web/WS 处理器调用 `handle()`」，`receive`/`should_exit` 抛出带说明的 `NotImplementedError`；`app/http_runtime` 复用 `HttpMode`，去掉本地重复类。
- **测试**：`tests/test_request_factory.py`。

---

### Release 0.3.4（2026-03-24）

**版本号**：`0.3.4`。

- **工具确认流**：用户确认后由 `AgentCore.handle_confirmation_approved(request, tool_call)` 直接执行待确认工具并续跑对话循环，不再经完整 `handle` 重复追加用户消息或重复为同一句生成 `tool_call`；`GenericAgentPort._confirm_and_run` 已切换至该入口。
- **测试**：`tests/test_confirmation_approved.py`（确认后仍为单条 `user` 消息、模型调用次数符合预期）。

---

### Release 0.3.3（2026-03-24）

**版本号**：`0.3.3`。

- **多轮工具协议**：`ToolCall.call_id`；会话中写入 `openai_v1` 格式的 `assistant(tool_calls)` 与 `tool(tool_call_id)`（`core/session/openai_message_format.py`）；`step_execute_tool` / `step_device_request` / `handle_device_result` 对齐；模型历史 `_render_history_messages_for_model` 展开为 OpenAI `messages`。
- **解析**：`openai_tool_parse` 从响应 `tool_calls[].id` 回填 `call_id`。
- **测试**：`tests/test_openai_session_messages.py`。

---

### Release 0.3.2（2026-03-24）

**版本号**：`0.3.2`。

- **模型**：OpenAI 兼容 Chat Completions 响应支持解析 `message.tool_calls` → `ModelOutput(kind=tool_call)`；`modules/model/openai_tool_parse.py`；可选 `params.tools` / `params.tool_choice` 透传至请求体。
- **测试**：`tests/test_openai_tool_parse.py`。

---

### Release 0.3.1（2026-03-24）

**版本号**：`0.3.1`。

- **意图**：`/tool ping`、`/tool add <a> <b>` → `ToolPing` / `ToolAdd`，模型部直接产出 `tool_call` 以便 MCP 演示链路可经 HTTP/CLI 触发。
- **文档**：`README.md` 版本与 MCP/测试说明；`docs/guides/系统测试流程.md` 新增 **2.10**（可选 MCP 回归）。

---

### Release 0.3.0（2026-03-24）

**版本号**：`0.3.0`。

- **MCP（stdio）**：依赖官方 PyPI `mcp`；`platform_layer/resources/config/mcp_servers.yaml` 控制 `enabled` 与白名单进程参数（`{src_root}` 占位）；`infra/mcp_stdio_bridge.py` 实现 `McpToolBridge`，`composition.build_core` 可选注入；演示进程 `infra/mcp_demo_server.py`（`ping` / `add`）。
- **安全**：配置校验拒绝 shell 元字符；未安装 `mcp` 包时跳过桥接；生产请优先选用 [MCP Registry](https://modelcontextprotocol.io/registry) 与 [awesome-secure-mcp-servers](https://github.com/fuzzylabs/awesome-secure-mcp-servers) 中已审计服务。
- **内核白名单**：`kernel_config.yaml` 增加 `ping`、`add` 供演示工具过策略。
- **测试**：`requirements-dev.txt` 含 `pytest`；`tests/test_mcp_stdio_bridge.py`（集成子进程 + 配置拒绝用例）。

---

### Release 0.2.5（2026-03-24）

**版本号**：`0.2.5`。

- **归档入口**：用户消息 `/archive` → `SystemArchive`，`AgentCoreImpl` 将当前 `(user_id, channel)` 活跃会话置为 `ARCHIVED`（无活跃会话时提示）；`SessionStore`/`SessionManager`/`AgentCoreImpl` 提供 `list_archives_for_user`。
- **HTTP**：`GET /archives?user_id=...&limit=` 返回该用户归档摘要列表（依赖 SQLite `session_archives`；归档后非空）。

### 2026-03-24 — 文档（系统测试：2.9 归档与 /archives）

- **任务**：`docs/guides/系统测试流程.md` 新增 **2.9**（`/archive`、`GET /archives`、`sqlite` 前置说明）；**2.1** 通过标准含 `version`；CLI 与**第四节**汇总同步归档验收。
- **变更文件**：`docs/guides/系统测试流程.md`、`CHANGELOG.md`（本条）

---

### Release 0.2.4（2026-03-24）

**版本号**：`0.2.4`。

- **归档表**：`SqliteSessionStore` 在 `set_status(..., ARCHIVED)` 后写入 `session_archives`（规则摘要、`message_count`、UTC 时间）；`list_archives_for_user(user_id)` 供后续 API 接入。
- **规则摘要复用**：`core/session/rule_summary.py` 抽取 `/summary` 与归档共用逻辑；模型部改为调用该模块。

---

### Release 0.2.3（2026-03-24）

**版本号**：`0.2.3`。

- **工具 / MCP 预留**：`modules/tools/mcp_bridge.py` 定义 `McpToolBridge`；`ToolModuleImpl` 支持可选 `mcp=`，本地无 handler 时先 `try_call` 再回退 `unknown`。

---

### Release 0.2.2（2026-03-24）

**版本号**：`0.2.2`。

- **`/summary` 可配置**：`SessionLimits.summary_tail_messages`、`summary_excerpt_chars`（默认 12 / 200）；YAML 与 SQLite 会话 JSON 往返；模型层规则摘要运行时钳制条数 1–200、摘录 16–4000 字符。

---

### Release 0.2.1（2026-03-24）

**版本号**：`src/app/version.py` → `0.2.1`。

- **组装部**：`SessionLimits.assembly_tail_messages`（默认 20，可在 `session_defaults.yaml` → `limits` 配置）；`AssemblyModuleImpl` 构建/工具回注上下文时取会话尾部消息条数，运行时钳制在 **1–200**；SQLite 会话 JSON 缺该字段时读入默认 20。

---

### Release 0.2.0（2026-03-24）

**版本号**：`src/app/version.py` 中 `0.2.0`；HTTP `GET /health` 返回 `version` 字段。

**本版包含（相对 0.1 骨架期）**：

- **会话存储**：`runtime.yaml` 可选 `session_store.backend: sqlite`，`infra/SqliteSessionStore` + JSON codec；默认 `memory` 不变。
- **模型**：多 provider 注册表、`openai_compatible`、Chat 请求当前轮 user 去重。
- **Port**：HTTP 单例 Port、待确认/待设备按 `(user_id, channel)` 分区；**threading.Lock** 保护待确认/设备字典。
- **HTTP**：`/input` 校验 `user_message` 缺 `text`；启动脚本与 ExecutionPolicy 说明。
- **/summary**：基于最近 `Context.messages` 的**规则摘要**（非 LLM）。
- **文档**：系统测试流程、README、STATUS 与数据层对照表同步。

---

### 2026-03-24 — AI（Release 0.2.0：/summary 规则摘要 + Port 锁 + version）
- **任务**：`/summary` 基于 `Context.messages` 生成规则摘要；`GenericAgentPort` 对 pending 字典加锁；`app/version.py` + `/health` 返回 `version`；README 与系统测试文档同步。
- **变更文件**：`src/modules/model/impl.py`、`src/port/agent_port.py`、`src/app/http_runtime.py`、`src/app/version.py`、`README.md`、`docs/guides/系统测试流程.md`、`docs/design/CHANGELOG.md`、`docs/design/STATUS.md`

### 2026-03-24 — AI（数据层：可选 SQLite 会话持久化）
- **任务**：新增 `infra/session_json_codec.py`、`infra/sqlite_session_store.py`；`runtime.yaml` + `runtime_config_loader`；`build_core` 按配置选择 `InMemorySessionStore` 或 `SqliteSessionStore`；`http_runtime` 传入 `src_root`；`.gitignore` 忽略会话库；README 说明运行时配置。
- **变更文件**：
  - `src/infra/session_json_codec.py`、`src/infra/sqlite_session_store.py`、`src/infra/__init__.py`
  - `src/app/config_loaders/runtime_config_loader.py`
  - `src/platform_layer/resources/config/runtime.yaml`
  - `src/platform_layer/resources/data/.gitkeep`
  - `src/app/composition.py`、`src/app/http_runtime.py`
  - `.gitignore`、`README.md`、`docs/design/STATUS.md`
  - `CHANGELOG.md`（本条）
- **影响范围**：将 `runtime.yaml` 中 `session_store.backend` 改为 `sqlite` 并重启服务后，同用户会话可在重启后保留；不改变默认 `memory` 行为。

### 2026-03-24 — AI（STATUS：数据与资源层设计对照）
- **任务**：在 `STATUS.md` 增加「数据与资源层」小节，对照 `架构设计ver0.4.md` 说明信息缓存/长期存储/向量与资源守门与当前实现的差距及建议落地顺序。
- **变更文件**：`docs/design/STATUS.md`、`CHANGELOG.md`（本条）

### 2026-03-24 — AI（Port：HTTP 多请求共享待确认；STATUS 仓库与 STUB 节奏）
- **任务**：`GenericAgentPort` 的待确认/待设备状态改为按 `(user_id, channel)` 字典存储；`handle` 支持 `emitter` 与 `user_id`/`channel`；HTTP 复用单例 `_HTTP_PORT` + thread-local emitter 注入。`docs/guides/系统测试流程.md` 2.6 补充第二步确认命令。`docs/design/STATUS.md` 增加「仓库与 STUB 何时完成」。
- **变更文件**：
  - `src/port/agent_port.py`
  - `src/app/http_runtime.py`
  - `docs/guides/系统测试流程.md`
  - `docs/design/STATUS.md`
  - `CHANGELOG.md`（本条）

### 2026-03-24 — AI（HTTP /input：user_message 缺 text 字段校验）
- **任务**：`kind=user_message` 且未提供 `text` 时不再调用 Core/模型，直接返回 `ErrorEvent`（`reason=validation_missing_text`），与 `docs/guides/系统测试流程.md` 2.8 对齐；空消息仍用 `"text":""`。
- **变更文件**：`src/app/http_runtime.py`、`docs/guides/系统测试流程.md`、`CHANGELOG.md`（本条）

### 2026-03-24 — AI（修复：run-http.cmd / load_env.ps1 编码与 cmd 解析）
- **任务**：`run-http.cmd` 改为纯 ASCII 注释并显式 `powershell.exe`，避免中文 Windows 下 UTF-8 `.cmd` 被误解析（曾出现 `'Shell' 不是内部或外部命令`）；`load_env.ps1` 提示改为英文，避免引号/中文在 PS 5.1 下损坏。
- **变更文件**：`scripts/run-http.cmd`、`scripts/run-cli.cmd`、`scripts/load_env.ps1`、`CHANGELOG.md`（本条）

### 2026-03-24 — AI（文档：ExecutionPolicy 下用 IEX 加载 env.ps1）
- **任务**：补充 `Get-Content ... | Invoke-Expression` 与 `run-http.cmd` 说明，解决无法 `. .\env.ps1` 时的密钥注入；修正 API 手册中的示例密钥占位。
- **变更文件**：`config/env.ps1.example`、`docs/guides/API密钥配置操作手册.md`、`docs/guides/系统测试流程.md`、`CHANGELOG.md`（本条）

### 2026-03-24 — AI（启动脚本：run-http.cmd 绕过 ExecutionPolicy）
- **任务**：新增 `scripts/run-http.cmd`、`scripts/run-cli.cmd`，内部以 `powershell -ExecutionPolicy Bypass -File` 调用对应 `.ps1`，避免默认策略禁止运行脚本。
- **变更文件**：`scripts/run-http.cmd`、`scripts/run-cli.cmd`、`docs/guides/系统测试流程.md`、`README.md`、`CHANGELOG.md`（本条）

### 2026-03-24 — AI（系统测试：PowerShell 自动注入 API Key）
- **任务**：为本地测试提供 `scripts/load_env.ps1`、`run-http.ps1`、`run-cli.ps1`，从仓库根目录 `env.ps1` 加载密钥后再启动进程；更新 `docs/guides/系统测试流程.md` 与 `README` 启动说明。
- **变更文件**：
  - `scripts/load_env.ps1`、`scripts/run-http.ps1`、`scripts/run-cli.ps1`（新增）
  - `.gitignore`（忽略 `env.ps1`、`.env`）
  - `docs/guides/系统测试流程.md`、`README.md`、`config/env.ps1.example`
  - `CHANGELOG.md`（本条）
- **影响范围**：运行 `http_runtime`/`cli_runtime` 时一键注入 `DEEPSEEK_API_KEY`；`Invoke-RestMethod` 仍仅需服务侧已注入。

### 2026-03-24 — AI（模型 E2E：OpenAI 兼容请求去重当前轮 user）
- **任务**：修复 Core 已把本轮用户消息写入 `session.messages` 后，模型层再次追加同一条 `user` 导致请求体重复、多轮上下文失真的问题（对齐 `docs/guides/系统测试流程.md` 2.2/2.3 验收）。
- **变更文件**：
  - `src/modules/model/impl.py`（`_drop_trailing_user_if_matches_current` + `_run_openai_compatible_chat` 调用）
  - `CHANGELOG.md`（本条）
- **影响范围**：单轮/多轮 Chat 发往 `/v1/chat/completions` 的 `messages` 与真实对话一致，不再双写当前用户句。

### 2026-03-23 — AI（模型：可切换注册表与统一配置）
- **任务**：将模型调用抽象为可切换框架：`model_providers.yaml` 统一声明 `default_provider`、多 provider 及 `params.api_key_env`；`SessionConfig.model` 与 provider **id** 对齐以切换后端；`openai_compatible` 与 legacy `deepseek` 共用一套 HTTP 实现。
- **变更文件**：
  - `src/modules/model/config.py`（`ModelRegistry` 增加 `default_provider_id`）
  - `src/app/config_loaders/model_provider_loader.py`（加载 `default_provider` 与校验）
  - `src/modules/model/impl.py`（按 registry + 会话解析 provider；`_run_openai_compatible_chat`）
  - `src/modules/model/interface.py`（`Session` 改为 `TYPE_CHECKING`，减轻 import 环）
  - `src/modules/model/__init__.py`（延迟导出 `ModelModule`/`ModelOutput`，避免 `config_loaders` 与 `core` 循环依赖）
  - `src/app/composition.py`（`ModelModuleImpl(registry=...)`）
  - `src/platform_layer/resources/config/model_providers.yaml`（stub / deepseek / openai 示例）
  - `src/platform_layer/resources/config/session_defaults.yaml`（`session.model` 与 provider id 对齐）
  - `README.md`（模型配置说明）
  - `CHANGELOG.md`（本条）
- **影响范围**：新增 provider 只需改 YAML + 环境变量；会话级切换模型改 `session_defaults.yaml` 或通过 ConfigProvider 按 user/channel 分流。

### 2026-03-18 — AI（文档搭建）
- **任务**：补齐项目根目录文档入口（README/STATUS/CHANGELOG）
- **变更文件**：
  - `README.md`
  - `STATUS.md`
  - `CHANGELOG.md`
- **影响范围**：文档体系完成闭环；后续变更按规则持续维护

### 2026-03-18 — AI（架构收敛/代码优化）
- **任务**：修复分层反向依赖（platform→core），并按规则补齐占位实现 STUB 标注
- **变更文件**：
  - `src/app/config_loaders/session_config_loader.py`（新增）
  - `src/app/config_loaders/kernel_config_loader.py`（新增）
  - `src/app/config_provider.py`（更新 import）
  - `src/app/composition.py`（更新 import）
  - `src/platform/shared/session_config_loader.py`（删除）
  - `src/platform/shared/kernel_config_loader.py`（删除）
  - `src/port/agent_port.py`（补齐 STUB 标注）
  - `src/port/request_factory.py`（补齐 STUB 标注）
  - `src/modules/model/impl.py`（补齐 STUB 标注）
  - `src/modules/tools/impl.py`（补齐 STUB 标注）
  - `src/modules/assembly/impl.py`（补齐 STUB 标注）
  - `STATUS.md`（更新 STUB 清单）
  - `CHANGELOG.md`（本条）
- **影响范围**：分层更一致；占位实现可识别；后续演进更可控

### 2026-03-18 — AI（端口输入事件收敛）
- **任务**：将 `AgentPort.handle` 输入升级为结构化 `PortInput`，并收敛 request_factory 只接受 `UserMessageInput`，避免 system_command 混入业务请求
- **变更文件**：
  - `src/port/input_events.py`（新增）
  - `src/app/runtime.py`（用 UserMessageInput 包装每行输入）
  - `src/port/agent_port.py`（handle 接收 PortInput；非 user_message 输入 emit 错误事件）
  - `src/port/request_factory.py`（RequestFactory 只接受 UserMessageInput）
  - `CHANGELOG.md`（本条）
- **影响范围**：确认流与普通消息通道语义更清晰；为 HTTP/WS/device_result 扩展铺路

### 2026-03-18 — AI（确认流升级：带 confirmation_id）
- **任务**：将确认流程升级为可跨渠道复用的形式：ConfirmationEvent 携带 `confirmation_id`，CLI 支持 `/confirm <id> yes|no`；同时保留 `yes/no` 兼容路径
- **变更文件**：
  - `src/port/events.py`（ConfirmationEvent 增加 confirmation_id）
  - `src/port/agent_port.py`（pending confirmation 引入 confirmation_id；解析 /confirm 指令；渲染增强）
  - `src/app/runtime.py`（/confirm 行输入映射为 SystemCommandInput）
  - `README.md`（更新使用说明）
  - `CHANGELOG.md`（本条）
- **影响范围**：确认交互不再依赖“下一条消息必须是 yes”；为 HTTP/WS/设备回调等异步确认场景打基础

### 2026-03-18 — AI（设备闭环：device_request/device_result）
- **任务**：实现最小设备能力闭环：tool_call 触发 device_request，CLI 支持 `/device_result <json>` 回传，Core 回注结果后继续 loop
- **变更文件**：
  - `src/core/device_types.py`（新增 DeviceRequest）
  - `src/core/agent_types.py`（新增 pending_device_request）
  - `src/core/agent_core.py`（新增 handle_device_result；tool_call -> device_request 分发）
  - `src/modules/model/impl.py`（新增 /tool take_photo 触发）
  - `src/platform/resources/config/kernel_config.yaml`（allowlist/confirm_required 增加 take_photo）
  - `src/port/events.py`（DeviceRequestEvent 结构化）
  - `src/port/agent_port.py`（pending device_request 状态机；解析 /device_result JSON；CLI 渲染）
  - `src/app/runtime.py`（识别 /device_result 并包装 DeviceResultInput）
  - `README.md`（更新试运行指令）
  - `CHANGELOG.md`（本条）
- **影响范围**：对齐图纸中的 device_request/device_result 通路，为真实设备接入铺路

### 2026-03-18 — AI（会话消息写入：可追溯性增强）
- **任务**：在 core 编排中写入关键消息（user/assistant/tool），让 session.messages 能真实反映一次 run 的轨迹
- **变更文件**：
  - `src/core/agent_core.py`（在 handle/text/tool/device_result 路径追加 append_message）
  - `CHANGELOG.md`（本条）
- **影响范围**：会话可追溯性增强；为后续 assembly 构建 context window（基于历史消息）打基础

### 2026-03-18 — AI（core types 收敛）
- **任务**：将 core 的共享类型收敛到 `src/core/types/`，并提供统一出口（保留旧路径兼容层）
- **变更文件**：
  - `src/core/types/__init__.py`（新增）
  - `src/core/types/tool.py`（新增）
  - `src/core/types/device.py`（新增）
  - `src/core/tool_types.py`（改为兼容 re-export）
  - `src/core/device_types.py`（改为兼容 re-export）
  - `src/core/__init__.py`（导出 ToolCall/ToolResult/DeviceRequest）
  - `CHANGELOG.md`（本条）
- **影响范围**：core 目录结构更清晰；共享类型的长期维护成本降低

### 2026-03-18 — AI（core types 彻底迁移）
- **任务**：全仓库迁移到 `core.types` 导入路径，并删除多余的兼容/重复文件
- **变更文件**：
  - `src/core/agent_types.py`（恢复为 core 根目录文件）
  - `src/core/agent_core.py`（切换为 `from .types import ...`）
  - `src/port/agent_port.py`、`src/port/events.py`（切换为 `from core.types import ...`）
  - `src/modules/*`（切换为 `from core.types import ...`）
  - `src/core/types/agent_types.py`（删除）
  - `src/core/types/tool_types.py`（删除）
  - `src/core/types/device_types.py`（删除）
  - `CHANGELOG.md`（本条）
- **影响范围**：core/types 结构稳定；移除多余文件后更易维护

### 2026-03-18 — AI（core 职责收敛：消息/策略/设备路由拆分）
- **任务**：将 `agent_core.py` 中“消息写入构造 / 工具安全门决策 / tool→device_request 路由”拆分为小模块，降低耦合并防止 core 文件继续膨胀（行为不变）
- **变更文件**：
  - `src/core/session/message_factory.py`（新增：new_message）
  - `src/core/tool_policy.py`（新增：decide_tool_policy）
  - `src/core/device_router.py`（新增：tool_to_device_request）
  - `src/core/agent_core.py`（改为调用上述模块）
  - `CHANGELOG.md`（本条）
- **影响范围**：core 的编排逻辑更聚焦；后续扩展新工具/新设备映射时改动面更小

### 2026-03-18 — AI（core 职责收敛：loop 治理拆分）
- **任务**：将 loop 的治理逻辑（max_loops 计算 / tool_call 计数）从 `agent_core.py` 拆出，`_run_loop` 更聚焦在编排；同时统一 handler 返回值为 Step 结构，减少类型分支
- **变更文件**：
  - `src/core/loop_policy.py`（新增：LoopGovernance/build_loop_governance/next_tool_calls）
  - `src/core/agent_core.py`（使用 governance + OutputStep）
  - `CHANGELOG.md`（本条）
- **影响范围**：后续追加“终止策略/预算策略”时更容易保持 core 低耦合

### 2026-03-18 — AI（core 进一步收敛：预算策略/输出处理器/Smoketest）
- **任务**：进一步将 loop 预算决策迁入 `loop_policy`；将输出 kind→handler 的构建逻辑拆到独立模块；新增最小 smoke test 验证 core 可运行
- **变更文件**：
  - `src/core/loop_policy.py`（新增：tool_call_budget_decision）
  - `src/core/output_handlers.py`（新增：OutputStep/build_output_handlers）
  - `src/core/agent_core.py`（移除 handler/预算内联实现，改为调用上述模块）
  - `src/core/agent_core_smoke_test.py`（新增）
  - `CHANGELOG.md`（本条）
- **影响范围**：`agent_core.py` 更接近“纯编排”；扩展新输出 kind/新预算规则时改动面更小

### 2026-03-18 — AI（core 最终收敛：终止/unsupported 策略化 + 文件结构优化）
- **任务**：将 `unsupported_output_kind` 与 `max_loops` 终止路径也策略化；并把 core 内的 policy 类模块收敛到 `core/policies/` 子包，同时保留旧路径 re-export 兼容层
- **变更文件**：
  - `src/core/loop_policy.py`（补齐：max_loops_exceeded_response；后续改为 re-export）
  - `src/core/output_handlers.py`（补齐：resolve_handler；后续改为 re-export）
  - `src/core/agent_core.py`（loop 终止/unsupported/预算全部收敛成 step 流水线；导入切换到 `core.policies`）
  - `src/core/policies/__init__.py`（新增）
  - `src/core/policies/loop_policy.py`（新增）
  - `src/core/policies/output_handlers.py`（新增）
  - `src/core/policies/tool_policy.py`（新增）
  - `src/core/policies/device_router.py`（新增）
  - `src/core/tool_policy.py`、`src/core/device_router.py`、`src/core/loop_policy.py`、`src/core/output_handlers.py`（改为薄 re-export）
  - `CHANGELOG.md`（本条）
- **影响范围**：`agent_core.py` 更接近“纯状态机编排”；文件结构更聚合，降低长期膨胀风险

### 2026-03-18 — AI（core 收敛：tool_call 动作表 + 删除冗余兼容文件）
- **任务**：将 tool_call 执行路径拆为依赖注入式的动作模块（device_request / execute_tool），减少 core 内长 if；并删除 `core/*` 下的薄 re-export 冗余文件，统一入口为 `core/policies/*`
- **变更文件**：
  - `src/core/policies/tool_actions.py`（新增）
  - `src/core/policies/__init__.py`（导出 tool_actions）
  - `src/core/agent_core.py`（tool_call 路径改为 ToolDeps+动作表）
  - `src/core/loop_policy.py`、`src/core/output_handlers.py`、`src/core/tool_policy.py`、`src/core/device_router.py`（删除）
  - `CHANGELOG.md`（本条）
- **影响范围**：core 依赖边界更清晰；文件结构更精简；后续扩展新动作只需新增 action 函数/表项

### 2026-03-19 — AI（Docker 实验性封装）
- **任务**：增加 Docker 实验性封装，用于对接验证运行形态（不实现具体业务能力）
- **变更文件**：
  - `requirements.txt`（新增：PyYAML）
  - `Dockerfile`（新增：运行 `python -m app.runtime`）
  - `.dockerignore`（新增）
  - `CHANGELOG.md`（本条）
- **影响范围**：可在容器中运行 CLI 进行“对接级”实验；功能测试留待后续版本

### 2026-03-19 — AI（HTTP 对接：runtime 重构 + 事件回传）
- **任务**：将 CLI runtime 与 HTTP runtime 分离：默认走 HTTP 对接，返回 PortEvent 列表用于实验性串联；CLI 作为调试入口保留
- **变更文件**：
  - `src/app/runtime.py`（删除：迁移为 `cli_runtime.py`）
  - `src/app/cli_runtime.py`（新增）
  - `src/app/http_runtime.py`（新增：FastAPI `/health` 与 `/input`）
  - `src/port/http_emitter.py`（新增：收集 PortEvent）
  - `requirements.txt`（增加：fastapi/uvicorn）
  - `Dockerfile`（默认启动：`uvicorn app.http_runtime:app`）
  - `README.md`（更新启动与对接说明）
  - `CHANGELOG.md`（本条）
- **影响范围**：可用 HTTP 做“对接级”数据流串联；后续再在此基础上做功能实现与功能测试

### 2026-03-19 — AI（修复：platform 命名冲突导致容器运行崩溃）
- **任务**：修复项目包名 `platform` 与 Python 标准库 `platform` 冲突导致的 `platform.system()` 崩溃（容器内尤为明显）
- **变更文件**：
  - `src/platform/`（删除）
  - `src/platform_layer/`（新增：替代目录）
  - `src/app/composition.py`（资源路径改为 `platform_layer`）
  - `README.md`（更新配置路径说明）
  - `CHANGELOG.md`（本条）
- **影响范围**：Docker/本地运行恢复正常；避免后续依赖（uvicorn/websockets 等）被标准库冲突影响

### 2026-03-19 — AI（核心能力增强：assembly/model/tools 协同）
- **任务**：为 assembly/model/tools 补齐最小可用能力，让一次对话具备上下文感知、简单指令和实用工具
- **变更文件**：
  - `src/modules/assembly/types.py`（新增：Context 结构）
  - `src/modules/assembly/impl.py`（使用最近消息 + 当前 payload 构建 Context；回注工具结果到 meta.last_tool）
  - `src/modules/model/impl.py`（支持 /help 与 /summary 指令；兼容 Context.current）
  - `src/modules/tools/impl.py`（新增 calc/now 工具与安全算术求值）
  - `CHANGELOG.md`（本条）
- **影响范围**：HTTP `/input` 调用在占位模型下已具备简单“帮助/概要/本地工具”能力，为后续接入真实 LLM 和外部工具打基础

