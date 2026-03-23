---
name: module-boundary
description: 模块入口出口规范，资源获取释放对称，统一index导出，外部不直接引用内部文件。新建模块时加载。
metadata:
  priority: L2
  category: principles
  depends: naming
---

# 单一入口，单一出口

## 规则

- **每个模块有一个清晰的入口**（构造函数/初始化方法）和**一个清晰的出口**（销毁方法/返回值）
- **资源获取和释放必须对称** — 获取了就必须释放，在对称位置（init↔destroy, subscribe↔unsubscribe, open↔close）
- **每个目录有一个 index 文件作为公共API出口** — 外部只能通过 index 导入
- **不允许直接导入目录内部文件** — 内部文件是实现细节，可以随时重构

## 示例

✅ 正确：
```typescript
// features/user/index.ts — 统一出口
export { UserProfile } from './components/UserProfile';
export { useUser } from './hooks/useUser';
export type { User, UserRole } from './types';

// 外部使用 — 只通过index导入
import { UserProfile, useUser } from '@/features/user';

// 资源对称
class WebSocketManager {
  connect() { this.ws = new WebSocket(url); }    // 获取
  disconnect() { this.ws?.close(); this.ws = null; }  // 释放（对称）
}
```

❌ 错误：
```typescript
// 直接引用内部文件 — 重构时会大面积破坏
import { UserProfile } from '@/features/user/components/UserProfile';
import { formatName } from '@/features/user/utils/format';

// 资源不对称 — 只有获取没有释放
class DataLoader {
  init() {
    this.interval = setInterval(this.poll, 5000);  // 获取了定时器
  }
  // 没有destroy/cleanup方法 → 内存泄漏
}
```

## 提交前检查清单

- [ ] 新建的目录有 index 文件作为公共API出口
- [ ] 外部引用使用目录路径（通过index），不直接引用内部文件
- [ ] 每个资源获取都有对应的释放代码
- [ ] 模块的初始化和清理逻辑在对称位置
