---
name: layering
description: 严格分层架构，只允许向下依赖，禁止跨层引用和同层具体实现互相依赖。新建文件或添加import时加载。
metadata:
  priority: L2
  category: principles
  depends: module-boundary
---

# 严格分层，禁止跨层依赖

## 规则

- **依赖方向只允许向下** — 上层可以依赖下层，下层绝不能依赖上层
- **同层之间禁止通过具体实现互相依赖** — 应通过接口、事件总线或依赖注入解耦
- **每个文件的 import 语句必须符合分层方向** — 违反即为架构破坏
- **跨层通信必须通过架构规划的通道**（事件、回调、接口），不允许直接引用

## 项目分层结构

```
外部/运行环境（用户输入、设备、网络）
  ↓ 可依赖
app（装配/运行时：composition + runtime）
  ↓ 可依赖
port（边界适配：输入事件/输出事件 emit）
  ↓ 可依赖
core（微内核编排：会话 + loop + 路由 + 安全门）
  ↓ 可依赖
modules（处理模块：assembly / model / tools）
  ↓ 可依赖
platform（基础能力：配置读取、序列化、资源访问；不得依赖 core）
  ↓ 可依赖
infra（外部基础设施实现：DB/MCP/网络客户端等；可为空）
```

### 依赖方向约束（用于审查 import）

- **app**：可以依赖所有层（它是组合根）
- **port**：可以依赖 `core`（调用内核），不得依赖 `app`
- **core**：不得依赖 `app/port`；可以依赖 `modules` 接口与 `platform` 基础能力
- **modules**：不得依赖 `app/port`；可依赖 `core` 的共享类型与协议
- **platform/infra**：不得依赖 `core/app/port/modules`

## 示例

✅ 正确：
```typescript
// UI层 → 引用业务层（向下依赖）
import { useUserProfile } from '@/features/user';

// 业务层 → 引用核心层（向下依赖）
import { eventBus } from '@/core/event-bus';

// 同层通过事件通信（解耦）
eventBus.emit('user:updated', userData);
```

❌ 错误：
```typescript
// 核心层 → 引用UI层（向上依赖，严重违规！）
import { UserCard } from '@/components/UserCard';

// 同层直接引用具体实现（耦合）
import { PaymentService } from '../payment/PaymentService';
// 应该通过接口：import type { IPaymentService } from '@/core/interfaces';
```

## 判断方法

添加 `import` 时问自己：
1. "被引用的文件在哪一层？我在哪一层？" → 必须是我引用下层
2. "如果被引用的模块被删除/重写，我需要改吗？" → 是 → 耦合过紧，应加接口层

## 提交前检查清单

- [ ] 所有新增的 `import` 语句都符合向下依赖方向
- [ ] 没有下层文件 import 上层文件
- [ ] 同层模块之间没有直接 import 具体实现
- [ ] 跨层通信使用了架构规划的通道（事件/接口/回调）
