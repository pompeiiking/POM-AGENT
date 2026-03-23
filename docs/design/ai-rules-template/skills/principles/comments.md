---
name: comments
description: 注释最小化原则，只注释"为什么"不注释"做什么"，禁止注释掉的代码。添加注释或文档时加载。
metadata:
  priority: L3
  category: principles
---

# 注释与文档最小化

## 规则

- **代码应该是自解释的** — 好的命名胜过注释
- 只在以下场景添加注释：
  1. **"为什么"而非"做什么"** — 解释设计决策，不解释代码逻辑
  2. **非直觉的性能优化** — 说明为什么选择了看起来不直觉的写法
  3. **公共API的参数和返回值说明** — JSDoc / docstring
  4. **TODO标记** — 格式：`// TODO(日期): 具体内容`
- **禁止注释掉的代码** — 直接删除，git有历史记录
- **禁止与代码不一致的注释** — 比不注释更糟糕

## 示例

✅ 正确：
```typescript
// 使用WeakMap而非Map，因为模块卸载后需要自动释放引用，避免内存泄漏
const moduleCache = new WeakMap<Module, CacheEntry>();

/**
 * 计算用户的活跃分数
 * @param activities - 近30天内的用户活动记录
 * @returns 0-100之间的活跃分数
 */
function calculateActivityScore(activities: Activity[]): number {
  // ...
}
```

❌ 错误：
```typescript
// 获取用户（废话注释，代码本身已说明）
const user = getUser();

// i++（逐行注释，说明代码不够清晰）
i++;

// const oldApi = fetch('/v1/users');  ← 注释掉的代码，应直接删除

// 发送邮件（但代码其实是发送短信 — 注释与代码不一致）
sendSms(phone, message);
```

## 提交前检查清单

- [ ] 新增注释解释的是"为什么"而非"做什么"
- [ ] 没有注释掉的代码残留
- [ ] 现有注释与修改后的代码仍然一致
- [ ] 公共API有参数和返回值文档
