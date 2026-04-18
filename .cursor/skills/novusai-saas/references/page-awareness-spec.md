# 页面感知系统规范 / Page Awareness System Specification

> 当前页面感知系统已从旧的 registry + dedicated page-op 架构迁移到共享
> UI Runtime `ui_*` 工具链。本文件只保留现行
> 工作树中的稳定接入方式；旧设计若仍见于历史审计材料，应视为归档记录，
> 不得再作为新实现依据。

## 一、当前架构 / Current Architecture

页面感知系统现在围绕“薄 `page_context` + 共享 UI Runtime + `ui_*` tools”
组织：

| 层级 | 组件 | 职责 |
|------|------|------|
| Layer 1 | `page_context` → `input_variables` | 注入当前页面的摘要态：`page_key`、`page_title`、`locale`、`surface_stack`、`ui_epoch` 等 |
| Layer 2 | `ui_read_page` / `ui_get_snapshot` / `ui_read_surface` / `ui_read_region` / `ui_read_table` / `ui_list_interactables` | 需要细节时按需读取页面、surface、region、table 或交互项 |
| Layer 3 | `ui_click` / `ui_open_surface` / `ui_get_form_state` / `ui_set_field` / `ui_fill_form` / `ui_submit_form` | 在共享安全策略与确认策略下执行页面读写操作 |

## 二、核心文件 / Core Files

### 前端

| 文件 | 职责 |
|------|------|
| `frontend/apps/web-antd/src/components/business/ai-runtime/runtime-bridge.ts` | 共享 UI Runtime 公共入口；负责导出 thin `page_context` 和 `ui_*` 读取能力 |
| `frontend/apps/web-antd/src/components/business/ai-runtime/ui-runtime.ts` | UI 图、surface 栈、`ui_epoch` 的统一运行时 |
| `frontend/apps/web-antd/src/components/business/ai-runtime/page-key-utils.ts` | `page_key` 规范化与路由解析 |
| `frontend/apps/web-antd/src/components/business/ai-runtime/page-operation-types.ts` | 页面操作读模型类型 |
| `frontend/apps/web-antd/src/composables/use-form-state-tracker.ts` | 表单会话追踪与 fallback 读写辅助 |
| `frontend/apps/web-antd/src/composables/use-ui-action-channel.ts` | `ui_*` action channel 对接 |
| `frontend/apps/web-antd/src/composables/use-page-ai-operation-helpers.ts` | 通用页面操作 helper facade |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/editor-page-ai-exposure.ts` | 富文本页面 AI exposure 注册与收集 |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/editor-page-ai-operations.ts` | 富文本页面操作 contract |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/editor-ai-adapter.ts` | 编辑器 AI 适配层 |

### 后端

| 文件 | 职责 |
|------|------|
| `backend/app/ai/tools/page_runtime/definitions.py` | `ui_*` page-runtime tools 的定义面 |
| `backend/app/ai/tools/page_runtime/executor.py` | page-runtime executor seam，含 `ui_get_snapshot -> ui_read_page` 兼容别名 |
| `backend/app/ai/tools/sandbox.py` | live sandbox 工具分发；当前仍有过渡期 legacy executor wiring，但对外工具面以 `ui_*` 为准 |

## 三、`page_key` 规范 / Page Key Convention

所有页面感知入口统一使用点号格式的 `page_key`：

```text
admin.ai.agents
tenant.ai.agents
admin.ai.quotas
```

规则：

- `normalizePageKey()` / `resolveRoutePageKey()` 是唯一权威入口。
- 路由层优先使用 `route.meta.ai.pageContextKey`；没有显式配置时再从路径规范化。
- 新页面不要再引入第二套 page-key registry 或手写 normalize 规则。

## 四、薄 `page_context` 契约 / Thin `page_context` Contract

前端通过 `getRuntimeThinPageContext()` 组装摘要态页面上下文，典型字段包括：

```ts
interface PageContext {
  page_key: string;
  page_title?: string;
  locale?: string;
  page_session_id?: string;
  active_form_session_id?: string;
  active_form_summary?: ActiveFormSummary;
  active_surface_id?: string;
  surface_stack?: PageSurfaceSummary[];
  suggested_tools?: PageContextSuggestedTools;
  ui_epoch?: number;
  page_data?: Record<string, unknown>;
}
```

约束：

- `page_context` 必须保持 summary-first，只放轻量摘要，不放完整 DOM、HTML 或整页 UI graph。
- 需要深度内容时，统一通过 `ui_read_page` / `ui_get_snapshot` / `ui_read_surface` / `ui_read_region` / `ui_read_table` 按需读取。
- `page_context.page_data` 只是可选的后端扩展摘要，不是前端 dump 任意页面状态的兜底口。

## 五、`ui_epoch` 与增量状态 / `ui_epoch` And Incremental State

`ui_epoch` 是前后端协作的 stale-context 保护字段：

- `UIRuntime` 会在 route、surface、graph 变化时 bump epoch。
- thin `page_context` 会携带当前 `ui_epoch`。
- `ui_*` 工具调用可带 `ui_epoch` 参数，后端据此做 stale-context guard。
- `ui_get_snapshot` 是 `ui_read_page` 的兼容别名；对外仍可接收旧名字，但文档与新代码都应优先写 `ui_read_page`。

## 六、CRUD 页面接入 / CRUD Page Integration

当前 CRUD 页面优先复用平台共享 helper：

1. 路由在 `route.meta.ai` 声明页面 AI 策略。
2. `useCrudPage` / `useCrudList` 负责 page-awareness 接入，不要重建 page registry。
3. 表单链路通过 `useCrudDrawer` + `use-form-state-tracker.ts` 维持 `form_session` 状态。
4. 额外页面操作通过 `use-page-ai-operation-helpers.ts` 暴露，保持 `PageOperation` contract。

常见稳定入口：

- `buildPageAIFormExtraData()`
- `createParameterizedPageOperation()`
- `createCreateRecordPageOperation()`
- `createOpenPageOperation()`
- `createRefreshPageOperation()`

不要再新增：

- 旧全局页面操作 helper facade
- 旧 slide-panel page registry
- 旧 dedicated page-op 展开层

## 七、富文本页面接入 / Rich Text Integration

富文本页面当前不再走旧 registry + dedicated page-op 架构，而是使用富文本 AI exposure seam：

- `registerRichTextPageAIExposure()`
- `listRichTextPageAIOperations()`
- `collectRichTextPageAIContextData()`
- `executeRichTextPageAIOperation()`

当前富文本 companion files：

- `editor-page-ai-exposure.ts`
- `editor-page-ai-operations.ts`
- `editor-content-helpers.ts`
- `editor-command-helpers.ts`
- `editor-ai-adapter.ts`

规则：

- 页面级富文本能力只在 exposure seam 内聚合，不回退到全局 page registry。
- 需要 editor 特有上下文时，通过 exposure 的 `getContextData()` / `getOperations()` 提供。
- 新增编辑器 AI 行为时，沿用 `editor-page-ai-*` 体系，不要复活旧富文本任务 launcher 或旧 runtime registry skeleton。

## 八、当前 `ui_*` 工具面 / Current `ui_*` Tool Surface

### 读工具

- `ui_read_page`
- `ui_get_snapshot`
- `ui_read_surface`
- `ui_read_region`
- `ui_read_table`
- `ui_list_interactables`
- `ui_get_form_state`

### 写工具

- `ui_click`
- `ui_open_surface`
- `ui_set_field`
- `ui_fill_form`
- `ui_submit_form`

约束：

- 读写分离必须与 `PageOperation.readonly` / route AI policy 对齐。
- `ui_*` 调用必须经过共享 security-policy 和确认策略。
- 页面无法满足请求时，应优先通过 `ui_list_interactables` / `ui_read_surface` / `ui_read_page` 补足上下文，而不是臆造旧 dedicated page-op 调用。

## 九、已知稳定保护 / Stable Guardrails

- 共享 Runtime 扫描必须排除 `[data-ai-panel]` 与 `data-ai="off"` 子树。
- `listRuntimeInteractables()` 最多返回 200 项，`truncated` 与 `items` 数量必须一致。
- `formStateTracker` fallback 只在“唯一活动表单”场景下生效；多表单并存时必须依赖精确 session/page key。
- 破坏性动作必须经 security policy / confirmation guard，而不是页面自己私下放行。

## 十、迁移禁区 / Retired Patterns

以下模式已退役，只能出现在历史审计或归档文档中：

- registry 驱动的旧页面操作协议
- dedicated page-op 工具展开层
- slide-panel 私有页面注册表
- 旧全局页面操作 helper facade

新实现禁止把这些旧 seam 重新接回当前运行链。

## 十一、接入检查清单 / Checklist

- [ ] 路由是否只通过 `route.meta.ai` 暴露页面 AI 策略
- [ ] 页面是否优先复用 `useCrudPage` / `useCrudList`
- [ ] 是否通过 `use-form-state-tracker.ts` 维护表单状态
- [ ] 是否通过 `use-page-ai-operation-helpers.ts` 暴露页面操作
- [ ] 富文本页面是否使用 `editor-page-ai-exposure.ts` / `editor-page-ai-operations.ts`
- [ ] `page_context` 是否保持 summary-first
- [ ] 细节读取是否改用 `ui_read_*` / `ui_get_snapshot`
- [ ] 是否彻底避免旧 page registry / 旧 dedicated page-op 协议

## 十二、权威参考 / Canonical References

- `.trellis/spec/ai-runtime/tool-skill-governance.md`
- `.trellis/spec/ai-runtime/frontend-ai-shell.md`
- `frontend/apps/web-antd/src/components/business/ai-runtime/**`
- `backend/app/ai/tools/page_runtime/**`
