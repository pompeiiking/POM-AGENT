---
name: performance
description: 执行频率意识、高频路径禁忌、精确订阅、异步加载策略。涉及渲染循环或高频调用路径时加载。
metadata:
  priority: L3
  category: principles
---

# 性能意识

## 规则

- **新增代码时必须考虑其执行频率** — 一次性初始化 vs 每帧渲染 vs 每次交互，策略完全不同
- **高频执行路径禁止**：运行时内存分配（`new` 对象）、DOM操作、同步重计算、`JSON.parse/stringify`
- **状态变更只通知真正关心的消费者** — 精确订阅，避免全局广播导致无关组件重渲染
- **异步加载非关键资源** — 不阻塞主流程和首屏渲染

## 示例

✅ 正确：
```typescript
// 高频路径 — 预分配对象，避免每帧new
const _tempVec = new Vector3();  // 复用
function onFrame() {
  _tempVec.set(x, y, z);  // 修改已有对象
  applyTransform(_tempVec);
}

// 精确订阅 — 只订阅需要的字段
const userName = useStore(state => state.user.name);  // 只有name变化才重渲染
```

❌ 错误：
```typescript
// 高频路径 — 每帧分配新对象（GC压力）
function onFrame() {
  const pos = new Vector3(x, y, z);  // 每帧new！60fps = 每秒60个对象
  applyTransform(pos);
}

// 粗粒度订阅 — 任何state变化都重渲染
const state = useStore(state => state);  // 订阅整个store
```

## 执行频率分类

| 频率 | 典型场景 | 允许的操作 | 禁止的操作 |
|------|---------|-----------|-----------|
| 一次性 | 初始化、模块加载 | 任何操作 | 无限制 |
| 低频 | 按钮点击、表单提交 | DOM操作、网络请求 | 无限制 |
| 中频 | 滚动、拖拽、窗口resize | 节流后的轻量计算 | 大量DOM操作 |
| 高频 | 每帧渲染(60fps)、动画 | 纯数学计算、复用对象 | new对象、DOM读写、JSON序列化 |

## 项目专属性能预算

[TODO:填充你的项目性能指标，如:]
```
- 首屏加载时间: < 3s (4G网络)
- 帧率: 稳定60fps（3D场景下可降至30fps）
- 包体积: 首屏JS < 200KB (gzip)
```

## 提交前检查清单

- [ ] 新代码已评估执行频率（一次性/低频/中频/高频）
- [ ] 高频路径中没有 `new` 对象、DOM操作、`JSON.parse/stringify`
- [ ] 状态订阅是精确的（只订阅需要的字段），不是全局订阅
- [ ] 非关键资源使用了异步/懒加载
