Pompeii - Agent 通用模块架构设计 ver0.6
=========================================


## 文档说明

**定位**：在 [架构设计ver0.4.md](./archive/架构设计ver0.4.md) 的微内核框架与五道关卡模型之上，按**当前代码真值**与**近期演进方向**做整编修订，形成可指导实现的架构书。

**与 ver0.5 的关系**：ver0.5 内容全部保留；ver0.6 **合并**原《会话与双库长期记忆架构设计》、《长期记忆定义》、《开发状态与系统接口》三份卫星文档的核心架构内容，消除文档分散与交叉引用，使架构书成为**单一架构参考源**。

**与 ver0.4 的关系**：ver0.4 的 Loop 拓扑、三处理模块、AgentPort 边界、安全关卡语义**仍然有效**；ver0.5–ver0.6 **新增/强化**以下内容：

- **组合与注册表平面**：`app` 层作为唯一装配根，`config_loaders` 与各类 `*_registry` 的职责边界。
- **模型子系统**：OpenAI 兼容路径的**声明式路由**（配置驱动、多供应商默认根 URL，**不依赖**外部网关类库）。
- **长期记忆子系统**（ver0.6 合并强化）：`MemoryOrchestrator` + 双库架构、记忆记录类型、会话内调用时序、双库写入顺序、接口化定义。
- **系统接口清单**（ver0.6 合并新增）：HTTP/Kernel/Port/Module Protocol 接口总表、配置旋钮、可替换模块。
- **共享服务（对齐 ver0.4 第四节）**：提示词 / Skill / 信息缓存 / 长期存储 / 安全策略模块的实现映射。
- **资源守门与关卡⑤**：`resource_access` + `KNOWN_RESOURCE_IDS` 等与实现的对照表。
- **系统用户意图**：`/remember`、`/forget`、`/archive`、`/delegate` 等在 Core / Port 中的位置。
- **演进路线与债务**：与 `docs/design/STATUS.md`、`CHANGELOG` 对齐的优先级表述。
- **实现中间层图示**：§1.1 模块化总表；§1.4 运行时主链分步表；§1.5 启动期装配清单；§1.7 调用先后对照表；§1.8 `_run_loop` 决策表。

**版本快照**：实现线发布号以 `src/app/version.py` 为准（当前 `0.5.0`）；细节以仓库代码为准。


---

## 一、架构总览

### 1.1 微内核不变量

Agent 采用**微内核架构**。核心部负责 Loop 级路由与治理；**组装部、模型部、工具部**三模块同级；共享能力通过**窄接口**注入，而非在模块间随意穿透引用。**AgentPort** 仍是 Agent 与外部环境之间的**唯一协议边界**（`handle` / `emit`）。

#### 1.1a 模块化总表（按 `src/` 包，一览职责与连线）

下表**一行一个包或子系统**：**谁在里面**、**主要做什么**、**通常谁调谁**（不要求 Mermaid/图形渲染，纯文本即读）。

| 包 / 子系统 | 代表性组件（文件级） | 职责摘要 | 上游 → 下游（粗箭头） |
|-------------|----------------------|----------|------------------------|
| **L0 外部** | HTTP / CLI | 用户或对接系统 | → `app` 入口 |
| **`src/app` 运行时** | `http_runtime` · `cli_runtime` | 把传输形态变成 `PortInput` | 外部 → → **`port`** |
| **`src/app` 装配** | `composition` · `config_loaders/*` · `*_registry` · `validate_resource_configs` | 启动时读 YAML、解析引用、**new** 出 Core/Port/模块 | `platform_layer` → → **Core / Port / modules / Memory / RAC** |
| **`src/platform_layer`** | `resources/config/*.yaml`、数据路径 | 静态配置与资源位置 | → `config_loaders` |
| **`src/port`** | `GenericAgentPort` · `request_factory` · `intent_parser` · `events` · `HttpEmitter` | **唯一边界**：`handle` / `emit`；待确认/待设备状态 | app → → **Core**；出向 → 外部 |
| **`src/core`** | `AgentCoreImpl` · `SessionManager` · `policies/*` · `user_intent` | Loop、会话写守门、策略岔路 | Port → → **assembly / model / tools** |
| **`src/core/memory`** | `MemoryOrchestrator` | 长期记忆编排 | **composition 注入** → Assembly 检索 / Core 侧引用 |
| **`src/modules/assembly`** | `AssemblyModuleImpl` · `openai_user_content` · `context_isolation` · `token_budget`… | 构建 Context、工具回流格式化 | **Core 调** → Memory / RAC /（不直接调 Port） |
| **`src/modules/model`** | `ModelModuleImpl` · `openai_provider_route` · `openai_sse`… | 一拍 `ModelOutput` | **Core 调** → **infra** HTTP 栈 |
| **`src/modules/tools`** | `ToolModuleImpl` · `builtin_handlers` · `mcp_bridge` · `http_url_guard`… | 执行 tool_call | **Core 调** → MCP / 本地 handler / **infra** |
| **`src/infra`** | `SqliteSessionStore` · `SqliteDualMemoryStore` · `model_http_client_pool` · `mcp_stdio_bridge`… | 持久化、出网、子进程 MCP | 被 **SessionManager / Memory / model / tools** 使用 |

**ASCII 依赖（装配 + 请求，两行记死）**：

```
【启动一次】platform_layer/*.yaml → validate → config_loaders → *_registry → composition.build_core/build_port
              → AgentCoreImpl + GenericAgentPort + Assembly + Model + Tools + MemoryOrchestrator + RAC

【每次请求】外部 → http_runtime|cli_runtime → GenericAgentPort → AgentCoreImpl
              ⇄ AssemblyModuleImpl ⇄ ModelModuleImpl ⇄ ToolModuleImpl
              → SessionStore / Memory / httpx池 / MCP（infra）
```

**读表**：**装配链**与 **请求链** 与上表最后一列一致；会话权威在 **`SessionManager` → `SqliteSessionStore`**；记忆权威在 **`MemoryOrchestrator` → 双库 infra**。

#### 1.1b 纵向责任栈 L0～L8（一页纸摘要）

```
L0 外部 → L1 http_runtime/cli_runtime → L2 GenericAgentPort
       → L3 request_factory + intent_parser → L4 AgentCoreImpl + SessionManager + 注入策略
       → L5 _run_loop 节拍 → L6a assembly · L6b model · L6c tools
       → L7 共享策略与配置已实例化对象 · L8 infra 持久化与网络
```

**与后续小节**：**§1.4** 为 **请求链分步表**；**§1.5** 为 **装配链清单**；**§1.7～1.8** 为 **Loop 调用先后表 + 决策表**。

### 1.2 数据与资源域（为何总览图里看不到单独的「资源区」）

ver0.4 **第五节**写的是 **资源访问规则**（读写谁守门、敏感度分级），并不是指代码里有一个名叫「资源部」的进程；在 **第四节共享服务**里，与「数据」相关的主要是 **信息缓存（会话）**、**长期存储（跨会话）** 等，由 **SessionStore / MemoryOrchestrator / 各类 YAML 配置** 承载。

ver0.5 总览图把下面整块收成 **「配置 + 实现 + 装配」**，避免与 **三处理模块** 并列时再画第四根柱子，因此**没有单独标一块「资源区」**——**不等于**没有资源模型：

- **关卡⑤（资源访问）**：逻辑上贯穿读写；实现上集中在 **`ResourceAccessEvaluator` + `resource_access.yaml` / `resource_index.yaml` + `KNOWN_RESOURCE_IDS`**，由组装、工具、记忆路径在**读/写前**查询。
- **物理数据**：会话在 **SessionStore**；长期记忆在 **双库（标准主数据 + 向量投影）**；静态配置在 **platform_layer**。它们属于 **数据面**，与 **控制面**（Core Loop）分层展示更清晰。

若需要与 ver0.4 **完全同构的条文级**「四条规则 + 敏感度表」，见下文 **§6.3** 的对照复述；全文仍以 [架构设计ver0.4.md](./archive/架构设计ver0.4.md) **第五节、第六节之关卡⑤** 为准。

### 1.3 组合平面（ver0.5 新增强调）

**单一装配入口**：`app/composition.py` 的 `build_core` / `build_port` 负责把 **SessionStore、KernelConfig、Assembly、Model、Tools、Security、Guard、MemoryOrchestrator、ResourceAccess、Loop/Tool 策略** 接线为可运行的 `AgentCoreImpl`。

**配置加载**：`app/config_loaders/*` 从 `platform_layer/resources/config/*.yaml` 读取结构化配置；**校验**（如 `validate_resource_configs`）在装配早期执行，避免运行期静默错误。

**解析注册表**：`app/*_registry.py`（session_store、memory_store、embedding、guard、mcp、loop_policy、tool_policy 等）把 **YAML 中的字符串引用**（如 `builtin:sqlite`、`entrypoint:...`）解析为**可调用实现**。原则：**core/modules 不直接读 YAML 路径**；由 app 注入依赖。

该平面使「同一套 Core 契约」可对接不同存储后端、不同嵌入实现、不同 MCP 桥，而无需修改内核循环代码。


### 1.4 实现逻辑：运行时主链（分步表）

在 **§1.1a** 包边界之上，把 **一次 `handle` → `emit`** 拆成**有序步骤**；**「下一步」**列给出自然后继（**tool 执行成功** 则回到 **Loop 再 `model.run`**）。确认/设备二次请求见 **§1.7**。

| 步序 | 阶段 | 所在包 / 组件 | 动作 | 下一步 |
|------|------|----------------|------|--------|
| 1 | 入口 L1 | `app` · `http_runtime` / `cli_runtime` | 收到 HTTP/CLI，构造 `PortInput` | 2 |
| 2 | Port | `port` · 解析 | `PortInput` 反序列化 | 3 |
| 3 | Port | `port` · `request_factory` | 生成 `AgentRequest`（含 `request_id`） | 4 |
| 3′ | （可选） | `port` · `intent_parser` | 得到 `UserIntent`，可走 Core **短路**（不归入下列普适步序） | 视意图 |
| 4 | Port | `GenericAgentPort` · `handle` | 调用 `Core.handle` | 5 |
| 5 | Core | `SessionManager` | `get_or_create_session` | 6 |
| 6 | Core | `AgentCoreImpl` | 追加 user 或处理意图早段 | 7 |
| 7 | Core → Assembly | `build_initial_context` | 入口 | 8～13 |
| 8 | Assembly | — | 读 `Session.messages` | 9 |
| 9 | Assembly → Memory | `MemoryOrchestrator` | 按 `memory_policy` 检索 | 10 |
| 10 | Assembly | — | 合并 system/user、Skill、提示词 | 11 |
| 11 | Assembly | `context_isolation` | 关卡② 分区 | 12 |
| 12 | Assembly | `openai_user_content` | 多模态预处理 | 13 |
| 13 | Assembly | `token_budget` 等 | 裁剪，得到 **Context** | 14 |
| 14 | Core Loop | `_run_loop` | 每轮开始 | 15 |
| 15 | Core → Model | `model.run` | 传入 `session, context` | 16～20 |
| 16 | Model | — | 渲染 OpenAI `messages` 载荷 | 17 |
| 17 | Model | `openai_provider_route` | URL / model / headers | 18 |
| 18 | Model → infra | `httpx` + 池 / 熔断 / 限流 | Chat Completions | 19 |
| 19 | Model | SSE 或 JSON | 聚合为 **`ModelOutput`** | **20** |
| 20 | 分支 | `ModelOutput` | **A. 文本** 见下续表「text 出口」；**B. tool_call** 见下续表「tool 出口」 | — |
| 24 | Port | — | 任意 `AgentResponse` → 映射 **`PortEvent[]`** | 25 |
| 25 | Port | `emit` / CLI | 输出到外部 | （结束） |

**续表：text 出口（接步 20-A）**

| 步序 | 所在 | 动作 | 下一步 |
|------|------|------|--------|
| T1 | Assembly | `format_final_reply` | T2 |
| T2 | Core → `SessionStore` | 写 assistant | T3 |
| T3 | Core → Port | `AgentResponse` ok | 上表 **步 24** |

**续表：tool 出口（接步 20-B）**

| 步序 | 所在 | 动作 | 下一步 |
|------|------|------|--------|
| K1 | Core | `tool_policy` / `loop_governance` / `guard` | K2 |
| K2a | 分支 | **需确认或设备** → `AgentResponse` 待定 | 上表 **步 24**（等待下次请求） |
| K2b | 分支 | **允许执行** | K3 |
| K3 | Core → Tools | `execute(tool_call)` | K4 |
| K4 | Tools | builtin / MCP / 路由 + `http_url_guard` | K5 |
| K5 | Tools | 返回 `ToolResult` | K6 |
| K6 | Core | 净化、工具输出规则扫描 | K7 |
| K7 | Core → Store | 写 tool 消息 | K8 |
| K8 | Assembly | `apply_tool_result` | K9 |
| K9 | Core | **`_run_loop` 下一轮**（回到主表 **步 14**） | 主表 14 |

**说明（按平面，便于与代码对照）**：

| 平面 | 运作方式（做什么 / 不做什么） |
|------|------------------------------|
| **L1 app 入口** | 只负责 **传输绑定**：HTTP 体 → `PortInput`，或 CLI 行 → 同一套输入类型；**不**进入 Loop。 |
| **L2～L3 Port** | **`handle`**：解析 → `RequestFactory` 生成 **`AgentRequest`**（含 `request_id`）；`intent_parser` 可得到 **`UserIntent`**，供 Core **短路**（归档、delegate 等）。**`emit`**：把 **`AgentResponse`** 编成 **`PortEvent`** 列表。**不**改会话存储；**待确认 / 待设备** 字典在 Port 内（进程内语义）。 |
| **L4 Core 外壳** | **`SessionManager`**：按 `user_id/channel` **取或建** `Session`；**追加消息**、切状态、触发归档等 **必经** 此层。**策略对象**为 **注入的函数/registry**，Core 在岔路口调用，不内嵌业务规则全文。 |
| **L4 策略** | **读**当前 `ToolCall` / 文本 / 会话统计，**返回**枚举决策（允许、确认、拒绝、终止循环等）；**不**执行工具、**不**调模型。 |
| **`_run_loop`（L5）** | **唯一节拍器**：每一轮先拿 **最新 context**，再 **`model.run`**；视输出走 **text 出口** 或 **tool 岔路**；满足终止条件则 **`AgentResponse`** 返回 Port。 |
| **组装部（L6a）** | **被 Core 调用**三个接口（见 §1.6）；**不**自行循环、**不**直接 `emit`。 |
| **模型部（L6b）** | **`run(session, context)` → `ModelOutput`**（`text` 或 `tool_call` **二选一**）；内部完成 HTTP/SSE、解析；**不**写会话。 |
| **工具部（L6c）** | **`execute` → `ToolResult`**；**`resolve_device_request`** 仅构造设备请求描述，**真正下发**由 Core → Port `emit`。 |
| **L6 共享服务 / infra** | **被动**应答：被组装/模型/工具 **拉取或写入**；会话 **权威写入**仍由 Core 在策略通过后落库。 |

### 1.5 实现逻辑：启动期组合链（清单式）

与「单次请求」不同，**装配**仅在进程启动执行：读 YAML → 校验 → loader → registry → `build_core` / `build_port`。下列与 `app/composition.py` **大致同序**（非每个 import 穷尽）。

**总顺序（一行）**  
`platform_layer/*.yaml` → `validate_resource_configs` → **下表 loaders** → **下表 registries** → `composition.build_core` →（`AgentCoreImpl` + 三模块 + 依赖）→ `build_port` → `GenericAgentPort`（持有 Core）。

**A. `app/config_loaders`（读配置成内存对象）**

| 典型 loader 模块 | 主要 YAML / 作用 |
|------------------|------------------|
| `kernel_config_loader` | `kernel_config.yaml` |
| `runtime_config_loader` | `runtime.yaml` |
| `model_provider_loader` | `model_providers.yaml` |
| `tool_registry_loader` | `tools.yaml` |
| `skill_registry_loader` | `skills.yaml` |
| `prompt_config_loader` | `prompts.yaml` |
| `security_policy_loader` | `security_policies.yaml` |
| `resource_index_loader` / `resource_access_loader` | `resource_index.yaml` · `resource_access.yaml` |
| `memory_policy_loader` | `memory_policy.yaml` |
| `storage_profile_loader` 等 | 存储相关配置 |

**B. `app/*_registry`（把字符串引用变成可调用实现）**

| registry 方向 | 解析内容示例 |
|----------------|--------------|
| `session_store_registry` | `builtin:sqlite` → `SqliteSessionStore` |
| `memory_store` / `embedding` | 双库、嵌入后端 |
| `guard_model_registry` / `guard_evaluator_registry` | 守卫 |
| `mcp_bridge_registry` | MCP 桥 |
| `loop_policy_registry` / `tool_policy_registry` | 循环与工具策略引擎 |

**C. `composition` 产出（运行实例）**

| 产出 | 说明 |
|------|------|
| `AgentCoreImpl` | 注入 SessionManager、三模块、策略、Guard、Memory、RAC… |
| `AssemblyModuleImpl` / `ModelModuleImpl` / `ToolModuleImpl` | 与注册表解析结果绑定 |
| `GenericAgentPort` | 持有 Core + `RequestFactory` + Emitter |

**原则**：**运行时热路径**（§1.4）不反复读盘；配置变更需**重启**或未来显式热重载（当前主线以前者为准）。


### 1.6 各模块运作方式（接口节拍与数据流）

以下与 `modules/*/interface.py` 及 `AgentCoreImpl` 行为对齐：**Core 驱动循环，三模块只响应单次调用**。

#### 组装部 `AssemblyModule`

| 方法 | 何时被调 | 运作内容（逻辑顺序摘要） | 产出 |
|------|----------|--------------------------|------|
| `build_initial_context` | 每轮用户消息进入 Loop **开头**（及确认/设备回流后重新进入 Loop 时） | 读 `Session.messages`；按需 **MemoryOrchestrator** 检索；合并 **system/user**（提示词、Skill、关卡② **context_isolation**）；**openai_user_content** 预处理多模态；**token/字符预算**裁剪 | **Context**（模型部消费的视图对象） |
| `apply_tool_result` | 某次 **`tools.execute` 成功** 且 Core 已将 tool 消息写入会话 **之后** | 将 `ToolResult` **格式化**为可进上下文的文本；按需套 **tool_result 分区**（关卡②）；与 **tool_first** 等策略兼容的回流形状 | **更新后的 Context**（供下一轮 `model.run`） |
| `format_final_reply` | 模型返回 **`ModelOutput.kind == "text"`** 即将回复用户前 | 对最终字符串做平台化格式化（长度、片段等） | **reply 文本**（再由 Core 写 assistant 消息） |

**原则**：组装部是 **Context 的唯一构建者**；**不**调用 `model.run`、**不**执行 `tool_call`（若需 LLM 摘要等内部能力，应通过 **注入的协作对象** 或回调，避免绕开 Core）。

#### 模型部 `ModelModule`

| 节拍 | 运作内容 | 产出 |
|------|----------|------|
| **`run(session, context)`** | 将 `context` 编成 **OpenAI Chat** 载荷；**`openai_provider_route`** 定 URL/model/头；**httpx** + **池 / 熔断 / 限流**；解析 **非流式或 SSE 流式** 聚合为 **`ModelOutput`** | `text`：**最终可见回复草稿**（仍经组装 `format_final_reply`）或 `tool_call`：**结构化调用** |

**原则**：一次 `run` = **模型的一拍输出**；**会话写回**由 Core 完成（assistant / tool 角色消息）。

#### 工具部 `ToolModule`

| 方法 | 运作内容 | 产出 |
|------|----------|------|
| `execute` | 按 `ToolCall.name` **查注册表** → 本地 handler / **MCP** / 设备路由；命中 **network_policy、http_url_guard** 等关卡④；返回原始或结构化 **`ToolResult`** | `ToolResult`（含 `source` 供信任档） |
| `resolve_device_request` | 若该 tool 映射为 **设备能力**，构造 **`DeviceRequest`**；**不**等待设备 | `DeviceRequest \| None` |

**原则**：工具部 **只执行与声明网络策略**；**确认门 / 白名单 / 预算** 在 Core；**结果净化**在 Core 写入前 + 组装 `apply_tool_result` 内继续结构化呈现。

#### Core `AgentCoreImpl`（浓缩）

- **驱动顺序**：`build_initial_context` → `model.run` →（若 tool）策略链 → `execute` 或 `emit confirmation/device` → 写会话 → `apply_tool_result` → 再 `model.run` … 直至 `text` 或终止 reason。
- **独占写会话路径**：用户/assistant/tool 消息追加、归档状态迁移，均在 Core（或其调用的 `SessionManager`）内完成，保证 **关卡③ 与审计点** 单一。

#### Port `GenericAgentPort`（浓缩）

- **入向**：多种 `PortInput` → 统一 **`AgentRequest`**。
- **出向**：**`AgentResponse`** → 一种或多种 **`PortEvent`**（`reply` / `confirmation` / `device_request` / `error` / `delegate` …）。
- **跨请求状态**：确认 id、设备挂起等 **仅存 Port**；Core 侧 **无** 全局「待确认」单例。


### 1.7 调用先后对照表（替代时序图）

按**时间顺序**列出「**从 → 到**」与**消息 / 动作**；列与 **§1.1a** 各包对应。**同一序号**可视为一次同步调用链上的相邻环节。

| 序 | 从 | 到 | 动作 / 数据 |
|----|----|----|-------------|
| 1 | 外部 | `app` 入口 | 原始 HTTP / CLI 输入 |
| 2 | `app` | `port` | `PortInput` |
| 3 | `port` | `request_factory` | 构造 `AgentRequest` |
| 4 | `port` | `core` · `AgentCoreImpl` | `handle(request)` |
| 5 | `core` | `SessionManager` / `Store` | `get_or_create`，读会话 |
| 6 | `core` | `assembly` | `build_initial_context` |
| 7 | `assembly` | `MemoryOrchestrator` | `retrieve`（按 `memory_policy`） |
| 8 | `assembly` | `core` | 返回 **Context** |
| 9 | `core` | `model` | **`_run_loop` 内** `run(session, context)` |
| 10 | `model` | `openai_provider_route` | URL / model / headers |
| 11 | `model` | `infra` · httpx 栈 | Chat Completions（SSE 或 JSON） |
| 12 | `model` | `core` | **`ModelOutput`**（text 或 tool_call） |
| 13a | `core` | `assembly` | 若 text：`format_final_reply` |
| 13a′ | `core` | `SessionStore` | 写 assistant |
| 13b | `core` | `policies` 注入 | 若 tool_call：tool / loop / guard 决策 |
| 13b′ | `core` | `port` | 若需确认/设备：`AgentResponse` 待定 → `emit` |
| 13b″ | `core` | `tools` | 若允许：`execute` |
| 14 | `tools` | builtin / MCP | 执行，经网络策略 |
| 15 | `tools` | `core` | `ToolResult` |
| 16 | `core` | `core` | sanitize 工具输出 |
| 17 | `core` | `SessionStore` | 写 tool 消息 |
| 18 | `core` | `assembly` | `apply_tool_result` → 新 Context |
| 19 | `core` | `model` | **下一轮** `run`（回到序 9） |
| 20 | `core` | `port` | `AgentResponse` |
| 21 | `port` | 外部 | `PortEvent[]` · `emit` |

**要点**：

- **首轮**必有 **序 6～8**；**仅工具回流**时通常 **不再**从 `build_initial_context` 整段重跑，而是 **序 18** 后接 **序 9**（与实现一致）。
- **`UserIntent` 短路**（归档、delegate、remember…）可在 **序 4 之后早段**完成，未必经过 **序 9～19** 全链。
- **第二次请求**（确认 / 设备结果）：`port` 调 `handle_confirmation_approved` / `handle_device_result`，再从 **`core`** 与 **序 9** 附近汇合。


### 1.8 `_run_loop` 内决策（表 + 文字回流）

| 步骤 | 条件 / 动作 | 结果 |
|------|-------------|------|
| 1 | `loop_governance`：超限、重复 tool、预算等 | **终止** → `AgentResponse(reason)` |
| 2 | 否则 `model.run` | 得到 `ModelOutput` |
| 3 | **`kind == text`** | `format_final_reply` → 写 assistant → **`AgentResponse` ok** → 结束 run |
| 4 | **`kind == tool_call`** | 进入 `tool_policy_decide` |
| 5 | 策略：**拒绝 / 错误** | **`AgentResponse` error** → 结束 run |
| 6 | 策略：**需确认** | Port `pending` + confirmation 事件 → **结束本轮 run，等下次请求** |
| 7 | 策略：**设备** | `resolve_device_request` + device 事件 → **结束本轮 run，等 device_result** |
| 8 | 策略：**允许执行** | `tools.execute` → 工具输出扫描 → 写 tool 消息 → `apply_tool_result` |
| 9 | **回流** | 回到 **步骤 1**（再经治理检查后 `model.run`），直到步骤 3 或 5 |

**文字回流（与上表步 9 同义）**  
`apply_tool_result` 完成后 **不**结束 `handle`，而是 **再次进入** `_run_loop` 顶部：先 **治理检查**，再 **`model.run`**，形成「工具 → 模型 → …」闭环，直到产出 **text** 或 **终止 reason**。


---

## 二、分层与依赖法则

| 层 | 路径（约定） | 职责 | 禁止 |
|----|----------------|------|------|
| **port** | `src/port` | 对外协议、事件类型、`GenericAgentPort` | 实现具体模型/工具业务 |
| **core** | `src/core` | 编排、会话抽象、策略组合、记忆/资源**接口类型** | 直接依赖具体 HTTP 客户端或 YAML 路径 |
| **modules** | `src/modules/*` | assembly / model / tools 的可替换实现 | 反向依赖 app；避免隐式全局配置 |
| **app** | `src/app` | 组合根、loaders、registry、HTTP/CLI 入口 | 塞进与装配无关的领域逻辑 |
| **platform_layer** | `src/platform_layer` | **静态**配置与资源路径 | 运行业务逻辑、访问密钥明文 |
| **infra** | `src/infra` | SQLite、HTTP 池、嵌入客户端、MCP 桥等 | 冒充 core 的编排职责 |

**依赖方向（理想）**：`port → core → modules`；`app` 向 `core/modules` **注入**实现；`infra` 仅被 `app` 或 `modules` 通过接口引用。**platform_layer** 只被 `app/config_loaders` 读取。

当前仓库仍可能存在个别历史耦合点；新代码应遵守上述方向，旧债在 `STATUS.md` 中跟踪收敛。


---

## 三、核心运行流程（与实现挂载点）

与 ver0.4 一致的主线：**组装 → 模型 →（tool_call 则）工具 → 组装追加 → 再模型**，由 Core 的 Loop 治理（`max_loops`、`max_tool_calls_per_run`、重复 `tool_call` 指纹等）约束。**更细的「谁先谁后、谁不调谁」** 见 **§1.4 分步表**、**§1.6 接口表**、**§1.7 调用先后表**、**§1.8 决策表**。

**ver0.5 补充的挂载点**：

1. **组装备注**：`AssemblyModuleImpl` 可持有 `MemoryOrchestrator` 与 `ResourceAccessEvaluator`；在构建送入模型的上下文时，按 `memory_policy.yaml` **检索并注入**长期记忆片段；按 `resource_access` 与工具侧策略处理 **多模态 URL** 等。
2. **模型调用**：主 Chat 路径通过 `openai_provider_route` 解析 `ModelProvider.params`（`base_url` / `model` / `model_id` 前缀推断 / `chat_completions_path` / `extra_headers` 等），再经 **熔断、限流、连接池**（`infra`）发出 HTTP 请求。
3. **工具结果回注**：Core 在写入会话前对工具输出做 **安全净化与注入模式扫描**（与 `security_policies` 对齐）；组装部对 `tool_result` 做 **关卡② 分区封装**（与 `ToolResult.source` 信任档映射一致）。
4. **系统意图**：用户消息经 Port 解析为 `UserIntent`（如 `SystemRemember`、`SystemForget`、`SystemArchive`、`SystemDelegate`）；Core 在常规 Loop 外或 Loop 内分支处理，避免与普适对话混淆。

**长期记忆读路径**：优先 **组装部注入**（每轮自动、策略驱动）；**`search_memory` 工具**提供模型主动检索的第二入口（详见 **§九 长期记忆子系统**）。

**长期记忆写路径**：系统指令（如 `/remember`）或归档晋升等经 **MemoryOrchestrator** 协调：标准库权威落库 → 切块 → 向量投影（嵌入经模型部 OpenAI 兼容 `embeddings` 或内置 hash 等）。


---

## 四、处理模块（实现映射）

### 4.1 组装部

**设计职责**（继承 ver0.4）：Context Window 的**唯一构建者**；关卡② 上下文隔离；工具结果格式化与预算裁剪。

**当前实现要点**：

- **OpenAI 用户内容出口**：`openai_user_message_payload` / `apply_user_parts_preprocessing` 统一 user 多模态与预处理（与关卡⑤、URL 守卫联动）。
- **上下文隔离**：`context_isolation` 与 `kernel.context_isolation_enabled` 对齐；历史与 system 侧分区一致。
- **Token/字符预算**：启发式 `assembly_approx_context_tokens` + 消息条数/字符上限配置；tiktoken/LLM 摘要为可选增强。
- **记忆**：若注入 `MemoryOrchestrator`，按策略查询并写入记忆分区；资源门拒绝时降级为占位或省略。

### 4.2 模型部

**设计职责**（继承 ver0.4）：主推理、流式输出、tool_call 解析；辅助能力（嵌入、归档摘要、守卫等）。

**当前实现要点**：

- **声明式路由**（`openai_provider_route`）：单一 OpenAI Chat Completions 适配面；**配置驱动**区分供应商，避免为每家写死分支；未知 `model_id` 前缀必须显式 `base_url`。
- **稳定性**：熔断器、速率限制、可配置超时与连接池行为（`infra`）。
- **流式**：SSE 累积与 tool_calls 解析路径与 ver0.4 设计一致；原生 chunked 直出等仍可扩展。

### 4.3 工具部

**设计职责**（继承 ver0.4）：执行 tool_call；关卡④ 网络策略、信任分级、结果形态。

**当前实现要点**：

- **内置处理器 + 插件发现**：`builtin_handlers` 与 entrypoint 注册；MCP stdio 桥可选。
- **网络策略**：`tools.yaml` 中 `network_policy` 与 `http_url_guard` 等，与 kernel allowlist / 资源校验对齐。
- **设备执行器**：仍属演进项（见 STATUS）；架构上保持「工具部 → Core → Port.emit(device_request)」的漏斗形状。


---

## 五、共享服务（与 ver0.4 第四节对齐）

**定义**（继承 ver0.4）：**不参与 Agent Loop 的步骤流转**，由处理模块在各自子步骤中**按需读取或经窄端口写入**；与「组装→模型→工具」并列的**控制面路由**不同，共享服务是**数据与规则供给层**。

下列 **5.1～5.5** 与 [架构设计ver0.4.md](./archive/架构设计ver0.4.md) **第四节**条目一一对应；**「实现映射」** 列为本仓库当前真值。

### 5.1 提示词配置

| 维度 | ver0.4 | 当前实现映射 |
|------|--------|----------------|
| 生命周期 | 系统级，基本不变 | `platform_layer/resources/config/prompts.yaml`，启动加载 |
| 内容 | System 模板、人格/规则、输出约束等 | `prompt_profiles` / `user_prompt_profiles`、`prompt_vars`、`tool_result_render`、`tool_first_tools` 等 |
| 消费者 | 组装部 | 组装路径组上下文；模型部侧按 provider 合并模板与策略（`prompt_strategy_ref` 等） |
| 缓存 | （未单列） | `infra/prompt_cache.PromptCache`（如启用） |

### 5.2 Skill 注册表

| 维度 | ver0.4 | 当前实现映射 |
|------|--------|----------------|
| 内容 | (1) 描述 → Context (2) 可执行函数 (3) Schema/权限/沙箱 | **(1)** `skills.yaml` 中 `items[]`（`summary`/`content` 等）→ 命中 `session.skills` 后注入 system 的 `active_skills` 区块。**(2)(3)** 主线由 **Tool 注册表**（`tools.yaml`）承担：工具 handler、参数 schema、网络策略等与 **tool_call** 执行链绑定 |
| 消费者 | 组装（描述+Schema）、工具（函数+配置） | 组装读 Skill；工具部按 **tool 名** 分发；二者通过 **id 引用** 与配置校验（`session.skills` 须在 `skills.yaml` 存在）衔接 |
| 与 Tool 关系 | Skill ≠ Tool | 本仓库：**Skill 偏「可编排的知识/能力包描述」**；**Tool 偏原子调用**；复杂自动化可走 Workflow/多 tool 组合（ver0.4 思路不变） |

### 5.3 信息缓存

| 维度 | ver0.4 | 当前实现映射 |
|------|--------|----------------|
| 生命周期 | 会话级 | `Session` + `SessionStore`（默认 `SqliteSessionStore`） |
| 内容 | `messages`、多模态原始等 | `Session.messages`、`Part`（text/image_url/tool_call/tool_result…） |
| 读 | 组装部 | `AssemblyModuleImpl` 经会话快照组装 |
| 写 | 核心每轮守门写入 | `AgentCoreImpl` 路径追加 user/assistant/tool，工具结果净化后经同一管道写入 |

### 5.4 长期存储

| 维度 | ver0.4 | 当前实现映射 |
|------|--------|----------------|
| 生命周期 | 持久级、跨会话 | **会话归档**：`session_archives`（规则摘要、可选 `llm_summary_*`）。**长期记忆**：`MemoryOrchestrator` + SQLite 双库（标准主数据 + 向量投影），策略见 `memory_policy.yaml` |
| 检索 | 向量 + BM25 混合等 | **部分落地**：FTS / 向量相似度 / RRF 等（见 `core/memory`）；GraphRAG、独立向量服务为后续项 |
| 嵌入 | 调模型部 embed | `builtin:hash` 或 **`builtin:openai_compatible`**（`/v1/embeddings`），由 registry 注入 |
| 可插拔 | 存储引擎可换 | SessionStore / MemoryStore / Embedding 经 **app registry** 替换实现 |

### 5.5 安全策略模块

| 维度 | ver0.4 | 当前实现映射 |
|------|--------|----------------|
| 定位 | 横切面规则库，各关卡查询 | `security_policies.yaml` + `resource_index.yaml` 选取 **active** policy |
| 关卡①～⑤ 与守卫 | 规则清单见 ver0.4 原文 | ① 多在 Port/入口；② 组装 `context_isolation`；③ kernel tool 策略 + 确认流；④ `tools.network_policy`、`http_url_guard`、工具结果净化；⑤ `resource_access` + `KNOWN_RESOURCE_IDS`；守卫经 **guard_evaluator** / **guard_model** registry 注入 |

---

## 六、横切子系统（治理与资源守门补充）

> **与第五节关系**：**提示词 / Skill / 会话热数据 / 长期域 / 安全策略条文** 已在 **第五节「共享服务」** 按 ver0.4 第四节结构展开。本节补充 **内核与会话治理**、**资源访问条文与缺口**、**会话状态与归档链路** 等，避免把「共享服务」与「治理参数」混在同一列表里。

### 6.1 核心与会话治理配置

- **KernelConfig**（`kernel_config.yaml`）：`core_max_loops`、`max_tool_calls_per_run`、`tool_allowlist`、`tool_confirmation_required`、`context_isolation_enabled`、`delegate_target_allowlist`、归档 LLM 摘要开关、`tool_policy_engine_ref`、`loop_policy_engine_ref`、`prompt_strategy_ref` 等。
- **SessionConfig**（`session_defaults.yaml` + `ConfigProvider`）：每会话 `model`、`skills`、`limits` 等。
- **Tool 注册表**（`tools.yaml`）：与 **§5.2** Skill 配合，承载可执行工具与网络策略；详见第五节表格。

### 6.2 安全策略注册表（激活与注入）

`security_policies.yaml` + `resource_index.yaml` 选择激活策略；**守卫评估器**与**守卫模型**引用经 registry 注入 Core。关卡③④ 的细则仍以 ver0.4 **第六节**为准；**规则清单与关卡对应**见 **§5.5**。

### 6.3 资源访问（关卡⑤ 实现子集）

**与 ver0.4 第五节的对照（条文摘要，便于检索「资源区」语义）**：

| 规则（ver0.4） | 含义 |
|----------------|------|
| 规则 1 | 处理模块间 Loop 步骤通信 → **经核心路由** |
| 规则 2 | 资源**写** → **经核心守门** |
| 规则 3 | 低/中敏感资源**读** → **直连 + 事件/审计上报**（实现程度因资源而异） |
| 规则 4 | 高敏感资源**读** → **经核心审批**（主线仍为规划项，见下） |

**敏感度分级（设计目标，ver0.4）**：

| 级别 | 典型资源 | 访问策略（设计） |
|------|----------|------------------|
| 低 | 提示词、Skill 注册表 | 直连 + 上报 |
| 中 | 信息缓存（会话 messages） | 直连 + 更细审计 |
| 高 | 长期私密记忆、凭证等 | 审批 / 强守门 |

**当前代码映射（真值）**：

| ver0.4 概念 | 当前落地 |
|-------------|----------|
| 资源读写分级 | `resource_access.yaml` profile + `ResourceAccessEvaluator` |
| 配置防呆 | `KNOWN_RESOURCE_IDS` 与 loader 校验 |
| 多模态 URL | 资源键 `multimodal_image_url` 与 `http_url_guard` 联动 |
| 长期记忆资源 | 显式资源 id，读写经 Orchestrator + 评估器 |

**未完整落地**（规划项）：**通用资源目录**、高敏感读「**人工审批**」流、完整审计流水线——与 `STATUS.md` 中「关卡⑤ 全覆盖仍弱于 ver0.4 愿景」一致；因此第五版**用表格写清映射与缺口**，而不在总览图里虚构一块已完成的「资源区」图示。

### 6.4 会话状态与归档链路（补充）

- **SessionStore**：SQLite 为主（`SqliteSessionStore`）；会话消息、状态、统计（**热数据**见 **§5.3**）。
- **归档触发**：`ARCHIVED` → `session_archives`（规则摘要 + 元数据）；可选 **异步 LLM 摘要**（`ArchiveLlmSummaryBinding`）（**持久摘要**亦与 **§5.4** 长期域相关）。
- **与长期记忆**：归档内容晋升到记忆标准库的策略见 `memory_policy` 与 Core 路径；细节见 **§九 长期记忆子系统**。


---

## 七、系统用户意图与 Port 事件

**意图解析**（`port/intent_parser` / `core/user_intent`）：将特定前缀指令从普适用户文本中剥离，形成结构化意图，供 Core 短路或旁路处理。

| 意图（示例） | 架构角色 |
|--------------|----------|
| 记住 / 忘记 | 触发 MemoryOrchestrator 写删；可能伴随确认与资源评估 |
| 归档 | 会话状态迁移 + 归档表 + 可选摘要 |
| Delegate | `AgentPort` 发出 `DelegateEvent`；**子 Agent 实例化**属部署侧；`delegate_target_allowlist` 约束 target |
| 确认流 | `emit(confirmation)` → 用户批准后 `handle_confirmation_approved`，不重复追加 user 消息 |

**事件类型**扩展时，应保持 **Port 对外契约**与 **Core 对内契约**分离：Core 只依赖稳定的数据结构，具体传输序列化在 Port/HTTP 层完成。


---

## 八、会话生命周期与数据模型

与 ver0.4 **第七节**一致：`ACTIVE` / `IDLE` / `ARCHIVED` / `DESTROYED`；消息 `Message` / `Part` 模型；Token 窗口与会话总预算分工不变。

**会话域**（`SessionStore` / `SqliteSessionStore`）：

| 概念 | 说明 |
|------|------|
| **会话域** | 当前对话状态：`Session` + `SessionStore`（含 `sessions`、归档摘要表等） |
| **长期域** | 跨会话可延续的记忆与知识，由标准库 + 向量库共同承载（见 **§九**） |

**状态转换**：`ACTIVE` ↔ `IDLE`（超时策略）→ `ARCHIVED`（显式触发）→ `DESTROYED`（规划中）。长期记忆项有独立 **`memory_id`** 与双库投影生命周期，与会话消息生命周期**解耦**；用户可跨会话延续记忆，而会话 id 可轮换。

**数据面分区**：

```
数据面（持久化）
┌──────────────────────┐      ┌────────────────────────────┐
│ 会话域                │      │ 长期域                      │
│ SessionStore         │      │ ┌──────────┐  ┌───────────┐ │
│ (SQLite 会话库)       │      │ │ 标准库    │  │ 向量库     │ │
│ sessions / archives  │      │ │ 主数据    │  │ 语义索引   │ │
└──────────────────────┘      │ └──────────┘  └───────────┘ │
                              └──────────┬─────────────────┘
                                         │
                              Memory Orchestrator（写协调）
```


---

## 九、长期记忆子系统

> 本节整合原《会话与双库长期记忆架构设计》与《长期记忆定义》的核心设计内容，作为记忆子系统的**单一架构参考**。

### 9.1 双库在架构中的位置

- **双库只属于长期域**；**会话域单独一套存储**。
- **Core 不直接连向量库**；通过**窄接口**连接 **Memory Orchestrator** 或其只读投影。
- **Assembly** 是「把长期检索结果写进上下文」的**首选挂载点**（自动注入）；**Tools** 是「模型主动要查再查」的**可选挂载点**（`search_memory`）。

### 9.2 标准库 vs 向量库：职责对照

| 维度 | 标准库 | 向量库 |
|------|--------|--------|
| **角色** | 权威（source of truth） | 派生索引（derivative） |
| **存什么** | `memory_id`、类型、`user_id`、`channel`、完整正文、信任度、`embedding_status` | 切片文本、向量、最小元数据（`memory_id`、`chunk_id`） |
| **擅长查询** | 主键、用户维度、时间范围、FTS/BM25 | 语义近邻（ANN） |
| **写入触发** | Orchestrator 策略通过后写入 | 标准库落库成功后投影（可异步） |
| **删除** | 逻辑删除 + 审计 | 按 `memory_id` 级联 |

**原则**：业务唯一真相以标准库为准；向量库丢数据或重建索引时，应能根据标准库 + 切块策略**重放**。

### 9.3 记忆记录类型

#### MemoryChunk（检索主单元）

面向 RAG / 混合检索的基本写入单位。

| 字段 | 说明 |
|------|------|
| `text` | 参与检索的正文 |
| `user_id` | 归属用户（分区键） |
| `channel` | 可选，按频道隔离 |
| `source_session_id` / `source_message_id` | 可选，追溯来源 |
| `trust` | `low` / `medium` / `high`，供组装打标签与关卡⑤ |
| `tags` | 可选过滤标签 |

#### UserPreference（用户偏好）

跨会话稳定的键值或短文本（`user_id` + `key` → `value`）。

#### Fact（事实陈述）

可验证陈述（`statement` + `confidence` + `evidence_ref`），便于冲突处理与高精度召回。

#### ArchiveLink（归档链接）

指向已归档会话的索引项（`session_id` + `archived_at` + `summary_excerpt`），避免重复存全量消息。

#### 与现有表的关系

- **`sessions` / `session_archives`** 仍属会话域；长期记忆通过 `ArchiveLink` 关联，避免混为一张大表。
- `storage_profiles.memory.path` 为双库 SQLite 路径；`store_ref` 仅对应旧线。

### 9.4 逻辑记忆项与双库映射

- 一条逻辑记忆项 → 标准库 **1 行**主记录（`memory_id` 全局唯一）
- 同一正文经切块 → 向量库 **N 条**向量（`chunk_id` 标识）
- 偏好/事实等结构化记录以标准库为主，仅需语义检索时才向量化

| ID | 用途 |
|----|------|
| `memory_id` | 全局唯一，标准库主键；向量元数据必带，用于回表 |
| `chunk_id` | 可选；同一 `memory_id` 下多切片时唯一 |
| `source_session_id` / `source_message_id` | 溯源至会话域 |

### 9.5 Memory Orchestrator 边界

**职责（必须）**：

1. **写入编排**：校验策略 → 写标准库 → 触发切块与向量索引（同步或入队）
2. **删除/撤回**：更新标准库状态 → 通知向量侧删除或标记不可检索
3. **重索引**：嵌入模型或切块策略变更时，按 `memory_id` 重算向量
4. **只读门面**：`retrieve_for_context` 内部并行查标准库（FTS）与向量库（ANN）→ 融合排序（RRF）→ 截断 Top-K

**非职责（避免膨胀）**：

- 不管理当前 Session 内消息顺序（属 `SessionManager`）
- 不替代模型选工具的业务逻辑
- 不在此层做最终安全裁决（护栏仍在 Core / Guard）

**配置归属**：

| 配置项 | 归属 |
|--------|------|
| 双库后端 ref、嵌入 ref | `memory_policy.yaml` 的 `dual_store_ref` / `embedding_ref` |
| 嵌入模型、向量维度 | `embedding_dim`；`builtin:openai_compatible` 时用 `embedding_openai` 块 |
| 切块大小、重叠 | `chunk_max_chars` / `chunk_overlap_chars` |
| 每用户召回条数 | `retrieve_top_k`、`rrf_k`、`rerank_max_candidates` |
| 双库文件路径 | `storage_profiles.memory.path` |

### 9.6 会话中的记忆调用逻辑（单次请求）

| 阶段 | 名称 | 与双库关系 |
|------|------|-----------|
| S0 | 请求进入 | Port 构造 `AgentRequest` |
| S1 | 会话解析 | `get_or_create_session` → 只读会话域 |
| S2 | 安全与策略 | 会话配置护栏 |
| S3 | 用户消息落会话 | `append_message` → 写会话域 |
| S4 | **长期检索（读）** | Assembly 内调 Orchestrator → 读标准库（FTS）+ 向量库（ANN） |
| S5 | 组装上下文 | 合并会话消息窗口 + 长期片段 |
| S6 | Loop | Model / Tools；可选 `search_memory` 工具再次检索 |
| S7 | 回复落会话 | `append_message` → 写会话域 |

**写长期域**不在每轮必经路径中；由显式意图 / 归档流水线 / 异步任务触发。

**S4 检索细部**：

1. 标准库路径：按用户拉取必注入数据（如偏好精确键）、FTS/BM25
2. 向量路径：query 编码 → ANN → 候选 `chunk_id` + score
3. 回表：用 `memory_id` 从标准库取权威正文与信任度；丢弃已 tombstone 项
4. 融合：RRF 合并 → 截断 Top-K → 输出给 Assembly

**Loop 内再检索**：推荐默认 S4 轻量检索 + `search_memory` 工具可选加深。

### 9.7 写长期域：双库顺序

**触发源**：

| 触发 | 说明 |
|------|------|
| 用户显式意图 | `/remember` → Orchestrator `ingest` |
| 归档策略 | 会话 `ARCHIVED` 后异步晋升 |
| 运营/批任务 | 重索引、全量重建向量 |

**写入顺序（强制）**：

```
1. 策略与去重（Orchestrator）
2. INSERT/UPDATE 标准库主记录 → 得到 memory_id
3. 切块 → 生成 chunk 列表
4. 嵌入 → 写向量库（附 memory_id, chunk_id）
5. 更新标准库 embedding_status = ready
```

**禁止**先写向量库后写标准库（会导致孤儿向量、无法回表）。步骤 4–5 允许异步；标准库可先标 `embedding_pending`，检索时过滤未就绪项。

### 9.8 接口化与代码位置

| 路径 | 内容 |
|------|------|
| `core/memory/ports.py` | `DualMemoryStore` = `StandardMemoryRepository` + `VectorMemoryIndex` Protocol |
| `core/memory/orchestrator.py` | `MemoryOrchestrator`（主线编排） |
| `core/memory/content.py` | 记录类型（dataclass） |
| `core/memory/protocol.py` | `LongTermMemoryStore`（旧线，主装配未用） |
| `app/memory_orchestrator_registry.py` | 双库 + 嵌入热插拔（`builtin:dual_sqlite` / `builtin:hash` / `builtin:openai_compatible`） |
| `infra/sqlite_dual_memory_store.py` | SQLite 双库实现（`memory_items` + `memory_fts` + `memory_vectors`） |

**协议能力（最小集）**：`put(record)` 写入/更新 → `search(query)` 检索 → `delete_user_data(user_id)` 合规删除。嵌入生成、切块策略、异步队列均属实现细节，不进入核心协议。

**配置约束**：`memory_policy.enabled=true` ⇒ `storage_profiles.memory.store_ref` 必须 `builtin:noop`，避免与双库共路径冲突（由 `resource_validation` 校验）。

### 9.9 质量闭环与待设计项

| 环节 | 做法 |
|------|------|
| 注入可控 | Top-K、score 阈值、按 `trust` 过滤低可信片段 |
| 可解释 | 附带来源 `memory_id` 供日志或 UI |
| 用户纠正 | `/forget` → Orchestrator tombstone + 删向量 |
| 评测 | 离线召回率；在线点踩关联 `memory_id` 降权或删除 |

**待设计**（不在实现中假定答案）：自动触发条件（归档？定时？容量？）、内容选择策略（全量 / LLM 摘要 / 事实抽取）、与合规的去重关系、向量管线失败重试频率。


---

## 十、容错、终止与观测

继承 ver0.4 **第八节**：模块内自愈（重试、Failover、熔断）、编排级错误回复、重复 `tool_call` 终止（`reason=repeated_tool_call`）。

- **request_id**（或等价关联 id）应贯穿日志，便于把 Port → Core → HTTP → 工具链路对齐。
- **测试**：`pytest` 覆盖核心策略、路由解析、记忆与组装关键路径；smoke 脚本验证最小闭环。

**观测**：当前以日志为主；未来可在 Port 层增加结构化 trace 出口，而不把观测逻辑塞进 Core 热路径。


---

## 十一、多模态与模型网关形态

**原则**（继承 ver0.4 第十节）：不在组装阶段过早销毁模态；API 载荷以 OpenAI content blocks 为**主互操作格式**。

**网关**：本仓库采取 **「自研声明式路由 + 单协议适配器」**，与业界「统一 LLM 网关」**思想对齐**，但**不绑定**任何第三方网关实现，以便控制依赖、审计面与密钥路径。

**安全**：图片 URL 等需过 **SSRF/主机基线** 与 **resource_access** 双重约束（与 `STATUS` 中关卡描述一致）。


---

## 十二、系统接口清单

> 本节整合原《开发状态与系统接口》的接口级内容，作为对外与对内接口的**单一索引**。

### 12.1 HTTP（实验性，FastAPI）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/health` | `ok` + `version` |
| GET | `/archives` | 查询用户归档列表（`user_id` 必填） |
| POST | `/input` | `kind`: `user_message` / `system_command` / `device_result`；返回 `events[]` |
| WS | `/ws` | 入站 JSON 与 `/input` 同构；逐条回传 `events[]` |

### 12.2 内核入口（`AgentCore`）

| 接口 | 作用 |
|------|------|
| `handle(AgentRequest)` | 主入口：追加 user → loop |
| `handle_confirmation_approved(request, tool_call)` | 确认后执行工具并续跑 |
| `handle_device_result(..., tool_result, tool_call_id?)` | 设备结果回注并续跑 |
| `list_archives_for_user(user_id, limit?)` | 归档列表 |

### 12.3 Port 边界

| 类型 | 作用 |
|------|------|
| `GenericAgentPort.handle(PortInput, user_id?, channel?, emitter?)` | 统一入口 |
| `PortEmitter.emit` / `HttpEmitter.dump` | 事件收集与输出 |
| `PolicyNoticeEvent` | 策略提示事件（如 `resource_approval_required`） |

### 12.4 模块 Protocol

| Protocol | 位置 | 职责 |
|----------|------|------|
| `AssemblyModule` | `modules/assembly/interface.py` | 构建上下文、工具回注、最终回复格式化 |
| `ModelModule` | `modules/model/interface.py` | `run` → `ModelOutput` |
| `ToolModule` | `modules/tools/interface.py` | `execute` → `ToolResult` |
| `SessionStore` | `core/session/session_store.py` | 会话 CRUD、归档列表 |
| `SessionManager` | `core/session/session_manager.py` | 会话生命周期 |
| `DualMemoryStore` | `core/memory/ports.py` | 标准库 + 向量投影 |
| `EmbeddingProvider` | `core/memory/ports.py` | 文本 → 向量 |
| `PortEmitter` | `port/agent_port.py` | 事件输出 |

### 12.5 配置文件（对外行为旋钮）

| 文件 | 内容 |
|------|------|
| `session_defaults.yaml` | 会话模型、limits（含组装预算） |
| `kernel_config.yaml` | `max_loops`、工具白名单、确认列表、delegate 白名单 |
| `model_providers.yaml` | 模型 provider、backend、环境变量名 |
| `tools.yaml` | 工具注册、设备路由、网络策略 |
| `skills.yaml` | Skill 注册表 |
| `prompts.yaml` | 提示词模板、profile、策略 |
| `memory_policy.yaml` | 双库策略、嵌入配置、检索参数 |
| `security_policies.yaml` | 安全策略、guard、信任分级 |
| `resource_access.yaml` | 关卡⑤ 读写控制 |
| `storage_profiles.yaml` | 会话 / 记忆存储路径与后端 |
| `resource_index.yaml` | 激活策略 / profile 选择 |
| `runtime.yaml` | SQLite 路径、运行时行为 |

### 12.6 开放程度与可替换模块

| 组件 | 替换方式 | 备注 |
|------|----------|------|
| 模型后端 | 实现 `ModelModule` Protocol 或新增 provider | registry 已支持 |
| 工具来源 | 扩展 handler、接 MCP、entrypoint 插件 | MCP 已桥接 |
| 组装策略 | 替换 `AssemblyModuleImpl` | 预算逻辑已模块化 |
| 会话存储 | 实现 `SessionStore` | 需保持 JSON codec |
| 记忆存储 | 实现 `DualMemoryStore` | 可换远程向量库 |
| 嵌入 | 实现 `EmbeddingProvider` | 经 registry 注入 |
| 设备桩 | Port 设备流 | 工具部 → Core → Port |
| 意图解析 | `port/intent_parser.py` | 影响 `AgentRequest.intent` |

**耦合点（替换时注意）**：

- `ModelOutput` / `ToolCall.call_id` 与 `openai_message_format`、Core 写消息强相关
- `KernelConfig` 路径固定读 `platform_layer/.../kernel_config.yaml`
- HTTP 与 Port 共享单例 `_HTTP_PORT`：扩展路由时勿绕过 Port 状态机


---

## 十三、可扩展性与演进路线

### 13.1 已稳固的扩展点

- **ModelProvider.params**：声明式路由字段可扩展（新厂商默认根、专用 path、headers）。
- **MemoryPolicy / 切块 / RRF**：检索与融合策略可配置化。
- **Tool/Skill entrypoint**：插件式工具注册。
- **SessionStore / Embedding / MCP**：registry 替换实现。

### 13.2 建议优先级（与 STATUS 对齐，摘要）

| 优先级 | 方向 |
|--------|------|
| P0–P1 | 维持 Core–模块契约清晰 + 回归测试；组装预算与上下文质量持续迭代 |
| P2 | 工具部设备抽象与 MCP 传输扩展（`builtin:stdio` + `builtin:http_json`，含可选流式映射） |
| P3 | Session 管理进一步策略化/状态机化 |
| P4 | Port 多 worker 与外置会话状态（`pending_state_backend=sqlite_shared` 已有 MVP） |
| P5 | 向量引擎远程化、HNSW、GraphRAG（`remote_retrieval_url` 融合已落地 MVP） |

### 13.3 已知债务（刻意记录）

- **多进程 Port**：内存态待确认字典不共享；生产需外置存储或粘性会话。
- **Session 内部流程**：部分路径仍偏过程式，可逐步策略化。
- **关卡⑤ 全覆盖**：资源模型与审批流仍弱于 ver0.4 全文愿景，以增量交付为主。
- **全异步**：Core/Port/模型调用当前为同步；高并发需 `async def` + `httpx.AsyncClient` + `aiosqlite`。

---

## 十四、相关文档索引

| 文档 | 用途 |
|------|------|
| [架构设计ver0.4.md](./archive/架构设计ver0.4.md) | 原始关卡与模块分工的完整条文 |
| [STATUS.md](./STATUS.md) | 快照与 STUB/债务 |
| [CHANGELOG.md](./CHANGELOG.md) | 与 `version.py` 同步的变更记录 |
| [archive/](./archive/) | ver0.2 / ver0.3 / ver0.5 卫星文档归档 |

---

**结语**：ver0.6 把「微内核 + 三模块 + 五关卡」与「共享服务、组合平面、声明式模型路由、**双库记忆子系统**、**系统接口清单**、资源守门子集」写进同一叙事，消除卫星文档分散问题，形成单一架构参考源。实现细节与发布节奏以 **`version.py` + CHANGELOG + 代码** 为最终依据。
