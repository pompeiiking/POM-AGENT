---
name: testing
description: 测试文件位置、命名、最小覆盖要求、临时调试测试的处理规范。写测试或改测试时加载。
metadata:
  priority: L2
  category: workflow
  depends: naming
---

# 测试规范

## 规则

- **测试文件与源文件同目录或统一测试目录** — 项目选择一种并全项目统一
- **测试文件命名**: `[源文件名].test.[ext]` 或 `[源文件名].spec.[ext]`
- **每个公共函数/方法至少有一个正例和一个反例测试**
- **测试只测行为，不测实现细节** — 重构不应导致测试失败

## 测试文件位置

[TODO:选择一种并填充]
```
方案A: 就近放置（推荐小项目）
  src/features/user/
    UserService.ts
    UserService.test.ts

方案B: 统一测试目录（推荐大项目）
  src/features/user/UserService.ts
  tests/features/user/UserService.test.ts
```

## 测试结构模板

```typescript
describe('UserService', () => {
  // 一个describe对应一个被测模块

  describe('getUserById', () => {
    // 一个内层describe对应一个被测方法

    it('应返回存在的用户', () => {
      // 正例：正常路径
    });

    it('用户不存在时应返回null', () => {
      // 反例：边界情况
    });

    it('参数为空字符串时应抛出错误', () => {
      // 反例：异常输入
    });
  });
});
```

## 临时调试测试

开发过程中写的临时测试（用于调试、验证假设）：
- 用 `// DEBUG-TEST` 标记
- **不允许合并到主分支** — 提交前删除或转化为正式测试
- 转化：去掉 `DEBUG-TEST` 标记，补充断言，使其成为正式测试

## 示例

✅ 正确：
```typescript
// 测试行为，不测实现
it('注册成功后应返回用户ID', async () => {
  const result = await service.register(validInput);
  expect(result.userId).toBeDefined();
  expect(result.userId).toMatch(/^usr_/);
});
```

❌ 错误：
```typescript
// 测试实现细节 — 重构时会无故失败
it('应调用repository的save方法', async () => {
  await service.register(validInput);
  expect(mockRepo.save).toHaveBeenCalledTimes(1);  // 内部实现细节
});
```

## 提交前检查清单

- [ ] 测试文件命名和位置符合项目约定
- [ ] 新增的公共函数/方法有正例和反例测试
- [ ] 测试验证行为而非实现细节
- [ ] 没有残留的 `DEBUG-TEST` 临时测试
- [ ] 所有测试通过
