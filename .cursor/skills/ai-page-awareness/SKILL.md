---
name: ai-page-awareness
description: NovusAI AI 页面感知技能。当需要接入或修复 thin page_context、shared UI Runtime、ui_* tools、useCrudList/useCrudPage 的页面 AI 配置，或排查表单 AI 操作问题时，参考此技能。
---

# AI 页面感知技能

## 何时使用

- 给页面接入 AI 页面感知
- 修复 thin `page_context` / shared UI Runtime / `ui_*` tools
- 为 `useCrudPage` / `useCrudList` / `useCrudDrawer` 配置页面 AI 能力
- 处理 `_aiPageKey`、`contextExtras`、表单状态追踪、`use-page-ai-operation-helpers`
- 排查富文本页面 `editor-page-ai-*` exposure

## 当前三层结构

1. `page_context -> input_variables -> system prompt`
2. `ui_read_page` / `ui_get_snapshot` / `ui_read_surface` / `ui_read_region` / `ui_read_table` / `ui_list_interactables`
3. `ui_click` / `ui_open_surface` / `ui_get_form_state` / `ui_set_field` / `ui_fill_form` / `ui_submit_form`

## 核心原则

- 页面 AI 策略以 `route.meta.ai` 为唯一入口
- 使用 `normalizePageKey()` 统一 pageKey
- `page_context` 必须保持 summary-first；细节读取统一走 `ui_read_*`
- `useCrudList` / `useCrudPage` 负责 shared runtime 接入，不要重建旧 page registry
- 表单状态统一通过 `use-form-state-tracker.ts` 维护
- 通用页面操作统一通过 `use-page-ai-operation-helpers.ts` 暴露
- ref 模式表单必须显式传 `_aiPageKey`
- `readonly=false` 的页面操作必须走前端确认
- 富文本页面沿用 `editor-page-ai-exposure.ts` / `editor-page-ai-operations.ts`

## 标准接入流程

1. 确认页面走 `useCrudPage` / `useCrudList` 还是页面本地 composable。
2. 在路由 `meta.ai` 中补齐页面 AI 策略。
3. CRUD 页面补齐 `formSchema` / `searchSchema` / `ai` 配置。
4. 需要补充页面操作时，优先使用 `use-page-ai-operation-helpers.ts`。
5. ref 模式表单的所有打开入口继续显式传 `_aiPageKey`。
6. 通过 `ui_read_page` / `ui_list_interactables` / `ui_get_form_state` 做实际验证。

## 关键禁令

- 禁止手动重建旧 slide-panel page registry
- 禁止跳过 `normalizePageKey()`
- 禁止把 HTML / JSON / tool 参数直接回显给用户
- 禁止复活旧 dedicated page-op 协议或历史 page-aware helper family
- 禁止绕过 `use-ui-action-channel.ts` / shared runtime 直接执行页面动作

## 参考

- [../novusai-saas/references/page-awareness-spec.md](../novusai-saas/references/page-awareness-spec.md)
- [../novusai-saas/references/ai-module.md](../novusai-saas/references/ai-module.md)
- [../websocket-guide/SKILL.md](../websocket-guide/SKILL.md)
