# Pompeii-Agent 项目规范

TEMPLATE_STATUS: INITIALIZED:Pompeii-Agent

---

## ⓪ AI接入协议

**当你被要求阅读此规范时，按以下流程执行：**

1. 检查上方 `TEMPLATE_STATUS`
   - 若为 `UNINITIALIZED` → 阅读 `skills/_bootstrap.md`，执行转化流程
   - 若为 `INITIALIZED` → 继续下一步
2. 阅读 `STATUS.md`（如存在），快速了解项目当前状态
3. 若当前任务涉及跨模块调用或通信 → 阅读 `contracts/` 中的相关契约
4. 根据当前任务，从下方 Skill索引 匹配并加载所需skill文件
5. 开始工作

---

## 一、全局铁律

**以下8条规则无条件生效，不需要加载任何skill，任何时候都必须遵守：**

1. **禁止未标注的假实现** — 写占位代码必须带 `// STUB(日期): 原因 — 替换计划`，三要素缺一不可
2. **修bug修根因，不堆防御代码** — 修完后代码量应持平或减少，不允许用 try-catch/null检查 掩盖错误
3. **类型安全严格模式** — 禁用 `any` / `@ts-ignore` / `# type: ignore` 等逃生舱，类型问题必须正面解决
4. **密钥凭证不入代码库** — API Key、密码、token等敏感信息只走环境变量，不硬编码、不写入日志
5. **每次变更必记CHANGELOG** — 无记录的变更视为未发生，包含变更文件列表和影响范围
6. **接口契约不可由AI擅自修改** — 契约文档由人类编写和变更，AI发现问题只能标记报告，不能自行改动
7. **规范文档修改必须溯源** — 修改 RULES.md / skills / contracts/ 等规范文档前须获得人类授权，修改后必须在CHANGELOG中记录变更前/后对比、理由和授权来源
8. **禁止保留旧接口/旧格式兼容分支** — 工程落地后必须移除 legacy fallback、旧字段兼容、旧协议回退；统一迁移到新规范，禁止“中间态长期共存”

---

## 二、优先级分层

**当规则之间发生冲突时，按此顺序决定：**

- **L1 安全与正确性** > **L2 架构与一致性** > **L3 风格与效率**
- L1: type-safety, error-handling, stub-management, anti-paranoid, security, interface-contract, interface-change
- L2: layering, zero-hardcoding, data-separation, module-boundary, naming, collaboration, changelog, status-management, session-handoff, git-commit, testing, file-structure
- L3: abstraction, comments, performance, code-style

---

## 三、Skill索引

<!-- AI：根据当前任务匹配以下description，加载 skills/ 目录下对应文件 -->

### principles/ — 设计原则

- **zero-hardcoding** — 所有可变值必须来自配置或常量，禁止魔术数字和魔术字符串。写任何新代码时加载。
- **abstraction** — 抽象层设计规范，每个抽象必须能一句话说清职责。新建接口或基类时加载。
- **data-separation** — 数据文件与代码文件严格分离，通过接口访问数据。涉及数据文件或配置时加载。
- **layering** — 严格分层架构，只允许向下依赖，禁止跨层引用。新建文件或添加import时加载。
- **module-boundary** — 模块入口出口规范，资源获取释放对称，统一index导出。新建模块时加载。
- **naming** — 文件、变量、函数、类的命名一致性规范。新建任何标识符时加载。
- **comments** — 注释最小化原则，只注释"为什么"不注释"做什么"。添加注释或文档时加载。
- **type-safety** — 强类型严格模式的具体规则和语言专属配置。写类型声明或遇到类型问题时加载。
- **stub-management** — STUB标记的完整规范：格式、必填字段、记录要求、替换流程。写占位代码或新会话搜索STUB时加载。
- **error-handling** — 自定义错误类、错误信息规范、故障隔离策略。写错误处理或catch块时加载。
- **performance** — 执行频率意识、高频路径禁忌、异步加载策略。涉及渲染循环或高频调用路径时加载。

### workflow/ — 工作流程

- **anti-paranoid** — bug修复的正确流程：追溯根因→修复→清理。区分架构级校验与补丁级校验。修复bug时加载。
- **collaboration** — 多AI协作行为准则：先读后写、最小变更、不删不懂的代码、不引入新依赖。每次会话快速浏览。
- **changelog** — CHANGELOG格式规范、写入规则、操作者标识。提交变更时加载。
- **status-management** — STATUS.md的维护规范：项目状态快照、任务交接、STUB清单。会话开始或结束时加载。
- **git-commit** — Git提交信息格式、scope定义、提交频率。提交代码时加载。
- **testing** — 测试文件位置、命名、生命周期、临时调试测试的处理。写测试或改测试时加载。
- **session-handoff** — AI会话交接协议：结束时必做项、新会话启动流程、任务交接模板。会话开始或结束时加载。
- **interface-change** — 公共接口变更流程：兼容性策略、影响评估、版本迁移。修改公共接口时加载。
- **security** — 密钥管理、环境变量、敏感数据处理、依赖安全。涉及认证、密钥、外部API时加载。
- **interface-contract** — 人类标注的接口契约规范。多人/多AI分模块开发时，按契约统一接口设计保障对接。开发涉及模块间调用或通信时加载。

### project/ — 项目专属（模板态为TODO骨架）

- **file-structure** — 项目目录结构、新增文件放置规则、禁止创建的文件、文档封闭清单。新建文件时加载。
- **code-style** — 项目代码风格：文件内部结构顺序、组件写法模板、样式方案。写代码时加载。

### 常见任务预设组合

| 任务类型 | 加载skill |
|----------|-----------|
| **新会话启动** | collaboration + session-handoff + status-management + stub-management |
| **新功能开发** | naming + layering + zero-hardcoding + type-safety + changelog |
| **修复bug** | anti-paranoid + error-handling + stub-management + changelog |
| **新建模块** | module-boundary + abstraction + naming + layering + file-structure |
| **接口变更** | interface-change + interface-contract + layering + changelog |
| **跨模块开发** | interface-contract + module-boundary + naming + type-safety |
| **写测试** | testing + naming |
| **提交代码** | git-commit + changelog |
| **涉及外部API/密钥** | security + error-handling |

---

## 四、文档体系

**本项目允许存在的文档文件（封闭清单）：**

| 文件 | 职责 | 更新方式 |
|------|------|---------|
| `RULES.md`（本文件） | 全局铁律、Skill索引、AI接入协议 | 仅人类开发者授权修改 |
| `STATUS.md` | 项目当前状态快照：进度、交接、STUB清单、已知问题 | 每次变更后**覆盖更新** |
| `CHANGELOG.md` | 纯变更日志：谁在何时改了什么 | 每次变更后**追加** |
| `README.md` | 项目简介、快速启动 | 里程碑时更新 |
| `contracts/` 目录 | 模块间接口契约：类型、签名、事件、约束 | 仅人类开发者编写和变更，AI更新状态字段 |
| `docs/design/架构设计ver0.5.md`（ver0.6） | 架构图纸、接口清单、记忆子系统（单一架构参考源） | 里程碑/重大决策时更新 |
| `docs/design/archive/架构设计ver0.4.md` | 原始五关卡全文（ver0.6 继承） | 归档参考 |

```
不在此清单中的文档文件不允许创建。
如需新增，必须人类开发者明确要求，并在此清单中登记。
```

---

## 五、本文件维护规则

- AI助手不得自行修改 RULES.md — 必须获得人类开发者明确授权
- 授权场景：人类主动要求修改，或完整性检查发现确实的缺陷（如索引与文件不一致）经人类确认
- 修改后必须按铁律#7执行溯源记录（见 changelog skill 规范变更模板）
- 如果AI认为某条规则需要修改，应向人类开发者提出建议，而非直接修改
- 当 RULES.md 与其他文档冲突时，RULES.md 优先级最高
