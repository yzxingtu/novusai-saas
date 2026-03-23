# AI 页面操作可靠性修复 DoD 验收记录

> 对应整改方案：`@ai页面操作可靠性修复_c5e1391f.plan.md`
>
> 与富文本完整修复审计方案交叉引用：`@富文本完整修复审计方案_09c31c3d.plan.md`、`docs/acceptance/rich-text-dedicated-tools-dod.md`。parse error 熔断、content_format 契约等与富文本整改一致。
>
> 历史说明：文中提到的“企业端智能体测试抽屉”是当时存在的一套测试 UI。该抽屉后续已删除，相关 AI 对话反馈能力已并入统一聊天页/统一页面操作链路；本文件保留的是当时验收事实，而非当前活跃组件清单。

## 验收标准（DoD）完成情况

| 标准 | 状态 | 说明 |
|------|------|------|
| replace_content 空输入保护 | ✅ | `useEditorPageOps.ts` 校验 content，空或仅标签时返回 success=false + error_type |
| replace_content 危险操作确认 | ✅ | `replace_content` 使用 i18n 确认文案（replaceContentConfirm） |
| 工具子状态细分 | ✅ | `ChatMessageItem` 区分 waiting_confirm / executing，按 error_type 展示不同错误提示 |
| 确认卡片 60s 倒计时 | ✅ | `ai-panel.ts` 增加 startedAt，AIChatSlidePanel 显示倒计时 |
| 执行中过程提示（8s+） | ✅ | `ChatMessageItem` 执行超 8s 显示「仍在执行，可继续等待」 |
| error_type 前后端打通 | ✅ | ToolResult/SSE 含 error_type，前端按类型映射 i18n 提示 |
| 历史测试抽屉 tool_start | ✅ | 当时支持 tool_start → running，tool_call → success/error；现能力已并入统一聊天页 |
| 后端 error_type 测试 | ✅ | test_page_operation 断言 invalid_input、session_not_found |

## 整改实施明细

### 阶段 A：防止误清空正文（已在前期完成）

- [x] `useEditorPageOps.ts`：replace_content 空输入校验，返回 invalid_input_empty_content
- [x] `use-page-operation-channel.ts`：replace_content 使用 replaceContentConfirm 确认
- [x] i18n：replaceContentEmptyError、invalidInputEmptyContent、replaceContentConfirm

### 阶段 B：细粒度状态与反馈

- [x] `ai-panel.ts`：PendingPageOp 增加 startedAt
- [x] `AIChatSlidePanel.vue`：确认卡片显示 60s 倒计时（confirmCountdown）
- [x] `ChatMessageItem.vue`：waiting_confirm（待确认）与 executing（执行中）区分
- [x] `ChatMessageItem.vue`：执行超 8s 显示 toolStillRunningHint
- [x] `types.ts`：ToolCallEvent 增加 errorType、startedAt
- [x] `use-ai-chat.ts`：tool_start 写入 startedAt，tool_call 透传 error_type
- [x] i18n：toolWaitingConfirm、toolExecuting、toolStillRunningHint、confirmCountdown
- [x] i18n：pageOpUserCancelledHint、pageOpNotRegisteredHint、pageOpInvalidInputHint、pageOpSessionNotFoundHint、pageOpExecFailedHint

### 阶段 C：后端 error_type 打通

- [x] `ToolResult`：增加 error_type 字段
- [x] `page_operation_executor.py`：缺参 → invalid_input，无 session → session_not_found，失败时透传前端 error_type
- [x] `tool_processor.build_tool_call_event`：失败时附带 error_type 到 SSE

### 阶段 D：历史测试抽屉对齐（该组件现已删除）

- [x] 历史测试抽屉：当时已处理 `tool_start`，工具列表展示 `running -> success/error`

### 阶段 E：测试与验收

- [x] `test_page_operation.py`：test_no_page_session_id、test_missing_page_key、test_missing_operation_name 断言 error_type
- [x] 前端单测：`replaceContentValidator.test.ts`（7 用例，空输入/仅标签拒绝、合法内容通过）、`getPageOpErrorHintKey.test.ts`（10 用例，各 error_type 映射）
- [x] **组件渲染层测试（二期审计补齐）**：
  - `ChatMessageItem.test.ts`（6 用例，组件挂载）：invoke_page_operation + pending → toolWaitingConfirm；普通/非 page-op 运行态 → toolExecuting；超 8s → toolStillRunningHint；error_type=pending_confirmation → pageOpPendingConfirmationHint；未知 error_type → pageOpExecFailedHint
  - `AIChatSlidePanel.test.ts`（2 用例，组件挂载）：pending op 时渲染 confirmCountdown；时间推进后倒计时递减且 ≥0
  - `countdown-display.test.ts`（3 用例，纯逻辑）：60s 初值、倒计时递减且 ≥0、confirmCountdown i18n
- [x] 本 DoD 文档

### 二期整改（页面操作反馈审计整改二期）

- [x] error_type 补全 pending_confirmation → pageOpPendingConfirmationHint
- [x] useEditorPageOps 全部用户可见文案改为 i18n（common.editorOp.*）
- [x] 提取 replaceContentValidator、pageOpErrorHints 可测试模块

## 手工验收场景

| 场景 | 预期 |
|------|------|
| 正常 replace_content 成功 | 全文正确替换 |
| 空 content 调用 | 被拒绝，原文不变，错误提示「内容为空或无效」 |
| 用户不确认到超时 | 确认卡片显示倒计时，超时后显示「建议刷新页面后重试」 |
| 用户取消操作 | 显示「你已取消本次操作」 |
| 编辑页刷新/断线 | 显示「请回到编辑页后重试」 |
| 历史测试抽屉工具执行 | 先显示「执行中」，完成后显示成功/失败；现由统一聊天页承接 |

## 测试执行

```bash
# 后端
cd backend && python -m pytest tests/services/test_page_operation.py -v

# 前端（本整改相关，含组件渲染层）
cd frontend && pnpm exec vitest run apps/web-antd/src/components/business/ai-chat-panel/__tests__ apps/web-antd/src/components/business/ai-slide-panel/__tests__ apps/web-antd/src/components/business/rich-text-editor/__tests__

# 前端全量门禁（pnpm run test:unit）
cd frontend && pnpm run test:unit
```

**门禁说明**：`test:unit` 全量执行 `vitest run --dom`，覆盖本整改相关测试。本整改范围内共 5 个文件、28 用例（ChatMessageItem、getPageOpErrorHintKey、AIChatSlidePanel、countdown-display、replaceContentValidator）。全量通过即门禁绿灯。

## 修改文件清单

- `backend/app/ai/tools/types.py`：ToolResult.error_type
- `backend/app/ai/tools/executors/page_operation_executor.py`：error_type 传递
- `backend/app/ai/engine/tool_processor.py`：SSE event.error_type
- `backend/tests/services/test_page_operation.py`：error_type 断言
- `frontend/.../ai-chat-panel/types.ts`：ToolCallEvent.errorType、startedAt
- `frontend/.../ai-chat-panel/use-ai-chat.ts`：tool_start startedAt、tool_call error_type
- `frontend/.../ai-chat-panel/ChatMessageItem.vue`：子状态、提示映射、8s 提示
- `frontend/.../ai-slide-panel/AIChatSlidePanel.vue`：60s 倒计时
- `frontend/.../store/shared/ai-panel.ts`：PendingPageOp.startedAt
- 历史企业端智能体测试抽屉：已删除；当时用于验证 `tool_start` 处理
- i18n：zh-CN/en-US common.json、shared/pageOperation.json
- （二期）`replaceContentValidator.ts`、`pageOpErrorHints.ts`：可测模块
- （二期）`__tests__/replaceContentValidator.test.ts`、`__tests__/getPageOpErrorHintKey.test.ts`
