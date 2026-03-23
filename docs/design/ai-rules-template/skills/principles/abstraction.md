---
name: abstraction
description: 抽象层设计规范，每个抽象必须能一句话说清职责，禁止过度抽象。新建接口或基类时加载。
metadata:
  priority: L3
  category: principles
  depends: naming
---

# 一个抽象层，易懂的抽象层

## 规则

- **每个抽象层（接口、基类、泛型）必须能用一句话说清楚它的职责**，说不清楚就需要拆分或重构
- **不允许"为了抽象而抽象"** — 每个接口必须有至少两个可预见的实现
- **抽象层的命名必须直觉可懂**，不允许无意义缩写或过长的组合词
- **继承层级不超过3层** — 超过则改用组合（composition）

## 示例

✅ 正确：
```typescript
// 一句话：用户数据的存取入口
interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}

// 两个可预见实现：数据库版 和 内存版（测试用）
class DatabaseUserRepository implements UserRepository { /* ... */ }
class InMemoryUserRepository implements UserRepository { /* ... */ }
```

❌ 错误：
```typescript
// 说不清楚这是干什么的
interface AbstractGenericProcessorFactory<T, U, V> { /* ... */ }

// 只有一个实现，抽象毫无意义
interface IUserService { /* ... */ }
class UserService implements IUserService { /* ... */ }  // 永远只有这一个
```

## 判断标准

新建抽象时问自己：
1. "能用一句话说清这个抽象的职责吗？" → 不能 → 设计有问题
2. "能想到至少两个不同的实现吗？" → 不能 → 可能不需要抽象
3. "去掉这层抽象，调用方代码会变复杂吗？" → 不会 → 不需要抽象

## 提交前检查清单

- [ ] 新建的每个接口/基类都能用一句话描述职责
- [ ] 新建的每个接口都有至少两个可预见的实现场景
- [ ] 继承层级未超过3层
- [ ] 没有出现只有一个实现的接口（除非架构规划中明确预留扩展点）
