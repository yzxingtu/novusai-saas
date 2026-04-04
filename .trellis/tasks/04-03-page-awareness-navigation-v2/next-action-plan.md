# Next Action Plan - Page Awareness Navigation V2
# 下一步行动计划 - 页面感知导航 V2

**Created**: 2026-04-03
**Status**: Ready to Execute
**Estimated Time**: 1-2 hours

---

## Quick Summary / 快速总结

**Problem**: Dashboard 等简单页面的 `available_operations` 在 AI 请求中为空
**Root Cause**: 需要验证操作暴露逻辑是否正确工作
**Solution**: 诊断 → 修复 → 验证

---

## Phase 1: Diagnostic (30 min) / 诊断阶段

### Step 1.1: Add Debug Logging

**File**: `frontend/apps/web-antd/src/components/business/ai-slide-panel/use-page-ai-capability.ts`

**Location**: In `buildEnrichedPageAIState` function, around line 180

**Add**:
```ts
// Debug: Check operation exposure
if (SHOW_PAGE_AI_DIAGNOSTICS) {
  console.log('[PageAI Debug] buildEnrichedPageAIState', {
    pageKey: ctx.page_key,
    normalizedPageMode: options.normalizedPageMode.value,
    canExposeOps: canExposePageOperations(options.normalizedPageMode.value),
    opsCount: ops.length,
    opsNames: ops.map(op => op.name),
    willIncludeInPayload: canExposePageOperations(options.normalizedPageMode.value) && ops.length > 0,
  });
}
```

**Purpose**: Verify if operations are being filtered out

### Step 1.2: Check Request Payload

**File**: Find where chat requests are sent (likely `AIChatSlidePanel.vue` or similar)

**Search for**: `page_context` in request payload construction

**Verify**:
- Is `currentPageContext.value` being used?
- Does it include `page_data.available_operations`?

**Command**:
```bash
# Find where chat requests are sent
rg "page_context.*page_data" frontend/apps/web-antd/src --type vue --type ts
```

### Step 1.3: Test and Observe

**Action**:
1. Open browser DevTools console
2. Navigate to `http://localhost:5666/admin/dashboard`
3. Open AI Panel
4. Check console for debug logs
5. Send a message
6. Check Network tab for request payload

**Expected Output**:
```json
{
  "page_context": {
    "page_key": "admin.dashboard",
    "page_data": {
      "navigation_context": { ... },
      "available_operations": [  // ← Should NOT be empty
        { "name": "list_available_menus", ... },
        { "name": "navigate_menu", ... },
        ...
      ]
    }
  }
}
```

---

## Phase 2: Fix (30-60 min) / 修复阶段

### Scenario A: Operations are filtered by policy

**If**: Debug shows `canExposeOps: false`

**Fix**: Check `pageAIPolicy` computation

**File**: Find where `pageAIPolicy` is computed (likely in AI Panel component)

**Verify**:
- Is `mode` set to `'disabled'`?
- Are `disabledCapabilities` blocking operations?

**Solution**: Ensure dashboard has correct AI mode

### Scenario B: Operations not included in request

**If**: Debug shows operations exist but not in request payload

**Fix**: Update request payload construction

**File**: Where chat request is built

**Ensure**:
```ts
const payload = {
  message: userMessage,
  page_context: currentPageContext.value,  // ← Must include available_operations
  // ...
};
```

### Scenario C: Timing issue

**If**: Operations are empty when request is sent but populated later

**Fix**: Wait for operations to be ready

**Solution**:
```ts
// Before sending request
await nextTick();  // Ensure computed values are updated
```

### Scenario D: Dashboard needs explicit registration

**If**: All else fails, explicitly register operations

**File**: `frontend/apps/web-antd/src/views/admin/dashboard/index.vue`

**Add**:
```ts
import { usePageAIOperations } from '#/composables/use-page-ai-registration';
import { getDefaultPageOperations } from '#/components/business/ai-slide-panel/page-operation-defaults';

// After existing usePageAIContext call
usePageAIOperations({
  operations: getDefaultPageOperations('admin.dashboard'),
});
```

---

## Phase 3: Validation (30 min) / 验证阶段

### Test Case 1: Dashboard Navigation

**Steps**:
1. Navigate to `http://localhost:5666/admin/dashboard`
2. Open AI Panel (Ctrl+K or click icon)
3. Say: "我想添加一个智能体"

**Expected**:
- AI calls `navigate_menu` with target="智能体"
- Page navigates to `/admin/ai/agents`
- AI continues with "现在我在智能体管理页面，可以帮你创建"

**Actual** (before fix):
- AI says "当前页面不支持创建智能体操作"

### Test Case 2: Other Simple Pages

**Test on**:
- `/admin/settings`
- `/admin/system/logs`
- Any page that only uses `usePageAIContext`

**Verify**: All expose navigation operations

### Test Case 3: Regression

**Test on**:
- `/admin/ai/agents` (useCrudList)
- `/tenant/ai/agents` (tenant endpoint)
- `/admin/ai/agents/:id` (detail page)

**Verify**: Existing functionality still works

---

## Rollback Plan / 回滚计划

If fix causes issues:

1. **Revert changes**:
   ```bash
   git checkout -- <modified-files>
   ```

2. **Alternative approach**: Explicitly register on each page
   - Lower risk but more work
   - Add `usePageAIOperations` to each simple page

---

## Success Metrics / 成功指标

✅ Dashboard request includes `available_operations` with 5+ operations
✅ AI successfully navigates from dashboard to agents page
✅ After navigation, AI can call page operations on new page
✅ No regression in tenant endpoint
✅ No regression in CRUD pages

---

## Prompt for Next AI / 给下一个 AI 的提示词

```
我需要修复页面感知导航功能的运行时集成问题。

## 背景
- 代码已全部实现，测试通过
- 企业端工作正常
- 管理端 dashboard 页面的 available_operations 在 AI 请求中为空

## 任务
1. 按照 .trellis/tasks/04-03-page-awareness-navigation-v2/next-action-plan.md 执行诊断
2. 找到 available_operations 为空的根本原因
3. 实施最小化修复
4. 运行验证测试

## 关键文件
- use-page-ai-capability.ts (操作暴露逻辑)
- dashboard/index.vue (dashboard 页面)
- AIChatSlidePanel.vue (请求构建)

## 验证方式
在 /admin/dashboard 页面说"我想添加一个智能体"，AI 应该能够：
1. 识别需要导航
2. 调用 navigate_menu
3. 跳转到智能体管理页
4. 继续执行创建操作

请开始诊断并修复。
```

---

## Notes / 备注

- 优先使用 Scenario A/B/C 的修复方案
- Scenario D (显式注册) 是最后的备选方案
- 修复后记得移除 debug logging
- 更新 mcp-validation 文档记录修复结果
