---
name: error-handling
description: 自定义错误类、错误信息规范、异步错误处理、故障隔离策略。写错误处理或catch块时加载。
metadata:
  priority: L1
  category: principles
---

# 错误处理一致性

## 规则

- **使用自定义错误类**，按模块或功能分类，不用裸 `Error`
- **错误信息必须包含上下文** — 哪个模块、什么操作、什么原因
- **异步操作必须有错误处理** — 每个 `await` / `Promise` 都要考虑失败路径
- **核心模块的错误不能导致整个应用崩溃** — 故障隔离，非核心功能失败不影响主流程

## 示例

✅ 正确：
```typescript
// 自定义错误类，携带上下文
class RegistryError extends AppError {
  constructor(moduleId: string, reason: string) {
    super(`[Registry] 模块 "${moduleId}": ${reason}`);
  }
}

// 使用时 — 错误信息清晰可追溯
throw new RegistryError('user-panel', '已注册，不能重复注册');

// 异步错误处理 — 明确的失败路径
try {
  await loadModule(id);
} catch (error) {
  if (error instanceof ModuleNotFoundError) {
    logger.warn(`模块 ${id} 不存在，跳过加载`);
    return fallbackModule;  // 优雅降级
  }
  throw error;  // 未知错误向上抛出
}
```

❌ 错误：
```typescript
// 裸Error，没有上下文
throw new Error("already registered");  // 谁注册了？在哪？

// 吞掉错误 — 问题被隐藏
try {
  await loadModule(id);
} catch (e) {
  // 空catch — 错误被静默吞掉，永远不知道出了问题
}

// 不区分错误类型 — 所有错误同样处理
try { /* ... */ } catch (e) {
  console.log('error');  // 丢失了所有错误信息
}
```

## 错误处理策略

| 错误类型 | 处理方式 |
|----------|---------|
| 可预期的业务错误（如验证失败） | 捕获 → 返回用户友好信息 |
| 可恢复的运行时错误（如网络超时） | 捕获 → 重试/降级/通知用户 |
| 不可恢复的系统错误（如内存不足） | 记录日志 → 安全关闭 |
| 编程错误（如类型不匹配） | **不捕获** → 让它崩溃 → 修代码 |

## 提交前检查清单

- [ ] 新抛出的错误使用了自定义错误类，不是裸 `Error`
- [ ] 错误信息包含模块名、操作名、原因
- [ ] 每个 `await` 都有错误处理（try-catch 或 .catch）
- [ ] 没有空的 catch 块
- [ ] 非核心功能的错误不会导致应用崩溃
