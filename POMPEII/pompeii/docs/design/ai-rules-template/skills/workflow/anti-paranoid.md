---
name: anti-paranoid
description: bug修复的正确流程：追溯根因→修复→清理。区分架构级校验与补丁级校验，禁止防御性冗余代码。修复bug时加载。
metadata:
  priority: L1
  category: workflow
  depends: error-handling, stub-management
---

# 反防御式编程（Anti-Paranoid Coding）

## 问题背景

AI助手修bug时常见的"安全习惯"：遇到空值就加 `?.`，遇到异常就包 `try-catch`，遇到类型不匹配就加 `as any`。这些做法**掩盖了根因**，代码量膨胀，真正的bug被埋得更深。

**铁律：修完bug后，代码量应持平或减少。如果增加了，说明你在"贴补丁"而不是"修根因"。**

## 规则

### 1. Bug修复三步法

```
Step 1: 追溯根因
  → 这个错误最早从哪里产生？（不是从哪里被发现的）
  → 用调试日志/断点确认，不要猜

Step 2: 在根因处修复
  → 修复点应该尽可能接近错误的产生位置
  → 修完后下游的防御代码应该变得不需要

Step 3: 清理下游防御代码
  → 移除因该bug而添加的临时防御代码
  → 验证移除后功能仍正常
```

### 2. 区分两类校验

| 类型 | 含义 | 示例 | 允许？ |
|------|------|------|--------|
| **架构级校验** | 对外部输入/系统边界的校验，永远需要 | API参数校验、用户输入校验、文件格式校验 | ✅ 永远需要 |
| **补丁级校验** | 对系统内部传值的防御性检查，说明上游有bug | 函数内部 `if (!user) return` 但调用方保证传了user | ❌ 应修上游bug |

### 3. 禁止的"修bug"模式

❌ **可选链滥用**：
```typescript
// 问题：user有时是undefined
// 错误修法：到处加?.
const name = user?.profile?.name ?? 'Unknown';
// 正确修法：找到user为什么是undefined，从源头修
```

❌ **try-catch掩盖**：
```typescript
// 问题：JSON解析偶尔报错
// 错误修法：包try-catch返回默认值
try { return JSON.parse(data); } catch { return {}; }
// 正确修法：找到data为什么不是合法JSON，从数据源修
```

❌ **类型断言绕过**：
```typescript
// 问题：类型不匹配
// 错误修法：as any / @ts-ignore
const result = brokenFunction() as any;
// 正确修法：修正函数的返回类型或调用方的期望类型
```

## 示例

✅ 正确的bug修复：
```typescript
// Bug: 用户列表偶尔显示undefined
// 追溯: API返回的数据中nickname字段有时缺失
// 修复: 在API数据层统一处理（架构级校验 — 外部数据边界）
function normalizeUser(raw: unknown): User {
  const data = validateUserSchema(raw);  // 在边界校验
  return {
    name: data.nickname ?? data.username,  // 在数据层处理默认值
    // ...
  };
}
// 效果: UI层不需要任何?.防御，数据层保证了类型完整性
```

## 提交前检查清单

- [ ] bug的根因已定位，不是在症状处打补丁
- [ ] 修复点在错误产生位置附近，不在错误发现位置
- [ ] 修改后的代码量持平或减少（不是增加了大量防御代码）
- [ ] 新增的空值检查是架构级校验（外部输入边界），不是补丁级校验
- [ ] 没有使用 `?.` / `try-catch` / `as any` 来掩盖根因
