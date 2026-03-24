---
name: ai-page-awareness
description: NovusAI AI 页面感知技能。当需要接入或修复 page_context、get_page_context、invoke_page_operation、pageop_*、useCrudList 的 ai 配置，或排查表单 AI 操作问题时，参考此技能。
---

# AI 页面感知技能

## 何时使用

- 给页面接入 AI 页面感知
- 修复 `get_page_context` / `invoke_page_operation`
- 为 `useCrudList` / `useCrudDrawer` 配置 `ai`
- 处理 `_aiPageKey`、`pageop_*`、`contextExtras`、表单状态追踪

## 三层架构

1. `page_context -> input_variables -> system prompt`
2. `get_page_context`
3. `invoke_page_operation` / `pageop_*`

## 核心原则

- 优先使用 `pageop_*` 专用工具，必要时才回退 `invoke_page_operation`
- 使用 `normalizePageKey()` 统一 pageKey
- `useCrudList` 已自动注册 context，不要再手动 `registerPageContext`
- ref 模式表单必须显式传 `_aiPageKey`
- `readonly=false` 的页面操作必须走前端确认

## 标准接入流程

1. 确认页面属于 `formComponent` 模式还是 ref 模式
2. 补齐 `formSchema` / `searchSchema`
3. 在 `useCrudList` 中配置 `ai`
4. 需要自定义上下文时使用 `contextExtras`
5. 打开表单的所有入口都传递 `_aiPageKey`
6. 通过页面操作和表单状态回读做实际验证

## 关键禁令

- 禁止手动 `registerPageContext` 覆盖 `useCrudList` 自动注册结果
- 禁止跳过 `normalizePageKey()`
- 禁止把 HTML / JSON / tool 参数直接回显给用户
- 禁止绕过注册表直接执行页面操作

## 参考

- [../novusai-saas/references/page-awareness-spec.md](../novusai-saas/references/page-awareness-spec.md)
- [../novusai-saas/references/ai-module.md](../novusai-saas/references/ai-module.md)
- [../websocket-guide/SKILL.md](../websocket-guide/SKILL.md)
