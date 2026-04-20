# Codex Frontend Live Truth Freeze

## Goal

把 frontend page-AI / chat-AI 展示与交互层继续收口到 canonical runtime contract。
目标不是“让 UI 更聪明”，而是防止 UI 再制造第二份 live truth：
只消费 canonical `ui_*` tool names、`turn_flow`、`turn_skill_activation`、
runtime capability summary、pending confirmation `tool_name`，不再借 `suggested_tools`
或 legacy page-op 名称回推运行时语义。

## Current Gap

当前 frontend 已经大幅收掉 legacy `navigate_menu` / `fill_form` 等 live 名称，
也把 `suggested_tools` 限制在 affordance/UX 侧，但仍有剩余风险：

1. slide panel / chat panel / page capability UI 仍可能借展示层 helper 重建语义。
2. 新加的 activation diagnostics 还没有完全进入所有 relevant UI contract。
3. 如果 frontend 不在最后统一冻结，旧 seam 很容易通过 pending-op、
   capability chips、或 route policy helper 重新长回来。
4. `ai-chat-panel` 仍保留 `legacy-*` turn-flow synthesis / persisted backfill /
   tool-call and rag evidence projection，当前 live UI 在 canonical `turn_flow`
   缺失时仍会重建第二份历史语义。
5. `use-ai-chat-page-operations.ts` 仍把 `suggested_tools` 作为 interactive-page
   fallback，并在 join/ready 流程里继续携带 `page_key`，这会让 UX hint 与
   route fallback 重新触碰 live page-op transport。

## Write Scope

- `frontend/apps/web-antd/src/components/business/ai-slide-panel/**`
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/**`
- `frontend/apps/web-antd/src/composables/use-ai-page-policy.ts`
- `frontend/apps/web-antd/src/utils/ai-page-capabilities.ts`
- 对应 frontend chat/page-AI tests

## Requirements

1. frontend 只认 canonical `ui_*` page tools、canonical diagnostics、
   canonical pending-confirmation key，不得再引入 legacy page-op live names。
2. `suggested_tools` 只能做 UX affordance，不得决定 live capability、pending action、
   confirmation、或 monitoring summary。
3. activation-related diagnostics，例如 `turn_skill_activation`、runtime capability
   summary、selected skills/tools，要进入 relevant UI surfaces，但只能做展示，不得回推路由。
4. page AI 唯一链路必须继续保持：
   `route/meta -> page policy -> slide/chat panel -> runtime bridge`，
   不得新增 page-local AI bypass。
5. 相关 tests 必须覆盖 capability filter、tool-call display、pending confirmation、
   slide panel page capability wiring。
6. 对于当前新 SaaS live turns，frontend 不得再把 `turnFlow`、`toolCalls`、
   `ragSources`、`thinkingContent` 互相 backfill 成 `legacy-*` timeline，
   也不得再把 legacy timeline 当作默认 live 展示 owner。
7. page-operation channel readiness 只能依据 canonical runtime facts
   （如 live `page_session_id` / runtime page facts）判断；
   `suggested_tools` 与 route-derived `page_key` 不得继续充当 live gating owner。

## Acceptance

1. frontend 页面 AI 展示层不再复活 legacy page-op 名称或 `suggested_tools`
   反向驱动运行时的 seam。
2. 相关 UI surfaces 能展示 canonical selected tools/skills 与 activation reason，
   但不会创造第二份 runtime state。
3. `ai-chat-panel` / `slide-panel` 对当前 live turns 不再默认产出
   `legacy-thinking`、`legacy-tool-selection`、`legacy-tool-execution` 等回填阶段。
4. page capability、tool-call display、pending confirmation、turn-flow display
   回归保持绿灯。
5. `basic.vue` 继续保持唯一 live page-AI shell chain。
