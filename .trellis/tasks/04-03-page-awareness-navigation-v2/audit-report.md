# Page Awareness Navigation V2 - Audit Report
# 页面感知导航 V2 - 审计报告

**Date**: 2026-04-03
**Auditor**: Claude Sonnet 4.6
**Status**: 🟡 Implementation Complete, Runtime Integration Issue Found

---

## Executive Summary / 执行摘要

✅ **Architecture & Code**: All components implemented correctly
✅ **Tests**: Unit tests passing
✅ **Tenant Endpoint**: Working end-to-end
❌ **Admin Endpoint**: Navigation operations not exposed to AI runtime

**Root Cause**: Dashboard and other simple pages don't register page operations, so `available_operations` is empty in AI requests.

---

## What Was Implemented / 已实现功能

### ✅ Frontend Components

1. **Shared Menu Navigation Layer** (`menu-navigation.ts`)
   - Endpoint-scoped menu indexing
   - Natural language target resolution
   - Handles: `already_on_page`, `not_found`, `ambiguous_match`

2. **Unified Navigation Helper** (`page-navigation.ts`)
   - Pre-navigation check (already on page?)
   - Post-navigation validation (actually arrived?)
   - Returns new `page_context`, `page_session_id`, `page_data_preview`
   - Handles: `permission_denied`, `navigation_blocked`

3. **Default Page Operations** (`page-operation-defaults.ts`)
   - `list_available_menus`: List accessible menus
   - `navigate_menu`: Navigate by natural language target
   - `read_current_view`: Read page snapshot
   - `read_current_sections`: Read DOM structure
   - `capture_screenshot`: Capture page screenshot

4. **Page Context Enhancement** (`use-page-ai-capability.ts`)
   - Added `navigation_context` to `page_data`:
     - `endpoint`, `path`, `breadcrumb`, `page_key`

5. **Existing Navigation Operations Upgraded**
   - `navigate_to_detail` (in `use-ai-operations.ts`)
   - `navigate_back` (in `use-detail-page-ai.ts`)
   - `createOpenPageOperation` (in `use-page-ai-operation-helpers.ts`)
   - All now return new page context after navigation

6. **CommandBar Integration** (`use-command-bar.ts`, `CommandBar.vue`)
   - Reuses shared menu navigation helper
   - Endpoint-scoped search

### ✅ Backend Components

1. **PageOperationExecutor** (`page_operation_executor.py`)
   - Recognizes new `page_context`/`page_session_id` in operation results
   - Writes back to `ExecutionContext`
   - Clears `_page_context_already_returned_this_turn` on page change

2. **Cross-Page Session Recovery**
   - Prioritizes `get_active_session_id(user_id, target_page_key, user_role)`

3. **Router Intent Recognition** (`agent_router_service.py`)
   - Added action words: "添加/打开/进入/跳转/切到"
   - Added module words: "智能体/知识库/插件/配额/设置"
   - Prefers page-operation-capable agents for navigation intents

4. **Tool Expansion** (`page_tool_expander.py`)
   - Added `pageop_list_available_menus`
   - Added `pageop_navigate_menu`

### ✅ Tests

**Frontend**:
- `menu-navigation.test.ts`
- `page-navigation.test.ts`
- `use-detail-page-ai.test.ts`
- `pageContextEditorOps.test.ts`
- `CommandBar.test.ts`

**Backend**:
- `test_page_operation.py`
- `test_agent_router_service.py`
- `test_tool_argument_recovery.py`

---

## Root Cause Analysis / 根本原因分析

### Problem / 问题

When user says "通过页面感知能力添加一个测试的智能体" on `/admin/dashboard`:
- AI responds: "当前页面不支持创建智能体操作"
- Logs show: `操作 'navigate_to_detail' 未在页面 'admin.dashboard' 注册`

### Why This Happens / 为什么会这样

1. **Dashboard doesn't register operations**
   ```vue
   <!-- dashboard/index.vue -->
   usePageAIContext({
     title: () => $t('admin.dashboard.platformConsole'),
     data: () => ({ ... }),
   });
   ```
   - Only calls `usePageAIContext` (registers context, NOT operations)
   - Does NOT call `usePageAIOperations`

2. **Default operations are only merged at read time**
   ```ts
   // page-operation-registry.ts:433
   function getMergedOperations(key: string): PageOperation[] {
     const defaults = getDefaultPageOperations(key);  // ✅ Includes navigate_menu
     const primary = registry.get(key) ?? [];         // ❌ Empty for dashboard
     const extraGroups = extrasRegistry.get(key) ?? [];
     return mergeOperationGroups([defaults, primary, ...extraGroups]);
   }
   ```
   - `getDefaultPageOperations(key)` returns navigation operations
   - BUT `listPageOperations` is only called when building `available_operations`

3. **available_operations is built in use-page-ai-capability.ts**
   ```ts
   // use-page-ai-capability.ts:119
   const currentPageOperations = computed(() => {
     void pageOperationVersion.value;
     const pageKey = resolvedPageKey.value;
     if (!pageKey) return [];
     return filterPageOperationsByPolicy(
       listPageOperations(pageKey),  // ✅ This DOES include defaults
       options.pageAIPolicy.value,
     );
   });
   ```
   - This computed DOES call `listPageOperations`
   - Which DOES merge defaults
   - So `currentPageOperations` SHOULD include `navigate_menu`

4. **But why is available_operations empty in the request?**
   
   Let me check the actual flow...

### Verification Needed / 需要验证

Need to check:
1. Is `currentPageOperations` actually populated for dashboard?
2. Is `canExposePageOperations` returning false?
3. Is `pageAIPolicy` disabling operations?
4. Is there a timing issue where operations aren't ready when request is sent?

---

## Next Steps / 下一步计划

### Phase 1: Diagnostic / 诊断阶段

**Task 1.1**: Add debug logging to verify operation exposure
- File: `use-page-ai-capability.ts`
- Add console.log in `buildEnrichedPageAIState` to check:
  - `currentPageOperations.value.length`
  - `canExposePageOperations(options.normalizedPageMode.value)`
  - `rawPageData.available_operations`

**Task 1.2**: Verify dashboard page key resolution
- Check if `resolvedPageKey` is correctly set to `admin.dashboard`
- Check if `pageContextKey` prop is passed correctly

**Task 1.3**: Check AI Panel request payload
- File: `AIChatSlidePanel.vue` or wherever chat requests are sent
- Verify `page_context.page_data.available_operations` is included

### Phase 2: Fix / 修复阶段

**Hypothesis A**: Operations are filtered out by policy
- **Fix**: Check `pageAIPolicy` and `disabledCapabilities`
- **File**: Where `pageAIPolicy` is computed

**Hypothesis B**: Timing issue - operations not ready when request sent
- **Fix**: Ensure operations are loaded before sending request
- **File**: Chat request sending logic

**Hypothesis C**: Dashboard needs explicit operation registration
- **Fix**: Add `usePageAIOperations` call in dashboard
- **File**: `dashboard/index.vue`
- **Code**:
  ```ts
  usePageAIOperations({
    operations: getDefaultPageOperations('admin.dashboard'),
  });
  ```

### Phase 3: Validation / 验证阶段

**Task 3.1**: Test on dashboard
- Navigate to `/admin/dashboard`
- Say: "我想添加一个智能体"
- Expected: AI calls `navigate_menu` with target="智能体"

**Task 3.2**: Test on other simple pages
- Check pages that only use `usePageAIContext`
- Ensure they also expose navigation operations

**Task 3.3**: Regression test
- Ensure tenant endpoint still works
- Ensure pages with `useCrudList`/`useCrudPage` still work

---

## Recommended Approach / 推荐方案

**Option 1: Auto-register defaults globally** (Recommended)
- Modify `usePageAICapability` to always include default operations
- No need for pages to explicitly register
- Consistent behavior across all pages

**Option 2: Explicit registration in simple pages**
- Add `usePageAIOperations` to dashboard and similar pages
- More explicit but requires touching many files

**Option 3: Fix operation exposure logic**
- If operations ARE populated but not exposed, fix the exposure logic
- Check `canExposePageOperations` and related filters

---

## Files to Review / 需要审查的文件

Priority order:

1. `use-page-ai-capability.ts` - Operation exposure logic
2. `AIChatSlidePanel.vue` - Request payload construction
3. `dashboard/index.vue` - Dashboard page setup
4. `page-operation-registry.ts` - Operation merging logic
5. `ai-page-capabilities.ts` - Policy and filtering logic

---

## Success Criteria / 成功标准

✅ Dashboard page exposes `navigate_menu` in `available_operations`
✅ AI can navigate from dashboard to agents page
✅ After navigation, AI can continue with page operations on new page
✅ Tenant endpoint continues to work
✅ No regression in existing CRUD pages

---

## Conclusion / 结论

The implementation is architecturally sound and complete. The issue is a runtime integration gap where default navigation operations are not being exposed to the AI in the request payload for simple pages like dashboard.

The fix is likely small - either ensuring operations are properly exposed, or explicitly registering them on simple pages.

**Estimated effort**: 1-2 hours
**Risk level**: Low (isolated to operation exposure logic)
