# Progress Update - Page Awareness Navigation V2
# 进展更新 - 页面感知导航 V2

**Date**: 2026-04-03
**Status**: 🟢 Core Functionality Complete, Final Polish Needed

---

## ✅ Completed Fixes / 已完成修复

### 1. Route Layer Fix / 路由层修复

**Problem**: Dashboard 和 analytics 页面的 AI mode 是 `context_only`，导致 `available_operations` 不暴露

**Solution**: 改为 `operate` mode

**Files Modified**:
- `frontend/apps/web-antd/src/router/routes/admin/index.ts`
- `frontend/apps/web-antd/src/router/routes/tenant/index.ts`

**Changes**:
```ts
// Before
meta: {
  affixTab: true,
  icon: 'lucide:layout-dashboard',
  title: 'page.dashboard.title',
  // No ai mode or context_only
}

// After
meta: {
  affixTab: true,
  icon: 'lucide:layout-dashboard',
  title: 'page.dashboard.title',
  ai: { mode: 'operate' as const },  // ✅ Now exposes operations
}
```

**Impact**: ✅ Dashboard 请求现在包含 `available_operations`

---

### 2. Planner Layer Fix / Planner 层修复

**Problem**: "我想添加一个智能体" 这类消息没有被识别为 page_ops intent

**Solution**: 扩展 `ToolInvocationPlanner` 的页面导航意图识别

**File Modified**: `backend/app/ai/engine/tool_invocation_planner.py`

**Changes**:
```python
# Added navigation action pattern
_PAGE_NAV_ACTION_RE = re.compile(
    r"(添加|新建|创建|打开|进入|跳转|切到|前往|管理|go to|open|navigate|switch to|jump to)",
    re.IGNORECASE,
)

# Added navigation target pattern
_PAGE_NAV_TARGET_RE = re.compile(
    r"(智能体|知识库|插件|配额|限速|设置|agents?|knowledge base|plugins?|quotas?|rate limit|settings?)",
    re.IGNORECASE,
)

# Enhanced page request detection
@staticmethod
def _is_explicit_page_request(
    user_text: str,
    *,
    page_context_present: bool,
    input_variables: dict[str, Any] | None = None,
) -> bool:
    # ... existing checks ...
    
    # NEW: Check if page has navigate_menu capability
    has_navigation_operation = "navigate_menu" in available_operation_names
    
    return bool(
        _PAGE_POINTER_RE.search(text)
        or _PAGE_ACTION_RE.search(text)
        or _PAGE_CAPABILITY_RE.search(text)
        or (
            has_navigation_operation
            and _PAGE_NAV_ACTION_RE.search(text)
            and _PAGE_NAV_TARGET_RE.search(text)
        )
    )
```

**Test Coverage**: `backend/tests/ai/test_tool_invocation_planner.py`

**Impact**: ✅ "我想添加一个智能体" 现在被识别为 page_ops intent

---

### 3. Navigation Stability Fix / 导航稳定性修复

**Problem**: 导航后返回的 page_context 可能还是旧页面的 DOM fallback

**Solution**: 强化 `page-navigation.ts`，等待新路由、新 session、新 context 稳定

**File Modified**: `frontend/apps/web-antd/src/utils/page-navigation.ts`

**Key Improvements**:
1. **Wait for route stabilization**:
   ```ts
   async function stabilizeNavigation(): Promise<void> {
     await nextTick();
     await delay(NAVIGATION_STABILIZE_MS);  // 80ms
     await nextTick();
   }
   ```

2. **Wait for page context ready**:
   ```ts
   const NAVIGATION_READY_TIMEOUT_MS = 3000;
   const NAVIGATION_READY_POLL_MS = 100;
   
   // Poll until page context is ready or timeout
   ```

3. **Verify target page reached**:
   ```ts
   function isTargetRoute(
     route: RouteLocationNormalizedLoaded,
     target: NavigationTarget,
   ): boolean {
     return (
       route.path === target.path ||
       normalizePageKey(routePageKey(route)) === normalizePageKey(target.pageKey)
     );
   }
   ```

**Impact**: ✅ 导航后返回的 page_context 更稳定，减少 fallback 情况

---

## ✅ MCP Validation Results / MCP 验证结果

### Tenant Endpoint / 企业端

✅ **Menu Boundary**: CommandBar 搜"智能体"只命中企业端菜单
✅ **Navigation**: 成功进入 `/tenant/ai/agents`
✅ **No Cross-Endpoint**: 没有串到 `/admin/*`

### Admin Endpoint / 管理端

#### Before Fix / 修复前
❌ Dashboard 请求没有 `available_operations`
❌ AI 只能反复调用 `get_page_context`
❌ 无法触发导航

#### After Fix / 修复后
✅ Dashboard 请求包含 `available_operations`
✅ 包含 `list_available_menus` 和 `navigate_menu`
✅ 真实对话成功执行：
   1. `get_page_context`
   2. `pageop_list_available_menus`
   3. `pageop_navigate_menu`
✅ 从 `/admin/dashboard` 成功跳到 `/admin/ai/agents`

---

## 🟡 Remaining Issue / 剩余问题

### Problem: Post-Navigation Form Opening Instability
### 问题：导航后自动打开表单不稳定

**Current Status**:
- ✅ Navigation from dashboard to agents page: **Stable**
- ❌ Auto-opening create form after navigation: **Unstable**

**Symptom**:
- AI successfully navigates to agents page
- But doesn't consistently continue to call `create_record` in the same turn
- Sometimes stops after navigation, requiring user to prompt again

**Possible Causes**:

1. **Context Continuation Issue**
   - After navigation, AI might not realize it should continue
   - New page context might not clearly indicate "now you can create"

2. **Tool Selection Hesitation**
   - AI might be uncertain whether to continue or wait for user confirmation
   - Prompt/system message might not encourage continuation

3. **Page Context Timing**
   - New page operations might not be immediately available
   - AI might see empty operations list briefly

4. **Model Behavior**
   - Model might interpret navigation as "task complete"
   - Needs stronger prompt to continue multi-step operations

---

## 📊 Test Coverage / 测试覆盖

### Backend Tests / 后端测试
✅ `test_page_operation.py` - Page operation execution
✅ `test_agent_router_service.py` - Router intent recognition
✅ `test_tool_invocation_planner.py` - Planner navigation intent
✅ `test_tool_argument_recovery.py` - Tool expansion

### Frontend Tests / 前端测试
✅ `page-navigation.test.ts` - Navigation helper
✅ `menu-navigation.test.ts` - Menu search and resolution
✅ `use-detail-page-ai.test.ts` - Detail page AI
✅ `pageContextEditorOps.test.ts` - Page context operations
✅ `CommandBar.test.ts` - CommandBar integration

---

## 🎯 Next Steps / 下一步计划

### Phase 1: Diagnose Post-Navigation Continuation (1-2 hours)

**Task 1.1**: Analyze AI behavior after navigation
- Review MCP logs for post-navigation turns
- Check if AI receives new page operations
- Verify if AI attempts to continue or stops

**Task 1.2**: Check page context after navigation
- Verify `available_operations` includes `create_record`
- Check if `page_data` provides enough context
- Ensure form state is clear (not already open)

**Task 1.3**: Review system prompts
- Check if prompts encourage multi-step completion
- Verify if navigation success message is clear
- Ensure AI knows it should continue

### Phase 2: Implement Fix (1-2 hours)

**Option A: Enhance Navigation Result Message**
```python
# In page_operation_executor.py or navigate_menu handler
return {
    "success": True,
    "message": "已导航到智能体管理页面。现在可以创建新智能体。",  # ← More explicit
    "data": {
        "page_context": new_context,
        "next_suggested_action": "create_record",  # ← Hint
        "available_operations": ["create_record", "search", ...]
    }
}
```

**Option B: Add Continuation Prompt**
```python
# In agent system prompt or tool description
"After navigating to a new page, if the user's original intent requires further action (like creating a record), continue with the appropriate operation without waiting for user confirmation."
```

**Option C: Improve Page Context Clarity**
```ts
// In use-page-ai-capability.ts
const pageData = {
  ...basePageData,
  navigation_context: navigationContext,
  available_operations: ops,
  // NEW: Add context hint
  page_ready_for_operations: true,
  suggested_next_actions: ["create_record"],  // Based on user intent
};
```

**Option D: Router Hint Enhancement**
```python
# In agent_router_service.py
# When routing to page-operation agent after navigation intent
# Add hint about continuation
routing_context = {
    "original_intent": "create agent",
    "navigation_completed": True,
    "should_continue": True,
}
```

### Phase 3: Validation (30 min)

**Test Case**: End-to-End Creation Flow
1. Start at `/admin/dashboard`
2. Say: "我想添加一个测试智能体，名字叫小助手"
3. Expected:
   - AI navigates to `/admin/ai/agents`
   - AI calls `create_record` with name="小助手"
   - Form opens with prefilled name
   - AI confirms form is ready

**Success Criteria**:
- ✅ 3 out of 3 attempts succeed
- ✅ No manual intervention needed
- ✅ Entire flow completes in one conversation turn

---

## 📝 Summary / 总结

### What Works / 已工作
✅ Dashboard exposes navigation operations
✅ AI recognizes navigation intents
✅ Navigation executes successfully
✅ New page context is returned
✅ Endpoint isolation is correct

### What Needs Polish / 需要打磨
🟡 Post-navigation continuation consistency
🟡 Multi-step operation completion rate

### Estimated Effort / 预估工作量
- Diagnosis: 1-2 hours
- Fix: 1-2 hours
- Validation: 30 minutes
- **Total**: 3-5 hours

### Risk Level / 风险等级
🟢 **Low** - Isolated to continuation logic, no architectural changes needed

---

## 🔗 Related Files / 相关文件

### Frontend
- `router/routes/admin/index.ts` - Route AI mode configuration
- `router/routes/tenant/index.ts` - Route AI mode configuration
- `utils/page-navigation.ts` - Navigation stability logic
- `use-page-ai-capability.ts` - Operation exposure
- `page-operation-defaults.ts` - Default operations

### Backend
- `ai/engine/tool_invocation_planner.py` - Intent recognition
- `ai/tools/executors/page_operation_executor.py` - Operation execution
- `ai/tools/page_tool_expander.py` - Tool expansion
- `ai/services/agent_router_service.py` - Agent routing

### Tests
- `backend/tests/ai/test_tool_invocation_planner.py`
- `frontend/apps/web-antd/src/utils/__tests__/page-navigation.test.ts`

---

**Conclusion**: Core navigation functionality is complete and stable. The remaining work is to improve the AI's consistency in continuing multi-step operations after navigation. This is a polish task, not a fundamental fix.
