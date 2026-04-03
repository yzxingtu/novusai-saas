# Frontend Composable Unit Tests

## Purpose

为 frontend/apps/web-antd/src/composables/ 下缺少测试的关键 composables 编写单元测试。

## Target Composables (无测试)

优先级排序：

### P1 - AI 相关（核心功能）
1. `use-ai-page-policy.ts` → `__tests__/use-ai-page-policy.test.ts`
2. `use-ai-permission.ts` → `__tests__/use-ai-permission.test.ts`
3. `use-page-ai-operation-helpers.ts` → `__tests__/use-page-ai-operation-helpers.test.ts`
4. `use-page-ai-registration.ts` → `__tests__/use-page-ai-registration.test.ts`
5. `use-page-screenshot.ts` → `__tests__/use-page-screenshot.test.ts`
6. `use-page-session.ts` → `__tests__/use-page-session.test.ts`

### P2 - 通用功能
7. `use-crud-form.ts` → `__tests__/use-crud-form.test.ts`
8. `use-file-upload.ts` → `__tests__/use-file-upload.test.ts`
9. `use-notification-toast.ts` → `__tests__/use-notification-toast.test.ts`
10. `use-modal-detector.ts` → `__tests__/use-modal-detector.test.ts`
11. `use-form-state-tracker.ts` → `__tests__/use-form-state-tracker.test.ts`

### P3 - 插件/设置
12. `use-plugin-admin-refresh.ts` → `__tests__/use-plugin-admin-refresh.test.ts`
13. `use-preference-sync.ts` → `__tests__/use-preference-sync.test.ts`

## Testing Conventions

参考现有测试文件：
- `frontend/apps/web-antd/src/composables/__tests__/use-ai-operations.test.ts`
- `frontend/apps/web-antd/src/composables/__tests__/use-crud-list.test.ts`
- `frontend/apps/web-antd/src/composables/__tests__/use-page-operation-channel.test.ts`

测试框架: Vitest
- 使用 `describe` / `it` / `expect` 模式
- Mock Vue composables (ref, computed, watch 等)
- Mock API 调用
- Mock store (pinia)
- 测试响应式行为

## Implementation Plan

1. 阅读每个 composable 的源码
2. 理解其依赖（API、store、其他 composables）
3. 创建测试文件，按现有模式编写
4. 运行 `pnpm --filter web-antd test -- --run composables/__tests__/<test-file>` 验证
5. 最终运行全部 composable 测试确认无回归

## Acceptance Criteria

- [ ] 至少 10 个新测试文件
- [ ] 每个 composable 的核心功能被测试覆盖
- [ ] 所有测试通过
- [ ] 不依赖外部资源
