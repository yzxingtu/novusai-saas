# Action Plan: Post-Navigation Continuation Fix
# 行动计划：导航后续接修复

**Created**: 2026-04-03
**Target**: Fix AI continuation after successful navigation
**Estimated Time**: 3-5 hours

---

## Problem Statement / 问题陈述

**Current Behavior**:
- User: "我想添加一个测试智能体"
- AI: Navigates from dashboard to agents page ✅
- AI: Stops and waits for next instruction ❌

**Expected Behavior**:
- User: "我想添加一个测试智能体"
- AI: Navigates from dashboard to agents page ✅
- AI: Continues to call `create_record` ✅
- AI: Opens form and confirms ready ✅

---

## Root Cause Hypotheses / 根本原因假设

### Hypothesis 1: Unclear Navigation Result Message
**Theory**: AI doesn't realize it should continue after navigation

**Evidence Needed**:
- Check navigation result message content
- Review if message suggests continuation

**Test**:
```python
# Check current message
result = await navigate_menu(target="智能体")
print(result["message"])
# Expected: "已导航到智能体管理页面"
# Problem: Doesn't hint at continuation
```

### Hypothesis 2: Missing Context Hint
**Theory**: New page context doesn't indicate "ready for operations"

**Evidence Needed**:
- Check `page_data` after navigation
- Verify if operations are clearly available

**Test**:
```ts
// After navigation
console.log(pageContext.page_data.available_operations);
// Should include: create_record, search, etc.
```

### Hypothesis 3: Model Prompt Insufficient
**Theory**: System prompt doesn't encourage multi-step completion

**Evidence Needed**:
- Review agent system prompt
- Check if continuation is mentioned

**Test**:
- Read agent prompt template
- Look for multi-step guidance

### Hypothesis 4: Router Context Loss
**Theory**: After navigation, router doesn't preserve original intent

**Evidence Needed**:
- Check if original user intent is passed through
- Verify if router knows this is a continuation

**Test**:
```python
# In agent_router_service.py
# Check if routing context includes original intent
```

---

## Diagnostic Steps / 诊断步骤

### Step 1: Capture MCP Logs (15 min)

**Action**:
1. Start fresh MCP session
2. Navigate to `/admin/dashboard`
3. Say: "我想添加一个测试智能体，名字叫小助手"
4. Capture full conversation log

**What to Look For**:
- Navigation result message
- Page context after navigation
- Available operations list
- AI's next action (or lack thereof)
- Any error messages

**Save to**: `.trellis/tasks/04-03-page-awareness-navigation-v2/mcp-continuation-debug.log`

### Step 2: Analyze Navigation Result (15 min)

**File**: `backend/app/ai/tools/executors/page_operation_executor.py`

**Check**:
```python
# Find navigate_menu result construction
# Look for message content
# Verify data payload includes:
# - page_context
# - available_operations
# - any continuation hints
```

**Questions**:
- Is the message clear about what's possible now?
- Does the data include operation list?
- Is there any hint about continuation?

### Step 3: Review Agent Prompt (15 min)

**File**: Find agent system prompt (likely in `backend/app/ai/prompts/` or similar)

**Check**:
- Does prompt mention multi-step operations?
- Does it encourage continuation after navigation?
- Does it explain when to stop vs continue?

**Look for**:
```
"When navigating to a new page, if the user's original intent requires further action..."
```

### Step 4: Check Page Context After Navigation (15 min)

**File**: `frontend/apps/web-antd/src/utils/page-navigation.ts`

**Verify**:
```ts
// In buildNavigationResultPayload
// Check what's included in the result
{
  navigation_target: { ... },
  page_context: { ... },
  page_data_preview: { ... },
  page_session_id: "...",
  // Missing: continuation hint?
}
```

---

## Fix Implementation / 修复实施

### Fix 1: Enhance Navigation Result Message (Priority: High)

**File**: `backend/app/ai/tools/executors/page_operation_executor.py`

**Location**: In `navigate_menu` result construction

**Change**:
```python
# Before
return {
    "success": True,
    "message": f"已导航到{target_page_title}",
    "data": {
        "page_context": new_context,
        "page_session_id": new_session_id,
    }
}

# After
return {
    "success": True,
    "message": f"已导航到{target_page_title}。页面已就绪，可以继续执行操作。",  # ← More explicit
    "data": {
        "page_context": new_context,
        "page_session_id": new_session_id,
        "available_operations": list(new_context.get("page_data", {}).get("available_operations", [])),  # ← Explicit list
        "page_ready": True,  # ← Clear signal
    }
}
```

**Rationale**: Make it crystal clear that AI can continue

### Fix 2: Add Continuation Hint to Page Context (Priority: Medium)

**File**: `frontend/apps/web-antd/src/utils/page-navigation.ts`

**Location**: In `buildNavigationResultPayload`

**Change**:
```ts
return {
  navigation_target: { ... },
  page_context: pageContext,
  page_data_preview: buildPageDataPreview(pageContext.page_data),
  page_session_id: pageSessionIdOverride ?? (getActivePageSessionId() || null),
  route_path: currentRoute.path,
  // NEW: Add continuation hint
  navigation_completed: true,
  page_ready_for_operations: true,
};
```

**Rationale**: Provide explicit signal that page is ready

### Fix 3: Enhance Agent System Prompt (Priority: High)

**File**: Find agent system prompt file

**Add Section**:
```markdown
## Multi-Step Operations

When a user's request requires multiple steps (e.g., "添加一个智能体"):

1. If you need to navigate to a different page first, use `navigate_menu`
2. After successful navigation, **immediately continue** with the next operation
3. Do NOT wait for user confirmation unless explicitly asked
4. Use the `available_operations` in the new page context to complete the task

Example:
- User: "我想添加一个测试智能体"
- Step 1: Navigate to agents page (if not already there)
- Step 2: Call `create_record` to open the form
- Step 3: Fill the form with provided details
- Step 4: Confirm form is ready for user review

**Important**: Complete the entire flow in one turn unless you encounter an error or need user input.
```

**Rationale**: Explicitly instruct AI to continue

### Fix 4: Add Router Context Preservation (Priority: Low)

**File**: `backend/app/ai/services/agent_router_service.py`

**Enhancement**: Preserve original intent through navigation

**Change**:
```python
# When routing after navigation intent detected
routing_metadata = {
    "original_user_intent": user_message,
    "navigation_required": True,
    "expected_continuation": True,
    "target_operation": "create_record",  # Inferred from intent
}

# Pass this metadata to the agent
```

**Rationale**: Help agent remember original intent

---

## Implementation Priority / 实施优先级

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Fix 1: Enhance navigation result message
2. ✅ Fix 3: Enhance agent system prompt

**Rationale**: These are high-impact, low-risk changes

### Phase 2: Context Enhancement (1 hour)
3. ✅ Fix 2: Add continuation hint to page context

**Rationale**: Provides clearer signal to AI

### Phase 3: Advanced (Optional, 1-2 hours)
4. ⚪ Fix 4: Router context preservation

**Rationale**: Only if Phase 1 & 2 don't solve the problem

---

## Validation Plan / 验证计划

### Test Case 1: Basic Creation Flow

**Setup**: Start at `/admin/dashboard`

**Input**: "我想添加一个测试智能体"

**Expected Steps**:
1. AI calls `get_page_context` (dashboard)
2. AI calls `pageop_navigate_menu` with target="智能体"
3. Navigation succeeds, returns new page context
4. AI calls `pageop_create_record` (without user prompt)
5. Form opens
6. AI confirms: "已打开新建智能体表单，请提供详细信息"

**Success Criteria**: Steps 1-6 complete in one turn

### Test Case 2: Creation with Details

**Setup**: Start at `/admin/dashboard`

**Input**: "我想添加一个测试智能体，名字叫小助手，类型是通用对话"

**Expected Steps**:
1. AI navigates to agents page
2. AI calls `create_record` with name="小助手"
3. Form opens with prefilled name
4. AI confirms form is ready and asks for remaining fields

**Success Criteria**: Form opens with correct prefill

### Test Case 3: Already on Target Page

**Setup**: Start at `/admin/ai/agents`

**Input**: "我想添加一个测试智能体"

**Expected Steps**:
1. AI calls `get_page_context` (agents page)
2. AI recognizes already on target page
3. AI directly calls `create_record`
4. Form opens

**Success Criteria**: No unnecessary navigation

### Test Case 4: Cross-Endpoint Boundary

**Setup**: Start at `/admin/dashboard`

**Input**: "我想添加一个企业端智能体"

**Expected**:
- AI explains cannot navigate to tenant endpoint from admin
- Suggests switching to tenant interface

**Success Criteria**: Proper boundary enforcement

---

## Rollback Plan / 回滚计划

If fixes cause issues:

1. **Revert prompt changes**:
   ```bash
   git checkout -- <agent-prompt-file>
   ```

2. **Revert code changes**:
   ```bash
   git checkout -- backend/app/ai/tools/executors/page_operation_executor.py
   git checkout -- frontend/apps/web-antd/src/utils/page-navigation.ts
   ```

3. **Alternative approach**: Add explicit continuation tool
   - Create `continue_with_operation` tool
   - AI calls this after navigation to signal continuation

---

## Success Metrics / 成功指标

### Quantitative / 定量指标
- ✅ 90%+ success rate on Test Case 1 (3/3 attempts)
- ✅ 90%+ success rate on Test Case 2 (3/3 attempts)
- ✅ 100% success rate on Test Case 3 (3/3 attempts)
- ✅ 100% success rate on Test Case 4 (3/3 attempts)

### Qualitative / 定性指标
- ✅ No manual intervention needed
- ✅ Natural conversation flow
- ✅ Clear AI feedback at each step
- ✅ No confusion or hesitation

---

## Documentation Updates / 文档更新

After successful fix:

1. Update `mcp-validation-20260403.md` with new test results
2. Update `progress-update-20260403.md` with completion status
3. Create `completion-report.md` summarizing entire feature
4. Update PRD with "Completed" status

---

## Next AI Prompt / 给下一个 AI 的提示词

```
我需要修复页面感知导航后的自动续接问题。

## 背景
- 导航功能已完成并验证通过
- AI 能成功从 dashboard 导航到 agents 页面
- 但导航后不会自动继续调用 create_record

## 任务
按照 .trellis/tasks/04-03-page-awareness-navigation-v2/post-navigation-continuation-plan.md 执行：

1. Phase 1 诊断：
   - 运行 MCP 测试并捕获日志
   - 分析导航结果消息
   - 检查 agent 系统 prompt

2. Phase 1 修复（优先）：
   - 增强导航结果消息的明确性
   - 更新 agent 系统 prompt 鼓励续接

3. 验证：
   - 运行 4 个测试用例
   - 确保 90%+ 成功率

## 关键文件
- page_operation_executor.py (导航结果消息)
- agent system prompt (续接指导)
- page-navigation.ts (上下文提示)

## 验证方式
在 /admin/dashboard 说"我想添加一个测试智能体"，AI 应该：
1. 导航到 agents 页面
2. 自动调用 create_record
3. 打开表单
4. 确认就绪

全程无需用户额外提示。

请开始诊断和修复。
```

---

**Estimated Total Time**: 3-5 hours
**Risk Level**: 🟢 Low
**Impact**: 🟢 High (completes the feature)
