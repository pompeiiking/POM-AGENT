---
name: interface-contract
description: 人类标注的接口契约文档规范。多人使用不同AI开发不同模块时，通过契约文档统一接口设计，保障对接效率。开发涉及模块间通信或调用其他模块时加载。
metadata:
  priority: L1
  category: workflow
  depends: interface-change, type-safety, naming
---

# 接口契约（Interface Contract）

## 问题背景

团队中多个开发者使用不同AI工具（Cursor、Windsurf、Copilot等）分别开发不同模块。每个AI只了解自己负责的模块，**不了解其他模块的实现细节**。如果没有统一的接口定义，对接时会出现：

- 参数类型不匹配
- 事件名/载荷结构不一致
- 返回值格式各异
- 错误处理方式冲突

**接口契约是由人类（架构师/技术负责人）编写的"对接合同"，所有AI必须读懂并严格遵守。**

## 核心原则

1. **契约先于实现** — 先写接口契约，再让各AI按契约开发
2. **契约由人类编写和变更** — AI不得自行修改契约文档，只能提出修改建议
3. **契约是唯一真相** — 当代码与契约冲突时，以契约为准修改代码
4. **一个接口点一份契约** — 不在多处重复定义同一接口

## 契约文档位置

```
项目根目录/
└── contracts/
    ├── _index.md                    # 契约索引（必须）
    ├── _template.contract.md        # 空白模板（复制后填充）
    ├── shared-types.contract.md     # 全局共享类型定义
    ├── user-payment.contract.md     # 用户模块↔支付模块（示例）
    └── user-notification.contract.md # 用户模块↔通知模块（示例）
```

- 每对需要对接的模块创建一个 `[模块A]-[模块B].contract.md`
- 全局共享类型放在 `shared-types.contract.md`
- 新增契约后必须在 `_index.md` 索引中登记

## 契约文档格式

### 每份契约必须包含以下结构：

```markdown
# [模块A] ↔ [模块B] 接口契约

> 状态: [草案/已确认/已实现/已弃用]
> 负责人: [人类开发者名]
> 最后更新: [日期]
> 实现方: A侧=[开发者/AI], B侧=[开发者/AI]

## 共享类型

​```typescript
// 双方都必须使用的类型定义
interface OrderItem {
  productId: string;
  quantity: number;
  unitPrice: number;
}
​```

## 函数接口

### [接口名称]

- **调用方**: [谁调用]
- **提供方**: [谁实现]
- **签名**:
  ​```typescript
  function processOrder(order: OrderItem[]): Promise<OrderResult>
  ​```
- **前置条件**: [调用前必须满足什么]
- **后置条件**: [调用后保证什么]
- **错误处理**: [会抛出什么错误，调用方如何处理]

## 事件接口

### [事件名称]

- **发布方**: [谁发布]
- **订阅方**: [谁订阅]
- **事件名**: `order:completed`
- **载荷类型**:
  ​```typescript
  interface OrderCompletedPayload {
    orderId: string;
    totalAmount: number;
    completedAt: Date;
  }
  ​```
- **触发时机**: [什么情况下发布此事件]
- **幂等性**: [订阅方是否需要处理重复事件]

## 约束与边界

- [双方必须遵守的业务规则]
- [性能约束：响应时间、并发量等]
- [数据约束：字段长度、值范围等]
```

## AI行为规则

### 开发前（必做）

```
1. 阅读与当前模块相关的所有契约文档
2. 确认自己是接口的"调用方"还是"提供方"
3. 如果契约状态是"草案" → 提醒人类开发者确认后再实现
```

### 开发中

- **严格按契约定义的类型、参数、返回值实现** — 不自行"优化"接口签名
- **契约中定义的事件名、载荷结构不可修改** — 即使你觉得有更好的命名
- **发现契约有问题（遗漏、矛盾、不合理）时**：
  → 不要自行修改契约
  → 在代码中添加 `// CONTRACT-ISSUE: [描述问题]` 标记
  → 向人类开发者报告，建议修改方案
  → 等待人类确认后再实施修改

### 开发后

- **实现完成后，在契约文档中更新状态**: `草案` → `已实现`
- **在CHANGELOG中标注**: "实现了 [契约名] 的 [调用方/提供方] 侧"

### 禁止的行为

- ❌ **修改契约中的接口签名**（即使当前实现更方便）
- ❌ **添加契约中未定义的参数或返回字段**（除非标注为可选扩展字段）
- ❌ **忽略契约中定义的错误处理方式**
- ❌ **使用与契约不同的事件名或载荷结构**

## 示例

### ✅ 正确：严格遵循契约

契约定义：
```typescript
// contracts/user-payment.contract.md 中定义
interface PaymentRequest {
  userId: string;
  amount: number;
  currency: 'CNY' | 'USD';
}

function createPayment(req: PaymentRequest): Promise<PaymentResult>
```

A侧AI（用户模块，调用方）的实现：
```typescript
// 严格按契约类型调用
const result = await paymentService.createPayment({
  userId: currentUser.id,
  amount: order.totalPrice,
  currency: 'CNY',
});
```

B侧AI（支付模块，提供方）的实现：
```typescript
// 严格按契约签名实现
async createPayment(req: PaymentRequest): Promise<PaymentResult> {
  // 实现细节...
}
```

### ❌ 错误：自行修改接口

```typescript
// B侧AI觉得加个discount参数"更好"，自行修改了签名
async createPayment(req: PaymentRequest & { discount?: number }): Promise<PaymentResult>
// A侧AI完全不知道有这个字段！对接时必然出问题
```

### ❌ 错误：忽略契约中的错误处理

```typescript
// 契约规定抛出 PaymentError，但AI用了通用Error
throw new Error('支付失败');  // 应该是 throw new PaymentError(...)
```

## 契约变更流程

```
1. 人类开发者提出变更需求
2. 更新契约文档（修改接口定义、标注变更原因）
3. 在契约文档中标注版本: v1 → v2
4. 通知所有相关模块的开发者/AI
5. 各方按新契约更新代码
6. 确认所有方更新完成后，删除旧版本标注
```

## 契约索引模板（方案B使用）

```markdown
# 接口契约索引

| 契约文件 | 模块 | 状态 | 负责人 |
|----------|------|------|--------|
| `user-payment.contract.md` | 用户↔支付 | 已实现 | Alice |
| `user-notification.contract.md` | 用户↔通知 | 草案 | Bob |
| `shared-types.contract.md` | 全局共享类型 | 已确认 | Alice |
```

## 提交前检查清单

- [ ] 已阅读当前模块相关的所有契约文档
- [ ] 实现的接口签名与契约完全一致（参数名、类型、返回值）
- [ ] 事件名和载荷结构与契约完全一致
- [ ] 错误处理方式与契约定义一致
- [ ] 没有自行添加契约中未定义的参数或字段
- [ ] 发现的契约问题已用 `CONTRACT-ISSUE` 标记并报告
- [ ] 实现完成后已更新契约状态
