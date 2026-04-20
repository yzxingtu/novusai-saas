# Codex Page Workflow State Owner Closeout

## Goal

把页面操作主线真正收口为状态机 owner。目标不是再补页面规则，而是让
`discover -> navigate/open -> read -> write -> submit -> verify`
成为 routing、recovery、completion、stop-loss 共用的 canonical contract。

## Current Gap

当前已经有了 page workflow metadata、state machine 基础、stage-aware recovery
和 completion contracts，但仍有剩余差距：

1. page-progress partial / stop-loss 还没有完全变成第一等事实；
2. recovery 与 finalization 仍可能退回文本式收尾；
3. 某些边界上仍可能残留 prompt-hint 或 legacy session fallback 思维。

## Write Scope

- `backend/app/ai/engine/page_workflow_state_machine.py`
- `backend/app/ai/engine/tool_router.py`
- `backend/app/ai/engine/prepare_execution_tool_helpers.py`
- `backend/app/ai/engine/page_flow_recovery_helpers.py`
- `backend/app/ai/engine/recovery_status_update.py`
- `backend/app/ai/engine/tool_policy_intent_helpers.py`
- `backend/app/ai/engine/turn_executor_completion.py`
- 对应 page intent / page recovery / orchestration tests

## Requirements

1. canonical workflow metadata 必须同时驱动 routing、recovery、completion、
   contract-breach、partial-exit 与 stop-loss。
2. `page_navigation`、`page_row_detail`、`page_form_write`、
   `page_editor_write`、`page_search` 等核心 page intents 都必须明确落在
   discover/open/read/write/submit/verify 阶段上。
3. consent gate 必须继续是一等 pause，不得被 budget exit、retry exhaustion、
   generic failure、或文本式“已处理”收尾吞掉。
4. live 路径里不得复活 `page_key -> session_id` 主身份链、prompt-hint-led
   recovery、或 text-only completion shortcut。
5. page-progress 证据需要进入 diagnostics / turn flow，便于后续 runtime-core
   收口时只做投影，不再二次猜页面状态。

## Acceptance

1. 页面导航、打开详情、编辑表单、提交表单、校验结果这几类核心场景都通过同一套
   workflow metadata 判断下一步，而不是各自维护例外逻辑。
2. page turn 在“动作已执行但验证未完成”的情况下会正确落入 page-progress
   partial/continue contract，而不是被文本回答过早终止。
3. prompt-hint 或 legacy session fallback 不再主导 page recovery / finalization。
4. page router、page recovery、structured orchestration 回归保持绿灯。
