## Pompeii-Agent 当前状态（快照）

**发布线**：`0.4.16`（见 `src/app/version.py`）

### 概览
- **目标**：以 Python 为起点，构建可长期演进的微内核 Agent 基础设施。
- **分层骨架**：`app`（runtime/composition）→ `port`（唯一边界 handle/emit）→ `core`（loop 编排）→ `modules`（assembly/model/tools）→ `platform_layer`（配置/资源）→ `infra`（预留）

### 实施优先级（原则）

| 优先做 | 后做 |
|--------|------|
| **完整系统**：在 **core → modules → port** 上把单条请求从进入到结束跑通、可测、可维护——会话与状态、组装与上下文、模型/工具协议、策略与错误路径、回归测试与 smoke；把 **assembly / model / tools** 从「能演示」推到「边界清晰、可替换」 | **外部对接**：额外 HTTP 路由与网关形态、WebSocket 服务化、MCP 非 stdio 传输、多租户接入、第三方回调/SDK 等——在**内核与模块契约稳定**后再扩展，避免把外部协议绑死在半成品编排上 |

- 当前主线：**补齐模块实现与 core 编排一致性**（见下「活跃 STUB」与「后续任务编排」中标注为**系统内**的项）。
- 明确**不**作为近期主线：为对接方单独扩面、堆集成代码而绕过或分叉 core 契约。

### 已完成（里程碑）
- **`/summary` 规则摘要**：基于最近 `Context.messages` 列表化输出（不调用 LLM）；条数与单条摘录长度可在 `session_defaults.yaml` → `limits.summary_*` 配置；`GET /health` 返回 `version`（`0.4.16`）；`GET /archives` 列出用户归档摘要（SQLite）；可选 **MCP stdio**；OpenAI **`tool_calls` 解析** + **会话内 assistant/tool 与 call_id 对齐**
- **Port 并发**：待确认/待设备字典读写加 `threading.Lock`
- **会话持久化**：`runtime.yaml` 中 `session_store.backend: sqlite` + `sqlite_path`，统一使用 `infra/SqliteSessionStore`（无独立内存 dict 实现；测试用 `SqliteSessionStore.ephemeral()`）
- HTTP 复用 `GenericAgentPort`：待确认/待设备按 `(user_id, channel)` 分区；每请求 `HttpEmitter` 经 thread-local 注入
- OpenAI 兼容模型请求：当前轮 user 与 `session.messages` 去重后再组 `messages` 载荷（多轮验收基础）
- 端口事件体系（`PortEvent`）与 `emit` 边界
- `tool_call` 最小闭环（model → tools → assembly → loop）
- KernelConfig（长期保存）与治理参数接入（max_loops/max_tool_calls/allowlist/confirmation_required）
- 工具安全门与确认流（确认状态在 port 层维护）；确认批准后走 `handle_confirmation_approved`，不重复用户消息
- core 职责收敛：消息写入/工具策略/设备路由/loop 治理拆分，`agent_core.py` 更接近纯编排
- core 最小可运行 smoke test（`src/core/agent_core_smoke_test.py`）

### 活跃 STUB 清单（必须持续清理）
> 规则：所有占位实现必须包含 `// STUB(YYYY-MM-DD): 原因 — 替换计划`
- `src/port/agent_port.py` — `HttpMode`/`WsMode` 仅用于类型与文档（不实现 stdin 循环）；**HTTP 运行时**已复用 `HttpMode`；未来 **WS 服务端**接入时同理在收包处调 `handle()`
- ~~`src/port/request_factory.py`~~ — `session_request_factory` / `http_request_factory` / `ws_request_factory` 已落地（按会话分区、每条消息独立 `request_id`）
- `src/modules/model/impl.py` — OpenAI 兼容 Chat 已可用；**响应 `tool_calls` 已解析**；流式输出等仍待扩展（可视为部分 STUB）
- `src/modules/tools/impl.py` — 本地工具 + 可选 MCP stdio 桥接；设备执行器仍待替换
- `src/modules/assembly/impl.py` — P1：`formatting`、单条字符预算、**近似总量 token 预算**（`assembly_approx_context_tokens`）；**接入 tiktoken 或 LLM 摘要仍属可选增强**

### 仓库与 STUB 何时完成（建议节奏）
- **Git 仓库**：在「有可复现的启动方式 + 至少一次 CHANGELOG」后即可 `git init`；不必等 STUB 清空。用分支/标签标记里程碑（如 `milestone-http-e2e`）。
- **占位 STUB**：按**迭代目标**替换，而非一次性清零——优先替换 **assembly/model/tools** 等系统内模块；与**外部系统**对接相关的 STUB（如 MCP 传输扩展）按「实施优先级」靠后。未动到的 STUB 保留标注即可。
- **优先级**：**完整系统**（契约 + 核心路径测试 + 模块质量）**>** 清掉与当前里程碑无关的占位 **>** 外部对接扩面。
- **系统测试**：`docs/guides/系统测试流程.md` 已覆盖 `version`、`/archive`、`GET /archives`、**SQLite**（2.9）与 **可选 MCP**（2.10）。

### 已知风险/债务（优先级从高到低）
- **分层方向**：配置 loader 已迁移至 `app/config_loaders/*`，需持续避免 `platform/*` 反向依赖 `core/*`
- **确认输入建模**：HTTP 已支持 `system_command` 与 `user_message` 完成确认；Port 侧待确认/待设备字典已加 `threading.Lock`；多 worker 进程仍不共享内存，需外置会话/状态
- **会话实现质量**：`session_manager.py/session_store.py` 仍存在较多 if/流程耦合（当前可用但不够“策略化”），后续可按同样方式做“策略/状态机收敛”
- **模型配置基座**：`model_providers.yaml` 提供 `default_provider`、多 provider 与 `api_key_env`；`SessionConfig.model` 选择 provider id；`ModelModuleImpl` 按会话解析并调用 `stub` / `openai_compatible`

### 数据与资源层（设计对照｜尚未按 ver0.4 落地）

`架构设计ver0.4.md` 中与「数据 / 资源」相关的分工大致是：

| 设计概念（ver0.4） | 含义摘要 | 当前代码现状 |
|-------------------|----------|--------------|
| **信息缓存** | 会话内 `messages` 等热数据 | 有：`infra/SqliteSessionStore`（文件或 `:memory:` 临时库） |
| **长期存储** | 归档会话、画像、摘要；引擎可 SQLite/PG 等 | **部分**：`SqliteSessionStore` 在会话 **`ARCHIVED`** 时写入 **`session_archives`**（规则摘要 + 元数据）；画像/向量等仍未实现 |
| **向量 / 检索** | 归档文本摘要 + 向量嵌入、混合检索/GraphRAG | **无** |
| **资源区 / 资源访问守门** | 关卡⑤：读写分级、高敏感经核心审批等 | **未实现**（仅有内核侧工具策略雏形） |
| **platform_layer** | 在本仓库中主要承担**静态配置与资源路径** | **仅有** `resources/config/*.yaml` 等；**不是**设计里的「数据部」全套实现 |

结论：**会话持久化 + 归档摘要表（SQLite）已部分落地**；**画像 / 向量 / 资源守门**仍未实现；`platform_layer` 仍以**配置与文件布局**为主。

**建议落地顺序（与功能绑定，不必一次做完）**：

1. ~~**会话持久化**~~：**已实现** `SqliteSessionStore` 文件库（见 `runtime.yaml`）；仍可将存储后端换为 PG 等。  
2. **归档与长期记忆**：规则摘要 + `session_archives` **已落地**；**LLM 摘要 / 用户画像** 仍属后续。  
3. **向量与 RAG**：在 (2) 之后，再接入向量库与检索策略接口。  
4. **资源守门**：与多工具/MCP/外部文件访问需求强相关时再收紧策略。

### 后续任务编排（简表）

> **类型**：`系统内` = 完整系统主线；`外部对接` = 契约稳定后再做（见「实施优先级」）。

| 顺序 | 类型 | 任务 | 说明 |
|------|------|------|------|
| P0 | 系统内 | 会话 SQLite | **已落地**（唯一 `backend: sqlite`）；生产并发可再加锁/连接策略 |
| P1 | 系统内 | Assembly 摘要/压缩 | **已落地**：规则摘要、`assembly_message_max_chars`、**`assembly_approx_context_tokens` 启发式总量裁剪**；可选 **tiktoken / LLM 摘要** |
| P2 | 系统内 | 工具部与设备抽象 | 本地工具 + **`DeviceToolBackend`**；**stdio MCP** 已够用则不必先上 SSE/HTTP |
| P3 | 系统内 | 归档 + 长期记忆表 | **已落地**：`SqliteSessionStore`（文件或 `ephemeral()`）在 `ARCHIVED` 时写入归档摘要；`GET /archives`、**/archive**；**LLM 异步摘要**仍待接 |
| P4 | 系统内 | Session 管理策略化 | **部分落地**：`append_message_inplace` 统一追加与统计；状态机/策略对象可再迭代 |
| P5 | 外部对接 | MCP 传输扩展 | SSE/HTTP 传输、多租户隔离——**在 P1–P4 无阻塞需求时**再排 |
| P6 | 系统内 → 运维 | Port 多 worker | 待确认/待设备外置或共享存储；与部署形态绑定 |
| P7 | 视需求 | 向量检索 | 依赖 P3 与知识库场景 |

### 目录结构备注
- 根目录（概览）：`README.md`、`Dockerfile`、`requirements*.txt`、`pyproject.toml`、`docs/`（`guides/` 运维、`design/` 设计与变更日志）；密钥仅本机 `env.ps1` / 环境变量，**不**随仓库提供模板目录
- `src/app`：组合根与运行入口（HTTP/CLI）
- `src/port`：对外协议与事件边界
- `src/core`：内核编排 + 策略
- `src/modules`：assembly/model/tools 模块实现
- `src/platform_layer`：长期配置与静态资源
- `src/infra`：后续预留的外部基础设施实现







