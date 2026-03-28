## CHANGELOG

### Release 0.5.1 — Design Evolution（2026-03-28）

**版本号**：`0.5.1`。

- **P2 设备后端抽象层**：
  - 新增 `modules/tools/device_backend.py`：`DeviceBackend` Protocol、`LocalSimulatorBackend`（模拟 camera/microphone/speaker/display/filesystem）、`CompositeDeviceBackend`（多后端组合）、`device_result_to_tool_result` 转换。
  - 新增 `app/device_backend_registry.py`：`NoopDeviceBackend`、`resolve_device_backend`（支持 `builtin:simulator`/`builtin:noop`/`entrypoint:<name>`）、`build_device_backend`。
  - `tools.yaml` 新增 `device_backend_refs` 配置项。
  - `tool_registry_loader.py` 新增 `device_backend_refs` 字段解析。
  - 测试：`tests/test_device_backend_registry.py`（25 用例）。

- **P3 Session DESTROYED 状态与清理机制**：
  - `SessionStore` 新增抽象方法 `delete_session`。
  - `SqliteSessionStore.delete_session` 实现物理删除（同时清理 `sessions` 和 `session_archives` 表）。
  - `SessionManager` 新增抽象方法 `trigger_destroy(session_id, physical_delete=False)`。
  - `SessionManagerImpl.trigger_destroy` 实现状态转换与可选物理删除。
  - 测试：`tests/test_session_destroy.py`（9 用例）。

- **P6 关卡⑤ 资源访问增强**：
  - `KNOWN_RESOURCE_IDS` 从 3 类扩展为 8 类：新增 `session_data`、`tool_execution`、`device_access`、`external_api`、`filesystem`。
  - `ResourceAccessEvaluator` 新增 `check_and_audit` 方法与 `ResourceAccessEvent` 审计事件。
  - 审计日志输出到 `pompeii.resource_audit` logger。
  - `resource_access.yaml` 新增 `strict` profile（最小权限原则）。

- **测试**：全量 34 项新增测试通过。

- **装配链集成**：
  - `composition.py` 集成 `build_device_backend`，从 `tools.yaml` 的 `device_backend_refs` 构建设备后端并注入 `ToolModuleImpl`。
  - `ToolModuleImpl` 新增 `device_backend` 属性，支持同步设备执行模式。

- **STUB 清理**：
  - `HttpMode`/`WsMode` 移除 STUB 标注（HTTP/WS 运行时已在 `http_runtime.py` 落地）。
  - `ToolModuleImpl` 设备执行器 STUB 已完全替换为真实实现。

---

### Docs consistency check fix（2026-03-27）

**版本号**：`0.5.0`。

- **链接与版本对齐**：
  - `README.md`：`ver0.4` 链接改为 `docs/design/archive/架构设计ver0.4.md`，修复归档后断链风险。
  - `docs/design/架构设计ver0.5.md`、`docs/guides/继续开发手册.md`：内部 `ver0.4` 引用统一改为 `archive/架构设计ver0.4.md`。
  - `docs/design/ai-rules-template/RULES.md`：在人类授权下，将封闭清单中的 `ver0.4` 路径同步为 `docs/design/archive/架构设计ver0.4.md`。
  - `.cursor/rules/pompeii-protocol-skills-docs.mdc`：同步 `ver0.4` 引用路径到 `docs/design/archive/架构设计ver0.4.md`，避免规则镜像与主规则漂移。
  - `docs/design/架构设计ver0.5.md`：版本快照从历史 `0.4.61` 更新为当前 `0.5.0`。
  - `docs/guides/系统测试流程.md`、`docs/guides/API密钥配置操作手册.md`：文档内“当前版本”从 `0.4.21` 同步为 `0.5.0`。

---

### Release 0.5.0（2026-03-27）

**版本号**：`0.5.0`。

- **里程碑定位**：从 `0.4.x` 的持续迭代升级为 `0.5` 主版本线，标记“微内核主链 + 外部对接 MVP + 配置/契约/测试体系”进入稳定发布阶段。
- **主系统完成度**：
  - Core/Assembly/Model/Tools/Port 主链闭环稳定；
  - 会话状态机、长期记忆双库（含 CRUD/reindex/GC）与预算治理可用；
  - 结构化日志与 `request_id` 全链路完成。
- **外部对接 MVP**：
  - HTTP `/input` + `WS /ws`；
  - MCP `builtin:stdio` + `builtin:http_json`（含可选流式 SSE 字段映射）；
  - `pending_state_backend=sqlite_shared` 支持多 worker 场景下待确认/待设备共享状态；
  - 远端检索 `remote_retrieval_url` 融合与资源守门/审批语义联动。
- **工程化**：
  - `pyproject`/`MANIFEST`/可安装包（`pip install -e .`）；
  - `contracts/` 契约索引与 Port 边界文档；
  - 当前测试基线保持全量通过（见本次会话回归记录）。

---

### Docs sweep & cleanup（2026-03-27）

**版本号**：`0.5.0`。

- **文档更新**：
  - `docs/design/架构设计ver0.5.md`：同步 `WS /ws` 接口、`PolicyNoticeEvent`、P2/P4/P5 的 MVP 落地描述（MCP HTTP 桥、pending sqlite_shared、remote_retrieval 融合）。
  - `README.md`：`/input` 事件说明补充 `policy_notice`。
  - `contracts/kernel_port_boundary.md`：Port 出向事件清单包含 `policy_notice`。
- **冗余文件清理**：删除仓库内 `src/` 与 `tests/` 下全部 `__pycache__/*.pyc` 缓存文件（不影响源码与测试）。

---

### External Phase 6 contract sync（2026-03-27）

**版本号**：`0.4.74`。

- `contracts/kernel_port_boundary.md` 同步 Port 出向事件清单，补充 `policy_notice` 在对接契约中的可见性，避免网关仅凭 changelog 反推事件类型。

---

### External Phase 6 policy notice（2026-03-27）

**版本号**：`0.4.73`。

- **Port 事件扩展**：新增 `PolicyNoticeEvent(kind=\"policy_notice\")`，用于表达“策略允许路径中的审批/治理提示”，避免仅依赖回复文本承载策略信息。
- **AgentResponse -> PortEvent 映射**：当 `reason=resource_approval_required` 且为 reply 路径时，Port 先发 `policy_notice` 再发 `reply`。
- **CLI 渲染**：新增 `[POLICY] <policy>: <detail>` 输出格式。
- **测试**：新增 `tests/test_policy_notice_event.py`，覆盖审批 reason 的事件序列。

---

### External Phase 6 approval progression（2026-03-27）

**版本号**：`0.4.72`。

- **remote_retrieval 审批语义推进**：
  - `MemoryOrchestrator` 在 `remote_retrieval/read` 为 `requires_approval` 时，不触发远端 HTTP 请求；
  - 返回策略提示片段（`memory_id=policy:remote_retrieval_approval_required`）用于上层可观测反馈，避免静默跳过。
- **检索流程健壮性**：`retrieve_for_context` 不再因“本地候选为空”提前返回，从而允许远端检索（或审批提示）独立生效。
- **测试**：`tests/test_memory_remote_retrieval.py` 新增审批用例并覆盖上述行为。

---

### External Phase 6 gate alignment（2026-03-27）

**版本号**：`0.4.71`。

- **远端检索守门联动**：
  - 新增资源键 `remote_retrieval`（`core/resource_access.py`，纳入 `KNOWN_RESOURCE_IDS`）。
  - `MemoryOrchestrator` 支持注入 `ResourceAccessEvaluator`，在远端检索前校验 `remote_retrieval/read`，被拒绝则跳过 HTTP 调用。
  - `composition._try_build_memory_orchestrator` 注入当前激活的资源访问评估器。
  - `resource_access.yaml` 默认与 `memory_readonly` profile 增加 `remote_retrieval` 规则。
- **测试**：`tests/test_memory_remote_retrieval.py` 增加资源门 deny 用例，确保拒绝时不触发远端 HTTP。

---

### External Phase 6 stream mapping（2026-03-27）

**版本号**：`0.4.70`。

- **MCP HTTP 流式字段映射可配置**：
  - `McpHttpServerEntry` 新增 `sse_event_type_key` / `sse_delta_key` / `sse_text_key` / `sse_output_key` / `sse_result_event_value`。
  - `mcp_http_bridge` 流式解析不再写死 `type/delta/text/output/result`，可通过 `mcp_servers.yaml` 为不同网关映射字段。
- **配置校验**：`mcp_config_loader` 对上述字段做非空字符串校验。
- **测试**：
  - `tests/test_mcp_http_bridge.py` 新增 `test_mcp_http_bridge_stream_custom_mapping`；
  - 新增 `tests/test_mcp_config_loader_http_stream_fields.py`。

---

### External Phase 6 extension（2026-03-27）

**版本号**：`0.4.69`。

- **MCP HTTP 桥升级（流式）**：
  - `McpHttpServerEntry` 新增 `stream_enabled` 与 `stream_endpoint_path`。
  - `infra/mcp_http_bridge.py` 新增 SSE 解析路径：支持 `data: {"type":"delta","delta":"..."}` 与 `data: {"type":"result","output":...}`，并处理 `[DONE]`。
  - 流式无 `result` 时自动拼接 delta 为 `{ "text": "..." }`；失败回退 JSON 模式保持兼容。
- **配置与示例**：`mcp_servers.yaml` 增加流式字段注释示例。
- **测试**：`tests/test_mcp_http_bridge.py` 新增流式 delta 聚合与 result 事件用例。

---

### External Phase 6 completion（2026-03-27）

**版本号**：`0.4.68`。

- **G10 WebSocket 服务化（MVP）**：`app/http_runtime.py` 新增 `WS /ws`，每条入站 JSON 与 `/input` 同构并回传 `events[]`。
- **G11 MCP HTTP 传输（MVP）**：
  - `infra/mcp_config_loader.py` 支持 `bridge_ref: builtin:http_json` 与 `http_servers`（`base_url/api_key_env/timeout_seconds`）。
  - 新增 `infra/mcp_http_bridge.py`，按 `POST {base_url}/tools/call` 调用网关。
  - `app/mcp_bridge_registry.py` 支持 `builtin:http_json`。
- **G12 多 worker 待确认/待设备外置（MVP）**：
  - `port/agent_port.py` 增加 `pending_state_sqlite_path`，可将待确认/待设备状态持久到共享 SQLite。
  - `runtime_config_loader.py` 新增 `port.pending_state_backend`（`memory|sqlite_shared`）与 `pending_state_sqlite_path`。
  - `http_runtime.py` 按 `runtime.yaml` 自动启用共享 pending 存储。
- **G13 远端检索融合（MVP）**：
  - `memory_policy` 新增 `remote_retrieval_url` / `remote_timeout_seconds`。
  - `MemoryOrchestrator.retrieve_for_context` 可融合远端检索候选（用于独立向量服务接入）。
- **G14 资源审批门（MVP）**：
  - `resource_access` 规则新增 `read_requires_approval` / `write_requires_approval`。
  - `ResourceAccessEvaluator.requires_approval()` 与 Core 记忆 CRUD 路径联动，返回 `reason=resource_approval_required`。
- **测试**：新增 `test_http_runtime_ws.py`、`test_mcp_http_bridge.py`、`test_port_pending_sqlite.py`、`test_memory_remote_retrieval.py`、`test_resource_approval_gate.py`。

---

### External Phase 6（2026-03-27）

**版本号**：`0.4.67`。

- **WebSocket 运行时（G10）**：`app/http_runtime.py` 新增 `WS /ws`，入站 JSON 与 `POST /input` 的 `InputDTO` 同构（`kind/user_id/channel/text/payload/openai_user_content/stream`），每条消息回传 `{"events":[...]}`，底层复用同一 `GenericAgentPort` 与会话分区语义。
- **输入处理复用**：抽出 `_handle_dto(dto)`，HTTP 与 WS 共用验证与 Port 调用路径，避免双份分支漂移。
- **测试**：新增 `tests/test_http_runtime_ws.py`（WS roundtrip + payload 类型校验）。
- **文档**：`README.md` 增加 `WS /ws` 入口；`STATUS.md` 的 STUB 备注同步为“WS 收包已落地，独立网关后续”。

---

### Packaging Phase 5 completion（2026-03-27）

**版本号**：`0.4.66`。

- **程序化配置门面补齐**：
  - `app/config_loaders/session_config_loader.py` 新增 `load_session_config_from_mapping(config_data)`，与文件加载路径等价。
  - `app/config_provider.py` 新增 `in_memory_mapping_config_provider(config_mapping)`，宿主可从内存 dict 构造 `ConfigProvider`，降低对整棵 `platform_layer` 目录复制依赖。
- **示例联动**：`examples/minimal_kernel.py` 使用内存映射 provider 路径演示一次最小 `build_core` + `handle`。
- **测试**：新增 `tests/test_config_provider.py`（mapping loader / provider / 非法结构）；全量 `pytest` 通过。
- **继续开发手册**：`docs/guides/继续开发手册.md` 中 P1 三项（可安装包、程序化配置门面、最小示例）标记为已落地。

---

### Packaging & contracts Phase 5（2026-03-27）

**版本号**：`0.4.65`。

- **`pyproject.toml`**：补充 `[build-system]`、`[project]`（`pompeii-agent`、动态 `version` ← `app.version.__version__`、依赖与 `requires-python>=3.11`）、`setuptools` 包发现（`package-dir` = `src`）、`include-package-data`；保留 `[tool.pytest.ini_options]`。
- **`MANIFEST.in`**：`graft src/platform_layer/resources`，保证 wheel/sdist 含静态 YAML。
- **`examples/minimal_kernel.py`**：装配 `build_core` + 会话强制 `model=stub`，单条 `Chat` 请求；无 Key 可跑通。
- **`contracts/`**：`README.md`（索引与 CONTRACT_STATUS）、`kernel_port_boundary.md`（AgentRequest/AgentResponse/Reason 摘要表）。
- **`docs/design/INDEX.md`**、`README.md`：契约入口与 `pip install -e .` / 示例说明。

---

### Observability Phase 4.1（2026-03-27）

**版本号**：`0.4.64`。

- **request_id 全链路**：`infra/request_context.py` 使用 `contextvars` 绑定 `request_id` / `user_id` / `channel`；`GenericAgentPort.handle` 在正常请求、非法输入、确认流、设备结果流中 `bind`/`reset`。
- **结构化日志**：`infra/logging_config.py` 链式 `setLogRecordFactory`，在每条 `LogRecord` 上注入 `request_id` / `user_id` / `channel`（无上下文时为 `-`）；`setup_structured_logging()` 为 root 配置含上述字段的单行 Formatter。`http_runtime` / `cli_runtime` 启动时调用；`tests/conftest.py` 与 `agent_core` / `agent_port` 侧向导入保证测试与库路径一致。
- **观测点**：`AgentCoreImpl._handle`、`run_openai_compatible_chat_impl` 增加 **DEBUG** 级日志（避免测试刷屏）。
- **测试**：`tests/test_request_logging_context.py`。

---

### Assembly Phase 3.1（2026-03-27）

**版本号**：`0.4.63`。

- **可选 tiktoken 组装 token 计数**：`SessionLimits` 增加 `assembly_token_counter`（`heuristic` | `tiktoken`）、`assembly_tiktoken_encoding`（默认 `cl100k_base`）。`session_defaults.yaml` 与 `session_config_loader` / `session_json_codec` 已贯通；`modules/assembly/token_budget.py` 提供 `make_message_token_counter` 与可注入的 `count_tokens`，`AssemblyModuleImpl` 按会话配置选用。**未安装 tiktoken 且配置为 tiktoken 时**记录 warning 并回退 len/4。
- **依赖**：`requirements.txt` 增加 `tiktoken>=0.5.0`。
- **测试**：`test_token_budget.py`、`test_session_json_codec.py` 覆盖 heuristic/tiktoken 与 JSON 往返。

---

### Memory Phase 2.2–2.3（2026-03-27）

**版本号**：`0.4.62`。

- **Phase 2.2 测试补齐**：新增 `tests/test_fact_crud.py`，覆盖 `/fact` 意图解析（add/get/list/delete）与 `MemoryOrchestrator` 事实 CRUD（含前缀匹配、用户隔离）。
- **Phase 2.3 重索引与 tombstone GC**：
  - `core/memory/ports.py`：`StandardMemoryRepository` 增加 `list_active_memory_ids_for_user`、`purge_tombstoned_rows`。
  - `infra/sqlite_dual_memory_store.py`：实现 `purge_tombstoned_rows`（物理删除 `tombstone=1` 主表行；向量与 FTS 已在 tombstone 时清理）。
  - `core/memory/orchestrator.py`：`reindex_memory_id`、`reindex_user_memories`（嵌入模型变更后重建向量投影）、`purge_tombstoned_rows`（运维回收主表空间）。
  - 新增 `tests/test_memory_reindex_gc.py`。

---

### 工具链（2026-03-27）

- **Cursor 规则库**：将 `docs/design/ai-rules-template/RULES.md` 要点部署为 `.cursor/rules/pompeii-iron-rules.mdc`（八条铁律 + L1/L2/L3）与 `.cursor/rules/pompeii-protocol-skills-docs.mdc`（接入协议、Skill 索引、任务组合、文档封闭清单）。`alwaysApply: true`，权威仍以 `RULES.md` 为准。

---

### Core Hardening（2026-03-27）

- **Session 状态机**：`session.py` 新增 `_VALID_TRANSITIONS` 转换表、`InvalidSessionTransition` 异常、`validate_session_transition` 校验函数。`SessionManagerImpl.update_status` 在写入存储前校验合法性；`get_or_create_session` 对 IDLE 会话自动重激活为 ACTIVE。28 项状态机单测（`test_session_state_machine.py`）。
- **ResponseReason 枚举**：`agent_types.py` 新增 `ResponseReason(str, Enum)`，覆盖 17 种终止原因（ok / max_loops / max_tool_calls / repeated_tool_call / tool_policy_denied / confirmation_required / device_request / security_* / resource_access_denied / delegate / delegate_target_denied / unsupported_output_kind / tool_call_missing）。`AgentResponse.reason` 类型由 `str | None` → `ResponseReason | None`；`agent_core.py`、`policies/loop_policy.py`、`policies/tool_actions.py`、`port/agent_port.py` 全量迁移。`ResponseReason` 继承 `str`，向后兼容所有 `==` 比较与序列化。

---

### 文档（2026-03-27）

- **架构设计 ver0.6 文档合并**：将《会话与双库长期记忆架构设计》、《长期记忆定义》、《开发状态与系统接口》三份卫星文档的核心架构内容合入 `架构设计ver0.5.md`（升级为 ver0.6）。新增 §九（长期记忆子系统：双库架构、记录类型、Orchestrator 边界、调用时序、写入顺序、接口化）、§十二（系统接口清单：HTTP/Kernel/Port/Module Protocol 接口总表、配置旋钮、可替换模块与耦合点）。原文档移至 `archive/`。
- **P0 清理**：为 `HttpMode`/`WsMode`（`port/agent_port.py`）、`approximate_message_tokens`（`modules/assembly/token_budget.py`）补 STUB 标注；删除 `modules/tools/__pycache__/device_backend.cpython-314.pyc` 幽灵文件；修复 STATUS.md 中 `DeviceToolBackend` 失效引用（→ `resolve_device_request`）。
- **INDEX.md / STATUS.md**：同步更新文档索引与状态快照，移除已合并卫星文档引用。
- **断链修复**：README.md、RULES.md 文档清单、`继续开发手册.md`、`系统测试流程.md`、`API密钥配置操作手册.md`、`core/memory/__init__.py`、`resource_validation.py` 中对已移动卫星文档的引用全部指向 `架构设计ver0.5.md`（ver0.6）对应章节。

---

### Release 0.4.61（2026-03-25）

**版本号**：`0.4.61`。

- **OpenAI 兼容调用声明式路由**：`modules.model.openai_provider_route` 从 `ModelProvider.params` 解析 `base_url`、`model` / `model_id`（前缀推断内置默认根 URL）、`chat_completions_path`、`extra_headers` 等；`run_openai_compatible_chat_impl` 统一经此出口拼 URL 与载荷。`model_providers.yaml` 顶部补充说明；新增 `tests/test_openai_provider_route.py`。

---

### Release 0.4.60（2026-03-25）

**版本号**：`0.4.60`。

- **架构 ver0.4 §8.1 重复 tool_call**：`_run_loop` 对连续两轮模型输出进行「名称 + 参数 JSON」指纹比对；第二次相同且尚未执行该次工具时返回 `reason=repeated_tool_call`。`tool_call_fingerprint` 键序无关。Port 对应该 reason 发出 `status` + `error`。

---

### Release 0.4.59（2026-03-23）

**版本号**：`0.4.59`。

- **Delegate 白名单**：`kernel_config.delegate_target_allowlist`（可选；空表示不限制）。非空时 `/delegate` 的 target 须命中列表，否则 `reason=delegate_target_denied` 且不写入会话、不发出 `DelegateEvent`。加载器校验 token 与 intent 规则一致。

---

### Release 0.4.58（2026-03-23）

**版本号**：`0.4.58`。

- **Delegate 契约（架构 ver0.4 多 Agent）**：`UserIntent.SystemDelegate`；解析 `/delegate <target> <payload>`（`target` 为 `[a-zA-Z0-9_.-]+`）。`AgentResponse` 增加 `delegate_target` / `delegate_payload` 与 `reason=delegate`。`GenericAgentPort` 在 `reply` 之前 `emit(DelegateEvent)`；CLI 输出目标与截断 payload。`/help` 文档已更新。

---

### Release 0.4.57（2026-03-23）

**版本号**：`0.4.57`。

- **关卡④-c 工具结果注入规则（顺序推进）**：`security_policies.baseline` 默认启用 `tool_output_injection_patterns`，拦截伪造关卡② `pompeii` 分区 HTML 注释边界。`AgentCoreImpl._sanitize_tool_result_for_guard` 对 dict/list 工具输出使用与组装序列化一致的 **JSON 文本视图**做截断、注入子串与 `guard_block` 扫描，以便匹配仅出现在 JSON 双引号形态下的危险片段。

---

### Release 0.4.56（2026-03-23）

**版本号**：`0.4.56`。

- **架构 ver0.4 §6.4 ④-c 来源标签（主线）**：`AssemblyModuleImpl.apply_tool_result` 在启用 `context_isolation_enabled` 时，用关卡② `tool_result` 分区包裹 `Context.current`；`trust`/`source` 由 `ToolResult.source` 推导。`tool_first` 策略在模型部先剥除外层分区再解析 `tool name -> payload`。

---

### Release 0.4.55（2026-03-23）

**版本号**：`0.4.55`。

- **关卡⑤ 配置校验**：`core.resource_access.KNOWN_RESOURCE_IDS`；`validate_resource_configs` 拒绝 `resource_access.yaml` 中未登记的资源键（防拼写错误导致策略不生效）。

---

### Release 0.4.54（2026-03-23）

**版本号**：`0.4.54`。

- **多模态 image_url 基线 SSRF**：`http_url_guard.multimodal_image_url_host_baseline_violation` 拒绝 `localhost` 及私网/环回等字面 IP（与工具侧 `_blocked_ip_literal` 一致）；`apply_user_parts_preprocessing` 在**未**启用 `http_url_guard` 白名单时亦执行，公网字面 IP（如 `8.8.8.8`）与普通域名仍放行。

---

### Release 0.4.53（2026-03-23）

**版本号**：`0.4.53`。

- **关卡⑤ `multimodal_image_url`**：`resource_access.yaml` 资源 `multimodal_image_url`（read 控制 user 多模态图是否进模型载荷）。`AssemblyModuleImpl` 将 `tools.network_policy` 的 `http_url_guard_*` 注入 `Context.meta`，`apply_user_parts_preprocessing` 对 `image_url` 做基线校验（仅 http(s)、禁 userinfo、须有 host）及可选白名单（与 `http_url_guard` 一致）；拒绝时替换为文本占位。当前轮多模态改由 **会话尾部 user `Message`** 经 `openai_user_message_payload` 生成 API 内容（不再依赖 `meta.openai_user_message_content`）。`composition` 单次加载 `tools.yaml` 供组装部与工具部共用。

---

### Release 0.4.52（2026-03-23）

**版本号**：`0.4.52`。

- **组装部 OpenAI user content 契约**：`modules.assembly.openai_user_content` 提供 `openai_user_message_payload`（user → `str | list` OpenAI content）与 `apply_user_parts_preprocessing`（MVP 透传，预留 §3.1 预处理）。`_render_history_messages_for_model_plain` 经此出口渲染 user 历史/文本，模型部不再直接依赖 `message_to_openai_user_blocks`。

---

### Release 0.4.51（2026-03-23）

**版本号**：`0.4.51`。

- **多模态 user 历史回放**：`_render_history_messages_for_model_plain` 对非末尾的 `Part(image_url)` user 消息输出 `content` 块数组（与 API 一致）；`_isolate_history_plain_messages` 对其中 `type=text` 块套 `history_user` 关卡②；`_drop_trailing_user_if_matches_current` 遇 list 形 content 不再误做字符串去重。

---

### Release 0.4.50（2026-03-23）

**版本号**：`0.4.50`。

- **多模态用户输入（MVP，OpenAI Chat 块）**：`AgentRequest.payload` 可为 `{ "openai_user_content": [ { "type":"text",...}, { "type":"image_url", "image_url": { "url": "..." } } ], "text": "可选说明" }`；`UserMessageInput.openai_user_content`；HTTP `POST /input` 字段 `openai_user_content`。会话以 `Part(type=image_url)` 持久化；`run_openai_compatible_chat_impl` 由会话 user `Message` 生成 `messages[].content` 为块数组（历史尾部多模态 user 从 history 渲染中剔除以免重复）。关卡① 对载荷使用 `flatten_payload_for_security`。MVP 多模态轮不应用 `user_prompt_profiles`。

---

### Release 0.4.49（2026-03-23）

**版本号**：`0.4.49`。

- **可插拔系统提示词策略（entrypoint）**：`kernel.prompt_strategy_ref`（默认 `builtin:none`）与可选 `params.prompt_strategy_ref`（按 provider 覆盖）。在 YAML 模板与 `<active_skills>` 合并（及 `PromptCache`）之后调用 `modules.model.prompt_strategy_registry.run_prompt_strategy`；插件组 **`pompeii_agent.prompt_strategies`**，签名为 `(system_prompt, provider, session, context, skill_registry) -> str | None`（`None` 表示保持原样）。`ModelModuleImpl` 经 `prompt_strategy_context` 注入默认 ref。`resource_validation` 校验 ref 形态。

---

### Release 0.4.48（2026-03-23）

**版本号**：`0.4.48`。

- **模型调用滑动窗口限流（简易计量）**：`infra.model_provider_rate_limit` 按 `provider.id` 维护时间戳队列；`params.model_rate_max_calls_per_window`（>0 启用）、`params.model_rate_window_seconds`（默认 60）。在 `run_openai_compatible_chat_impl` 中于熔断检查之后、组装载荷之前执行，避免无谓计算。超限文案含「调用过于频繁」，已纳入 `openai_failure` 以支持 `failover_chain`。`clear_model_provider_rate_limit_state()` 供测试。

---

### Release 0.4.47（2026-03-23）

**版本号**：`0.4.47`。

- **模型 provider 简易熔断**：`infra.model_provider_circuit` 按 `provider.id` 统计连续失败（与 `openai_failure.openai_output_suggests_failover` 一致）；`params.model_circuit_failure_threshold`（>0 启用）、`params.model_circuit_open_seconds`（默认 60）。`run_openai_compatible_chat_impl` 在调用前 `precheck`、返回前 `record`。熔断文案含「熔断中」，纳入 failover 启发式以便 `failover_chain` 可换备用。`clear_model_provider_circuit_state()` 供测试重置。

---

### Release 0.4.46（2026-03-23）

**版本号**：`0.4.46`。

- **OpenAI 兼容：流式 + tools（可选）**：`params.stream_with_tools: true` 且 `params.stream: true`、入站流式开启时，即使配置了 `params.tools` 也走 SSE；`openai_stream_accumulate.OpenAiChatStreamCollector` 合并 `delta.tool_calls` 后走既有 `openai_message_to_model_output`。未开启时行为与此前一致（有 tools 则非流式）。

---

### Release 0.4.45（2026-03-23）

**版本号**：`0.4.45`。

- **模型部 HTTP 连接复用**：`infra.model_http_client_pool` 按 `(base_url, timeout)` 复用 `httpx.Client`（LRU 上限 48）；`run_openai_compatible_chat_impl` 非流式与 SSE 流式均经 `_chat_http_client`；可选 **`params.http_disable_connection_pool: true`** 恢复每次新建 Client。顺带修正原先非流式在 `with httpx.Client` 退出后再 `raise_for_status`/`json()` 的边界。

---

### Release 0.4.44（2026-03-23）

**版本号**：`0.4.44`。

- **Port 交互模式 registry（继续开发矩阵）**：`runtime.yaml` 可选 `port.interaction_mode_ref`（默认 `builtin:cli`）；`app.port_mode_registry` 支持 `builtin:cli|http|ws` 与 `entrypoint:<name>`（**`pompeii_agent.interaction_modes`**，工厂 `() -> InteractionMode`）。`cli_runtime.main` 从 runtime 解析模式；`resource_validation` 校验 ref 形态。HTTP 路由仍直接使用 `GenericAgentPort.handle`（`builtin:http` 供对称与测试）。

---

### Release 0.4.43（2026-03-23）

**版本号**：`0.4.43`。

- **模型主备 Failover（设计 3.2 / 缺口）**：`model_providers.yaml` 各 provider 可选 `failover_chain: [id, ...]`（须指向已定义 id，且不得包含自身）。主为 `openai_compatible` 时，对网络/密钥/空响应等**可判定失败**的文本结果按序尝试链上 provider（可含 `stub` 作最后降级）；仅展开**一层**链，不递归备用上的 `failover_chain`。`merge_prompt_config_into_registry` 保留 `failover_chain`。

---

### Release 0.4.42（2026-03-23）

**版本号**：`0.4.42`。

- **Skill entrypoint（设计 4.2 / 继续开发矩阵）**：`skills.yaml` 支持 `enable_entrypoints`、`entrypoint_group`（默认 `pompeii_agent.skills`）；`merge_skill_registry_with_entrypoints` 合并 setuptools 技能，**YAML 覆盖同名插件**；`composition` 与 `resource_validation` 使用合并结果。
- **策略引擎 entrypoint**：`kernel_config` 增加 `tool_policy_engine_ref`、`loop_policy_engine_ref`（默认 `builtin:default`）；`app.tool_policy_registry` / `app.loop_policy_registry` 支持 `entrypoint:<name>`，组分别为 **`pompeii_agent.tool_policies`**、**`pompeii_agent.loop_policies`**；`AgentCoreImpl` 注入可替换的 `decide` 与 `LoopGovernance` 计算。

---

### Release 0.4.41（2026-03-23）

**版本号**：`0.4.41`。

- **关卡④-a（设计对照）**：`tools.network_policy.http_blocked_content_type_prefixes`；`http_get` 在读取 body 前按响应 `Content-Type` 主类型前缀拦截；成功结果标记 `ToolResult.source=http_fetch`。
- **关卡④-b/c（设计对照）**：`security_policies` 增加 `http_fetch_tool_output_trust`（与 `tool_output_max_chars_by_trust` 联用）、`tool_output_injection_patterns` / `tool_output_injection_redaction`（工具结果串在截断后、入口 `guard_block_patterns` 之前做子串匹配并整段替换）。

---

### Release 0.4.40（2026-03-23）

**版本号**：`0.4.40`。

- **内置 `http_get` 工具（可选启用）**：`tools.local_handlers` 中声明 `http_get: "modules.tools.builtin_handlers:http_get_tool"` 时，由 `composition._build_tools` 绑定为 `make_http_get_handler(network_policy)`。GET、不跟随重定向、响应体与预览长度上限可配；请求前执行 `enforce_http_url_policy`。默认 `tools.yaml` 未注册，须自行加入 `kernel.tool_allowlist` 与会话技能。

---

### Release 0.4.39（2026-03-23）

**版本号**：`0.4.39`。

- **关卡④-a HTTP URL 校验（可复用库）**：`tools.network_policy` 可选 `http_url_guard_enabled`、`http_url_allowed_hosts`；`modules.tools.http_url_guard` 提供 `enforce_http_url_policy` / `assert_safe_http_tool_url`（仅 http(s)、禁 userinfo、字面 IP 防 SSRF、域名依赖白名单）。供后续 HTTP 类工具在发请求前调用；默认关闭。

---

### Release 0.4.38（2026-03-23）

**版本号**：`0.4.38`。

- **关卡④-a 网络策略（MVP）**：`tools.yaml` 可选 `network_policy`（`enabled`、`deny_tool_names`、`mcp_allowlist_enforced`、`mcp_tool_allowlist`）。`ToolModuleImpl.execute` 在启用时拦截黑名单工具；在启用 MCP 白名单时仅允许名单内工具经 `McpToolBridge.try_call`。`validate_resource_configs` 要求 `mcp_tool_allowlist`  ⊆ `kernel.tool_allowlist`。配置类型见 `modules.tools.network_policy`。

---

### Release 0.4.37（2026-03-23）

**版本号**：`0.4.37`。

- **§7.3 单次窗口三级压缩（MVP）**：在 `assembly_approx_context_tokens` 超限时，依次尝试（1）截短 `openai_v1` **tool** 正文（`limits.assembly_compress_tool_max_chars`，0=跳过）、（2）自前向后折叠相邻纯文本 **user+assistant** 为一轮（`assembly_compress_early_turn_chars`，0=跳过）、（3）沿用既有自新向旧 **丢消息** 裁剪。会话默认值仍为 0/0，行为与此前仅第三级一致；LLM `model.summarize` 与异步归档留待后续。

---

### Release 0.4.36（2026-03-23）

**版本号**：`0.4.36`。

- **关卡② 上下文隔离（架构 ver0.4 §6.2 / §3.1）**：以 HTML 注释形态 `pompeii:zone-begin/end` 标记 **system**（`prompt_config` / `high`）、**memory**（长期记忆块 / `medium`）、会话 **history**（`history_user|assistant|tool`）及当前轮 **user** / **tool_result**（工具回注时按 `last_tool.source` 映射 trust）。`kernel.context_isolation_enabled`（默认 `true`）经 `AssemblyModuleImpl` 写入 `Context.meta`，OpenAI 兼容聊天路径在**去重尾部 user 之后**再套包装，避免破坏 `_drop_trailing_user_if_matches_current`。

---

### Release 0.4.35（2026-03-23）

**版本号**：`0.4.35`。

- **AssemblyModule 显式注入**：`build_core(..., assembly=AssemblyModule | None)`；传入非空时跳过默认 `AssemblyModuleImpl`（自定义实现须自行处理记忆块、预算等与默认等价职责）；`None` 时行为与此前一致。

---

### Release 0.4.34（2026-03-23）

**版本号**：`0.4.34`。

- **MCP 桥可插拔（设计 P2）**：`mcp_servers.yaml` 可选 `bridge_ref`（默认 `builtin:stdio`；或 `entrypoint:<name>`）。新增 `app.mcp_bridge_registry.resolve_mcp_bridge`，entry point 组 **`pompeii_agent.mcp_bridges`**，工厂签名 `(McpRuntimeConfig, src_root: Path) -> McpToolBridge | None`；`composition._load_mcp_bridge` 经 registry 解析。
- **配置**：`McpRuntimeConfig.bridge_ref`；加载器校验 ref 格式。

---

### Release 0.4.33（2026-03-23）

**版本号**：`0.4.33`。

- **关卡④ 设备回传信任档**：`security_policies` 可选 `device_tool_output_trust`（默认 `low`）；`GenericAgentPort` 接受设备回传时构造的 `ToolResult` 带 `source="device"`，净化层与 MCP 一样仅在 `tool_output_max_chars_by_trust` 非空时按档合并截断上限。

---

### Release 0.4.32（2026-03-23）

**版本号**：`0.4.32`。

- **关卡④ 信任分级截断**：`security_policies` 可选 `tool_output_max_chars_by_trust`（`low` / `medium` / `high` → 非负整数，**0 表示该等级不额外限制**）、`default_tool_output_trust`、`tool_output_trust_overrides`、`mcp_tool_output_trust`；**仅当 `tool_output_max_chars_by_trust` 非空时启用**，与全局/按工具上限合并为 `min`（一侧为 0 则只受另一侧约束）。
- **MCP**：`McpStdioBridge` 返回的 `ToolResult` 带 `source="mcp"`，净化层按 `mcp_tool_output_trust` 选档。
- **类型**：`ToolResult` 增加可选字段 `source`（约定 `"mcp"` 表示经 MCP）。

---

### Release 0.4.31（2026-03-23）

**版本号**：`0.4.31`。

- **关卡④ 按工具截断**：`security_policies` 每条策略可选 `tool_output_max_chars_overrides`（`工具名 -> 非负整数`）；命中键时优先于全局 `tool_output_max_chars`，**值为 0 表示该工具不截断**；未列出的工具仍用全局值。

---

### Release 0.4.30（2026-03-23）

**版本号**：`0.4.30`。

- **关卡④（MVP）工具结果截断**：`security_policies` 每条策略可选 `tool_output_max_chars`（非负整数，**0 表示不截断**）与 `tool_output_truncation_marker`；在写入会话前对工具 `output` 先截断，**再**执行既有 `guard_enabled` 模式/守卫检测（截断后命中则整段替换为 `guard_tool_output_redaction`）。
- **实现**：`SecurityPolicySpec` + `security_policy_loader`；`AgentCoreImpl._sanitize_tool_result_for_guard`；单测覆盖仅截断与截断后守卫。

---

### Release 0.4.29（2026-03-23）

**版本号**：`0.4.29`。

- **P0 长期记忆双线语义封顶**：`memory_policy.enabled=true` 时 `storage_profiles.memory.store_ref` 必须为 **`builtin:noop`**（`resource_validation`），避免旧版 `LongTermMemoryStore` 与 `DualMemoryStore` 争用同一 `memory.path`；仓库默认 `storage_profiles.yaml` 已改为 `builtin:noop`。
- **文档/注释**：`LongTermMemoryStore` 与 `memory_store_registry` 标明为冻结旧线（composition 不注入）；`长期记忆定义.md`、继续开发手册 P0 同步。

---

### Release 0.4.28（2026-03-23）

**版本号**：`0.4.28`。

- **OpenAI 兼容流式输出**：`model_providers` 可选 `params.stream: true`；与 `AgentRequest.stream`（HTTP `InputDTO.stream` → `UserMessageInput.stream`）同时为真且无 `params.tools` 时，使用 SSE 消费增量并通过 `core.model_stream_context` 回调；Port 发出 `StreamDeltaEvent`，最终仍合并为完整 `ReplyEvent`。
- **API**：`AgentCore.handle` / `handle_confirmation_approved` / `handle_device_result` 增加可选关键字参数 `stream_delta`。
- **实现**：`modules/model/openai_sse.py`（SSE 行解析）、`modules/model/impl._post_openai_chat_stream`。

---

### Release 0.4.27（2026-03-23）

**版本号**：`0.4.27`。

- **关卡⑤ 资源访问（MVP）**：新增 `resource_access.yaml` 与 `resource_index.active_resource_access_profile`；`ResourceAccessEvaluator` 按资源 `long_term_memory` 的 `read`/`write`（`allow`|`deny`）裁决。
- **接入点**：组装部长期记忆上下文注入（读）、`/remember` 与 `/forget`（写）、归档晋升写入长期记忆（写，禁止时跳过晋升）、工具 `search_memory`（读）。
- **校验**：`resource_validation` 要求所选 profile 存在于 `resource_access.profiles`。

---

### Release 0.4.26（2026-03-23）

**版本号**：`0.4.26`。

- **归档异步 LLM 摘要**：`kernel_config.yaml` 可选 `archive_llm_summary_enabled` 等字段；`/archive` 后 daemon 线程调用所选 `openai_compatible`（或 `stub`）provider 生成摘要，写入 `session_archives.llm_summary_text` / `llm_summary_status`（`pending` → `done` / `failed` / `skipped`）；`GET /archives` 列表含新字段。
- **实现**：`modules/model/archive_dialogue_summary.py`；`core/archive_llm_summary.py` 注入绑定；`SqliteSessionStore` 启动时迁移新增列；`build_dialogue_plain_for_archive` 抽至 `session_archive.py` 供 Orchestrator 复用。
- **校验**：`archive_llm_summary_enabled` 时要求解析出的 provider 存在于 `model_providers`。

---

### Release 0.4.25（2026-03-23）

**版本号**：`0.4.25`。

- **OpenAI 兼容嵌入 builtin**：`embedding_ref: builtin:openai_compatible` 调用 `/v1/embeddings`；密钥仅经 `memory_policy.embedding_openai.api_key_env` 所指环境变量（缺省块内字段与 `default_openai_compatible_embedding_params()` 一致）。
- **配置**：`memory_policy.yaml` 可选 `embedding_openai`（`api_key_env` / `base_url` / `model` / `timeout_seconds`）；`resolve_embedding_provider(..., policy=…)` 传入完整策略；entry point `pompeii_agent.embedding_providers` 工厂签名为 `(embedding_dim, policy | None) -> EmbeddingProvider`。
- **实现**：`infra/openai_compatible_embedding_provider.py`（`httpx`）；测试用可注入 `http_client`。

---

### 文档（2026-03-24）

- **继续开发手册**：新增 `docs/guides/继续开发手册.md`，汇总插拔设计完成度矩阵、主装配配置地图、entry points 速查、已知缺口（含 `LongTermMemoryStore` 与 `memory_store_ref` 未接线）及 P0–P3 Backlog；`docs/README.md`、`design/INDEX.md` 增加入口链接。

---

### Release 0.4.24（2026-03-23）

**版本号**：`0.4.24`。

- **长期记忆热插拔与会话存储对称**：新增 `app/memory_orchestrator_registry.py`（`resolve_dual_memory_store` / `resolve_embedding_provider`）；`memory_policy.yaml` 增加 `dual_store_ref`、`embedding_ref`（默认 `builtin:dual_sqlite` / `builtin:hash`）；`composition._try_build_memory_orchestrator` 仅通过注册表解析，不再硬编码具体实现类。
- **Entry point 组**：`pompeii_agent.memory_dual_stores`（`factory(Path) -> DualMemoryStore`）、`pompeii_agent.embedding_providers`（自 0.4.25 起 `factory(int, MemoryPolicyConfig | None) -> EmbeddingProvider`）；测试见 `tests/test_memory_orchestrator_registry.py`。

---

### Release 0.4.23（2026-03-23）

**版本号**：`0.4.23`。

- **长期记忆 P0–P3 工程落地**：`memory_policy.yaml` + `MemoryOrchestrator`；标准库表 `memory_items`、FTS5 `memory_fts`、向量表 `memory_vectors` 同库（`storage_profiles.memory.path`）；写入顺序为先标准库再向量投影；检索为 FTS + 余弦向量 + RRF 融合 + 可选 lexical rerank。
- **会话链路**：`AssemblyModuleImpl` 在 `build_initial_context` 调用 `retrieve_for_context`，经 `Context.memory_context_block` 注入模型 OpenAI 兼容路径的第二条 system；`/remember`、`/forget` 意图；归档在 `promote_on_archive` 为真时晋升长期记忆。
- **工具**：`composition` 注册 `search_memory`（`kernel.tool_allowlist` 已加入）；`resource_validation` 加载校验 `memory_policy.yaml`；测试夹具与 `tests/test_memory_dual_store_integration.py` 覆盖写入/检索/遗忘/归档晋升。

---

### Release 0.4.22（2026-03-23）

**版本号**：`0.4.22`。

- **长期记忆边界澄清**：文档明确向量库/向量检索尚未搭建；会话域 → 长期记忆的管理编排**未设计、未在核心路径实现**。
- **移除误实现**：删除 `LongTermMemoryBridge` / `MemoryPromotionPolicy` 及 `AgentCore` 归档后自动写入长期记忆、组装中注入桥接的逻辑；保留 `LongTermMemoryStore` 协议与 `memory_store_registry`（及 SQLite 示例子串实现）供后续设计落地后接线。
- **设计文档**：新增 `docs/design/会话与双库长期记忆架构设计.md`（标准库与向量库职责、会话内 S0–S7 调用逻辑、Orchestrator 写序与检索融合）；`长期记忆定义.md` 增加交叉引用。

---

### Release 0.4.21（2026-03-23）

**版本号**：`0.4.21`。

- **去兼容化清理**：移除模型层 legacy 回退路径（`_run_legacy`、`provider.params.system_prompt` 兜底、`deepseek` 默认 API key 回退、`prompt_profiles` 字符串旧形态、`tool_result_render` 字符串简写兼容），统一仅接受新规范配置。
- **规则升级**：`airules` 全局铁律新增“禁止保留旧接口/旧格式兼容分支”，明确工程落地后不得长期保留中间态兼容代码。

---

### Release 0.4.20（2026-03-23）

**版本号**：`0.4.20`。

- **Skill Registry 落地**：新增 `skills.yaml` 与 `skill_registry_loader`，技能项包含 `id/index/title/summary/content/quality_tier/enabled/tags`，实现“定义清晰、索引明确、质量分级”的技能注册框架。
- **技能运行注入**：模型层在 system prompt 渲染后按 `session.skills` 注入 `active_skills` 区块，技能内容由注册表驱动；未知技能在启动校验阶段拦截。
- **Prompt Cache 落地**：新增 `infra/prompt_cache.py`（TTL + LRU），用于系统提示词合并结果缓存，降低重复渲染开销。
- **资源校验增强**：`resource_validation` 新增 `skills.yaml` 校验与 `session.skills` 交叉一致性校验。

---

### Release 0.4.19（2026-03-23）

**版本号**：`0.4.19`。

- **资源区收敛（提示词解耦）**：新增 `prompts.yaml`，将 `model_providers.yaml` 中提示词与回流策略字段拆分到独立 PromptRegistry（按 provider id 合并注入），实现“模型连接参数”与“提示词策略参数”分仓。
- **统一加载与校验**：新增 `prompt_config_loader` 并接入 `composition/resource_validation`，启动时完成 providers+prompts 合并与一致性校验（禁止未知 provider 注入）。

---

### Release 0.4.18（2026-03-23）

**版本号**：`0.4.18`。

- **工具插件自动发现**：`tools.yaml` 新增 `enable_entrypoints` 与 `entrypoint_group`，支持从 Python entry_points 自动发现并注册工具（显式配置同名优先覆盖）。
- **统一资源校验中心**：新增 `resource_validation`，在 `build_core` 启动阶段统一校验 `model/session/kernel/runtime/tools/mcp` 配置并做跨配置一致性检查（如 `tool_confirmation_required ⊆ tool_allowlist`、本地工具与设备路由名冲突检测）。

---

### Release 0.4.17（2026-03-23）

**版本号**：`0.4.17`。

- **工具架构（最终版解耦）**：移除 core 与 tools 中的工具名硬编码路径。新增 `tools.yaml` 声明式注册（`local_handlers` + `device_routes`），`ToolModuleImpl` 通过动态加载 handler 与配置路由工作；core 改为调用 `ToolModule.resolve_device_request()`，不再依赖固定 `take_photo` 路由函数。
- **热插拔能力**：新增 `tool_registry_loader` 与 `load_tool_handler("module:function")`，新增工具可通过配置注册而无需修改核心编排源码。

---

### Release 0.4.16（2026-03-23）

**版本号**：`0.4.16`。

- **提示词配置校验（加载期）**：`load_model_registry` 新增对提示词相关参数的结构校验（`prompt_profiles`、`user_prompt_profiles`、`prompt_vars_env`、`user_prompt_vars_env`、`tool_result_render`、`tool_first_tools`、`user_input_max_chars`）。错误配置在启动加载阶段直接报错，避免运行时隐性失效。

---

### Release 0.4.15（2026-03-23）

**版本号**：`0.4.15`。

- **提示词架构（用户输入稳定化）**：用户输入在注入 `user_prompt_profiles` 前新增标准化流程（统一换行、去除 NUL 字符），并支持 `params.user_input_max_chars` 限长裁剪（`0` 表示不限制），提升长输入与异常字符场景的稳定性。

---

### Release 0.4.14（2026-03-23）

**版本号**：`0.4.14`。

- **提示词架构（用户提示词模板）**：新增 `params.user_prompt_profiles`，支持将用户输入以模板方式注入为结构化 `user` 消息（例如 `<user_request>{user_input}</user_request>`）；并支持 `user_prompt_vars` / `user_prompt_vars_env` 变量注入。未配置时保持兼容，默认继续使用原始用户输入。

---

### Release 0.4.13（2026-03-23）

**版本号**：`0.4.13`。

- **提示词架构（变量注入）**：在 `prompt_profiles` 资源模板基础上新增变量渲染层。支持 `params.prompt_vars`（静态变量）与 `params.prompt_vars_env`（环境变量注入）统一管理模板参数；并提供内建运行时变量（如 `prompt_strategy`、`channel`、`today`）。

---

### Release 0.4.12（2026-03-23）

**版本号**：`0.4.12`。

- **提示词架构（tool_first 触发条件配置化）**：新增 `params.tool_first_tools`，支持白名单控制 `tool_first` 直出仅对指定工具生效；支持两种写法：`list[str]`（全局白名单）与 `mapping[strategy -> list[str]]`（按 strategy 细分）。未配置时保持兼容，默认允许所有工具。

---

### Release 0.4.11（2026-03-23）

**版本号**：`0.4.11`。

- **提示词架构（工具结果渲染）**：新增 `params.tool_result_render`（`raw` / `short` / `short_with_reason`，支持按 strategy 配置）。在 `tool_first` 回流轮次下，工具结果直出格式可配置，不再固定单一渲染。

---

### Release 0.4.10（2026-03-23）

**版本号**：`0.4.10`。

- **提示词架构（tool_first 执行化）**：当 `session.prompt_strategy=tool_first` 且进入“工具结果回流轮次”时，模型层优先直出工具结论（如 `ping -> pong`、`add -> 5`），避免再次生成冗长解释文本。该行为仅在工具回流上下文触发，不影响普通对话策略。

---

### Release 0.4.9（2026-03-23）

**版本号**：`0.4.9`。

- **提示词架构（二层策略）**：新增会话级 `session.prompt_strategy`；`prompt_profiles` 支持 `profile -> strategy` 嵌套结构。模型层解析优先级升级为：`profile+strategy -> profile.default -> default+strategy -> default.default -> legacy string profile -> system_prompt`，兼容旧配置并支持更细粒度提示词策略切换（如 `concise`、`tool_first`）。

---

### Release 0.4.8（2026-03-23）

**版本号**：`0.4.8`。

- **提示词架构（配置化）**：会话配置新增 `session.prompt_profile`；模型配置支持 `providers.<id>.params.prompt_profiles`，模型层按“会话档位 -> default 档位 -> legacy system_prompt”优先级解析 system prompt，实现多 provider 通用提示词档位切换。
- **默认模板**：`model_providers.yaml` 为 `deepseek/openai` 增加 `prompt_profiles` 示例（`default`、`strict`），便于后续提示词工程与 A/B 调整。

---

### Release 0.4.7（2026-03-23）

**版本号**：`0.4.7`。

- **MCP**：`mcp_servers.yaml` 默认 **`enabled: true`**，便于本地验证 `/tool ping`、`/tool add`；不需要时改为 `false` 并重启。

---

### Release 0.4.6（2026-03-23）

**版本号**：`0.4.6`。

- **安全与仓库布局**：删除仓库根目录 **`config/`**（原含 `env.ps1.example`、`.env.example`），避免对外暴露密钥模板路径；本地仅使用根目录 **`env.ps1`**（gitignore）或系统环境变量注入 `DEEPSEEK_API_KEY`。`scripts/load_env.ps1` 仅加载根目录 `env.ps1`。运行时 YAML 仍在 **`src/platform_layer/resources/config/`**，不受影响。

---

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

