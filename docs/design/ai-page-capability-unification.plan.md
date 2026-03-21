# AI 页面能力统一重构方案

审计日期：2026-03-21

## 一、目标

本次重构的目标不是“继续给个别页面补 AI 操作”，而是把页面 AI 能力统一为一套可扩展、可禁用、可自动接入的机制。

核心目标：

1. **每个页面默认自动拥有基础 AI 能力**
   页面无需逐页手写 `registerPageContext()` / `registerPageOperations()`。

2. **声明式页面自动拥有结构化 AI 能力**
   基于 `useCrudList` / `useCrudPage` / `useDetailPageAi` / `RichTextEditor` 的页面，自动获得对应能力。

3. **每个页面允许声明“禁用哪些 AI 能力”**
   页面可以按能力组或按具体操作进行禁用，而不是只能整体开关。

4. **表策略能力进入页面运行时协议**
   如果某页面支持表策略相关行为，进入页面后必须把“该页面支持哪些表策略动作”传给 AI。

5. **富文本 AI 与普通页面 AI 使用同一套能力协议**
   富文本保留专用工具，但不再是独立体系。

6. **迁移过程必须兼容旧页面**
   旧的 `registerPageContext()` / `registerPageOperations()`、`invoke_page_operation`、`pageop_*` 在迁移期内必须继续工作。

---

## 二、审计结论

### 2.1 当前已经存在的基础能力

当前项目已经具备三块可复用基础设施：

1. 前端页面上下文注册
   - [page-context-registry.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/page-context-registry.ts)

2. 前端页面操作注册
   - [page-operation-registry.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/page-operation-registry.ts)

3. CRUD 页面自动产出标准操作
   - [use-ai-operations.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-ai-operations.ts)
   - [use-crud-list.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-crud-list.ts)
   - [use-crud-page.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/core/adapter/vxe-table/use-crud-page.ts)

另外还存在：

4. 详情页辅助能力
   - [use-detail-page-ai.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-detail-page-ai.ts)

5. 富文本专用页面操作
   - [useEditorPageOps.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/useEditorPageOps.ts)
   - [page_tool_expander.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/page_tool_expander.py)

6. 后端页面上下文与页面操作执行
   - [page_context_executor.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/executors/page_context_executor.py)
   - [page_operation_executor.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/executors/page_operation_executor.py)
   - [sandbox.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/sandbox.py)

### 2.2 当前存在的核心问题

#### 问题 A：同一页面经常同时存在“自动注册”和“手动注册”两套 AI 能力来源

典型页面：

- [table-policies/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/table-policies/index.vue)
- [providers/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/providers/index.vue)
- [models/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/models/index.vue)
- [api-keys/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/api-keys/index.vue)

这些页面同时做了两件事：

1. 在 `useCrudPage/useCrudList` 里打开 `ai: { ... }`
2. 又手写 `registerPageContext()` / `registerPageOperations()`

这会带来三个问题：

1. 页面能力来源不唯一，难以维护。
2. 同名操作存在覆盖关系，行为并不直观。
3. 页面作者很容易以为自己覆盖了操作，实际上可能被自动产物重新覆盖。

#### 问题 B：`ai.mode` 目前没有真正约束页面操作能力

当前 `route.meta.ai.mode` 在以下位置被读取：

- [use-ai-page-policy.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-ai-page-policy.ts)
- [basic.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/layouts/basic.vue)

但它目前只影响“页面是否显示 AI 面板”，**没有真正影响页面操作能力注入**。

现状问题：

1. `context_only` 没有阻止 `available_operations` 被注入。
2. `operate` 和 `context_only` 在运行时几乎没有差别。
3. 页面注册了操作就可能被 AI 看到，即使页面配置本意只是“只读上下文”。

这意味着当前的页面 AI 策略并不闭环。

#### 问题 C：全站并没有统一的“页面能力模型”，只有一堆散落的 page context / page operations

现状是：

1. 页面上下文是一套 Map。
2. 页面操作是一套 Map。
3. CRUD 自动能力是 `use-ai-operations.ts` 里的规则。
4. 富文本能力是 `useEditorPageOps.ts` 的另一套规则。
5. 详情页能力是 `useDetailPageAi.ts` 的另一套规则。

缺少统一抽象导致：

1. 页面无法声明“我支持哪些能力组”。
2. 页面无法声明“我只禁用其中哪一类能力”。
3. 后端拿到的只是扁平化的 `available_operations`，缺少能力层信息。

#### 问题 D：当前“每个页面自动带 AI 能力”只完成了一半

项目现在已经具备：

1. 全局 AI 面板默认可用。
2. `resolvePageContext()` 在无注册时会退化到 DOM 扫描。

但还没有做到：

1. 所有页面自动拥有统一的基础 page AI 能力协议。
2. 所有标准页面自动拥有标准化结构能力。
3. 自定义页面无需手写大量 page op 代码也能被 AI 理解。

也就是说，当前是“全局都有 AI 面板”，不是“全局都有统一的页面 AI 能力”。

#### 问题 E：表策略仍然主要停留在 Skill 配置层，没有进入页面运行时协议

当前表策略核心位于：

- [resolver.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/skills/resolver.py)
- `table_policy_ids`

它已经能控制数据智能 Skill 的 CRUD 能力，但页面层仍然缺少统一协议来表达：

1. 该页面是否支持表策略。
2. 该页面支持哪些表策略动作。
3. 该页面关联哪些表或策略。
4. 该页面是“策略管理页”还是“策略消费页”。

这正是 `admin/ai/table-policies`、`skill-packages`、`skills` 等页面现在显得割裂的原因。

#### 问题 F：富文本能力是强功能，但目前不是统一体系的一部分

富文本当前方案是正确方向：

1. 前端产出 editor ops。
2. 后端展开 dedicated tools。
3. 模型优先调用 `pageop_*` 而非裸 `invoke_page_operation`。

但它的问题是：

1. 它不是统一 capability model 的一个 block。
2. 它现在通过单独注册 page context / page operations 实现。
3. 它和普通页面的禁用、模式控制、能力过滤还没有统一。

#### 问题 G：动态菜单与插件页面 AI 元数据表达能力不足

当前前端动态菜单和插件页面只支持：

1. `mode`
2. `page_context_key`

对应位置：

- [menu-transformer.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/menu-transformer.ts)
- [plugin-slots.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/stores/plugin-slots.ts)
- [manifest.py](E:/git_clone/novusai-saas-yudi/backend/app/plugins/manifest.py)

缺失：

1. `disabled_capabilities`
2. `disabled_operations`
3. 更细粒度的页面 AI 策略

如果这个层面不补齐，那么“每个页面可以禁用哪项 AI 能力”只能覆盖静态页面，无法覆盖动态菜单和插件页。

#### 问题 H：`page_context` 预算有限，不能靠“把整页数据都塞给模型”解决

相关位置：

- [AIChatSlidePanel.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue)
- [page_context_limits.py](E:/git_clone/novusai-saas-yudi/backend/app/services/ai/page_context_limits.py)

所以“让 AI 看表格内容 / 看页面内容”必须采用：

1. 摘要
2. 精确读取操作
3. 按需查看更多

不能用一次性把整页 JSON 全部塞入 `page_context` 的方式。

---

## 三、页面现状分型

### 3.1 已使用自动 AI 的页面

这些页面已经在 `useCrudList/useCrudPage` 中使用 `ai: { ... }`：

- `admin/ai/agent-assignments`
- `admin/ai/agents`
- `admin/ai/api-keys`
- `admin/ai/health`
- `admin/ai/knowledge-bases`
- `admin/ai/models`
- `admin/ai/providers`
- `admin/ai/quotas`
- `admin/ai/table-policies`
- `admin/ai/usage`
- `tenant/ai/agents`
- `tenant/ai/knowledge-bases`
- 若干非 AI 模块页面也已开始接入

### 3.2 自动 + 手动混用的页面

高优先级样板页：

- [table-policies/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/table-policies/index.vue)
- [providers/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/providers/index.vue)
- [models/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/models/index.vue)
- [api-keys/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/api-keys/index.vue)

### 3.3 仍然完全手写 page AI 的页面

代表页面：

- `admin/ai/action-logs`
- `admin/ai/call-logs`
- `admin/ai/conversations`
- `admin/ai/skill-packages`
- `tenant/ai/action-logs`
- `tenant/ai/call-logs`
- `tenant/ai/conversations`
- `tenant/ai/usage`
- `tenant/ai/quotas`

### 3.4 详情页

- [admin/ai/agents/detail.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue)
- [admin/ai/skill-packages/detail.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/skill-packages/detail.vue)
- [tenant/ai/agents/detail.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/tenant/ai/agents/detail.vue)

### 3.5 富文本能力入口

- [RichTextEditor.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/RichTextEditor.vue)
- [useEditorPageOps.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/rich-text-editor/useEditorPageOps.ts)

### 3.6 复合页面

代表页面：

- [admin/ai/quotas/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/quotas/index.vue)
- [admin/ai/usage/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/usage/index.vue)

特点：

1. 同一页包含多个数据区块。
2. 不止一个列表或不止一个能力源。
3. 不能简单地用“一个列表页”建模。

---

## 四、目标架构

## 4.1 总体原则

新架构采用三层自动化：

### Layer 0：全局默认能力

适用于所有页面，无需页面写代码。

提供：

1. 路由上下文
2. DOM 语义快照
3. 基础页面阅读能力

### Layer 1：标准页面自动增强

适用于 `useCrudList`、`useCrudPage`、`useDetailPageAi` 等标准页面。

提供：

1. 列表能力
2. 搜索能力
3. 分页能力
4. 表单能力
5. 详情页能力

### Layer 2：组件级自动附着能力

适用于富文本、图表、文档、插件扩展等组件。

提供：

1. 富文本编辑器能力
2. 特殊业务能力
3. 自定义扩展能力

核心规则：

1. 页面默认自动有基础能力。
2. 标准组件自动追加结构化能力。
3. 页面只在需要“禁用/增强/特例”时写少量配置。

---

## 五、统一能力模型

## 5.1 新增统一概念：Page AI Capability

新增统一能力注册协议：

```ts
interface PageAIMeta {
  mode?: 'disabled' | 'context_only' | 'operate';
  pageContextKey?: string;
  disabledCapabilities?: PageAICapabilityKey[];
  disabledOperations?: string[];
}

interface PageAICapabilityConfig {
  pageKey?: string;
  disable?: {
    capabilities?: PageAICapabilityKey[];
    operations?: string[];
  };
  content?: ContentCapabilityConfig;
  list?: ListCapabilityConfig;
  form?: FormCapabilityConfig;
  detail?: DetailCapabilityConfig;
  editor?: EditorCapabilityConfig;
  tablePolicy?: TablePolicyCapabilityConfig;
  extra?: PageOperation[];
}
```

### 5.2 能力组定义

建议固定能力组如下：

1. `context`
   页面基础上下文能力。

2. `content`
   页面内容读取能力。

3. `search`
   搜索能力。

4. `pagination`
   分页能力。

5. `list_read`
   列表内容读取能力。

6. `form`
   表单读写能力。

7. `submit`
   表单提交能力。

8. `detail`
   详情页导航与刷新能力。

9. `editor`
   富文本专用能力。

10. `table_policy`
    表策略运行时能力。

11. `custom`
    页面特殊扩展能力。

### 5.3 能力组与操作的映射

#### `content`

建议映射：

- `read_current_view`
- `read_current_sections`

#### `search`

- `search`
- `clear_search`

#### `pagination`

- `next_page`
- `prev_page`
- `go_to_page`
- `set_page_size`

#### `list_read`

- `refresh_list`
- `read_visible_rows`
- `read_row_detail`

#### `form`

- `create_record`
- `edit_record`
- `get_form_state`
- `fill_form`
- `validate_form`
- `get_form_options`

#### `submit`

- `submit_form`

#### `detail`

- `refresh_detail`
- `navigate_back`

#### `editor`

- `pageop_get_editor_html`
- `pageop_get_editor_text`
- `pageop_replace_section`
- `pageop_replace_content`
- `pageop_insert_content`
- `pageop_append_content`
- 以及其它 editor 专用操作

#### `table_policy`

不是简单的一组按钮，而是页面运行时向 AI 声明：

```ts
table_policy_support: {
  enabled: true,
  kind: 'management' | 'consumer',
  supported_actions: string[],
  related_tables?: string[],
  related_policy_ids?: number[],
}
```

---

## 六、模式与禁用规则

## 6.1 `mode` 的正确语义

### `disabled`

1. 页面 AI 面板不展示。
2. 不注入页面上下文。
3. 不注入页面操作。

### `context_only`

1. 页面允许 AI 看到页面上下文。
2. **不允许暴露页面操作**。
3. 富文本 dedicated tools 也不应该暴露。

### `operate`

1. 页面允许 AI 看到页面上下文。
2. 允许暴露页面操作。
3. 允许富文本 dedicated tools。

### 审计结论

当前 `context_only` 与 `operate` 没有真正分离，因此这部分必须作为 P0 先修。

## 6.2 禁用规则优先级

建议统一优先级：

1. `mode=disabled`
2. Route/Menu/Plugin `disabledCapabilities`
3. 页面 composable `disable.capabilities`
4. Route/Menu/Plugin `disabledOperations`
5. 页面 composable `disable.operations`

## 6.3 兼容规则

现有 `useCrudList/useCrudPage` 中的 `ai.disabled` 当前语义是“禁用操作名列表”。

迁移策略：

1. 旧字段继续保留，映射为 `disabledOperations`。
2. 新增 `disabledCapabilities`。
3. 两者可同时存在。

---

## 七、自动化接入策略

## 7.1 所有页面默认自动拥有基础 AI 能力

基础自动能力来源：

1. 路由信息
2. 页面标题
3. DOM 语义扫描
4. 当前 URL、弹窗、抽屉等视觉状态

实现位置：

- [use-ai-page-policy.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/composables/use-ai-page-policy.ts)
- [AIChatSlidePanel.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue)
- [page-context-registry.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/page-context-registry.ts)

目标效果：

1. 任意页面不写一行 AI 页面代码，也能被 AI 知道“当前在哪一页、页面标题是什么、页面上有哪些主要内容块”。
2. 这层默认只提供基础读取，不自动提供危险操作。

## 7.2 标准 CRUD 页面自动增强

对 `useCrudList` / `useCrudPage`：

自动识别并产出：

1. 搜索能力
2. 分页能力
3. 列表读取能力
4. 表单能力
5. 回收站能力
6. 当前可见列、当前过滤条件、当前列表摘要

新增目标：

1. 自动补充 `read_visible_rows`
2. 自动补充 `read_row_detail`
3. 自动补充 `read_current_view`
4. 自动补充能力组禁用逻辑

## 7.3 详情页自动增强

对 `useDetailPageAi`：

自动产出：

1. `refresh_detail`
2. `navigate_back`
3. 详情页主实体摘要
4. 详情页当前 tab/section 状态

## 7.4 富文本自动增强

对 `RichTextEditor`：

1. 页面挂载富文本组件时自动追加 editor capability。
2. 后端根据 editor capability 自动展开 dedicated tools。
3. editor 能力受 `mode` 与 `disabledCapabilities` 统一控制。

## 7.5 复合页面自动增强

复合页面需要统一引入 `content blocks` 概念。

例如：

- Usage 页：统计卡片、趋势图、表格预览
- Quotas 页：Quota Tab、Rate Limit Tab

建议引入：

```ts
content: {
  blocks: () => [
    { key: 'summary_cards', type: 'stats', data: ... },
    { key: 'trend_chart', type: 'series', data: ... },
    { key: 'quota_tab', type: 'list', data: ... },
  ],
}
```

这部分应允许页面“补充结构化内容块”，但不是强制每页都写。

---

## 八、表策略能力统一方案

## 8.1 设计目标

如果页面支持表策略相关行为，进入页面后必须在 `page_context.page_data` 中明确告诉 AI：

1. 页面是否支持表策略。
2. 页面是策略管理页还是策略消费页。
3. 页面支持哪些表策略动作。
4. 页面关联哪些表或策略。

## 8.2 统一结构

建议统一使用：

```ts
table_policy_support: {
  enabled: true,
  kind: 'management' | 'consumer',
  supported_actions: [
    'list_policies',
    'sync_policies',
    'edit_policy',
    'inspect_columns',
    'jump_to_related_skills',
    'select_policy',
    'filter_by_policy',
  ],
  related_tables?: string[],
  related_policy_ids?: number[],
  related_resources?: string[],
}
```

## 8.3 页面分型

### 管理页

例如：

- `admin/ai/table-policies`

支持动作建议：

- `list_policies`
- `sync_policies`
- `edit_policy`
- `inspect_columns`
- `jump_to_related_skills`

### 消费页

例如：

- 技能包页面
- 技能表单页面
- 数据智能技能页面

支持动作建议：

- `select_policy`
- `filter_by_policy`
- `show_related_policy_info`

## 8.4 前端声明方式

建议页面或组件只声明一次：

```ts
tablePolicy: {
  enabled: true,
  kind: 'management',
  supportedActions: ['list_policies', 'sync_policies', 'edit_policy'],
  relatedTables: ['ai_table_policies'],
}
```

而不是在每个页面里手工拼接 `contextExtras`。

---

## 九、富文本能力统一方案

## 9.1 保留 dedicated tools，禁止退回纯 wrapper 方案

富文本方向保持不变：

1. 编辑器页面优先暴露 dedicated tools。
2. 仍由后端重定向到 `invoke_page_operation` 执行。
3. 保留现有 `pageop_*` 兼容能力。

## 9.2 富文本纳入统一 capability model

`useEditorPageOps` 不再直接作为“另一套 page AI 系统”，而改成：

1. editor capability provider
2. 自动附着在页面 capability registry 下

## 9.3 错误模型统一

继续统一并固定以下错误类型：

- `invalid_input`
- `target_not_found`
- `non_unique_match`
- `invalid_html`
- `pending_confirmation`
- `user_cancelled`
- `timeout`

## 9.4 mode / disable 统一控制

当页面：

1. `mode=context_only`
2. `disabledCapabilities` 包含 `editor`

则：

1. 不应在 `available_operations` 中出现 editor ops。
2. 不应在后端扩展 `pageop_*`。

---

## 十、动态菜单与插件页面方案

## 10.1 Route/Menu/Plugin 统一元信息扩展

需要扩展到三条链路：

1. 静态路由
2. 动态菜单
3. 插件 standalone page

统一增加：

```ts
ai: {
  mode?: 'disabled' | 'context_only' | 'operate';
  pageContextKey?: string;
  disabledCapabilities?: string[];
  disabledOperations?: string[];
}
```

## 10.2 需要修改的位置

前端：

- [menu-transformer.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/menu-transformer.ts)
- [plugin-slots.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/stores/plugin-slots.ts)

后端：

- [manifest.py](E:/git_clone/novusai-saas-yudi/backend/app/plugins/manifest.py)
- [\_extension_registrar.py](E:/git_clone/novusai-saas-yudi/backend/app/plugins/_extension_registrar.py)

---

## 十一、迁移批次与详细任务

## Batch 0：协议与约束先落地

### 目标

先把“统一能力模型”和“模式/禁用规则”定下来，并接入 layout 与 AI 面板，不先改大量页面。

### 任务

#### B0-T1 定义前端统一类型

涉及：

- 新增 `page-capability-registry.ts`
- 更新 `use-ai-page-policy.ts`
- 更新 `page-context-registry.ts`
- 更新 `page-operation-registry.ts`

交付：

1. 定义 `PageAIMeta`
2. 定义 `PageAICapabilityConfig`
3. 定义 `PageAICapabilityKey`
4. 定义 capability -> operation 的映射规则

#### B0-T2 真正落实 `mode`

涉及：

- [basic.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/layouts/basic.vue)
- [AIChatSlidePanel.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue)

交付：

1. `disabled` 隐藏页面 AI
2. `context_only` 仅保留上下文，不注入可执行操作
3. `operate` 才允许注入操作

#### B0-T3 加入 `disabledCapabilities` / `disabledOperations`

涉及：

- 静态路由 meta
- 动态菜单 meta
- 插件 page AI meta

交付：

1. 前端可读取两类禁用规则
2. 前端可合并 route + page config 两层禁用
3. 旧 `ai.disabled` 兼容为 `disabledOperations`

#### B0-T4 全站基础自动能力落地

涉及：

- `resolvePageContext()`
- DOM fallback
- AI Panel 注入逻辑

交付：

1. 所有页面默认有基础 `context + content`
2. 不需要逐页注册基础 page context

### 验收

1. 一个未接入标准 composable 的普通页面，也能被 AI 正确识别页面名和基础 DOM 内容。
2. `context_only` 页面不会暴露 `available_operations`。
3. 页面可通过 meta 禁用某一组能力。

---

## Batch 1：重构 CRUD 自动能力生产器

### 目标

让 `useCrudList` 与 `useCrudPage` 成为真正统一的标准页面能力生产器。

### 任务

#### B1-T1 重构 `use-ai-operations.ts`

交付：

1. 操作生成从“散装函数”升级为“能力组编译器”
2. 新增 `read_visible_rows`
3. 新增 `read_row_detail`
4. 新增 `read_current_view`

#### B1-T2 重构 `useCrudList`

交付：

1. 自动注册统一 capability config
2. 支持 `disabledCapabilities`
3. 支持 `disabledOperations`
4. 继续兼容 `ai.extra`

#### B1-T3 重构 `useCrudPage`

交付：

1. 去掉“自动注册 + 页面手写 register 再覆盖”的隐式冲突模式
2. 统一由 capability registry 产出 `available_operations`
3. `formAiOperations` 变为过渡兼容字段，后续逐步下线

#### B1-T4 把列表页分页、搜索、表单能力纳入统一能力组

交付：

1. `search`
2. `pagination`
3. `list_read`
4. `form`
5. `submit`

### 验收

1. 只写 `ai: {}` 的 CRUD 页面即可自动拥有完整标准能力。
2. 页面不再需要手写 `refresh/search/create_record` 这种重复代码。

---

## Batch 2：重构详情页与复合页能力

### 目标

统一详情页与复合页面的页面能力表达。

### 任务

#### B2-T1 重构 `useDetailPageAi`

交付：

1. 改成 capability producer
2. 自动产出 `detail` 能力组
3. 支持禁用 `detail`

#### B2-T2 引入 `content blocks`

适用：

- Usage
- Quotas
- Dashboard 型页面

交付：

1. 结构化块状上下文
2. 支持 tab / section / summary / chart / cards

#### B2-T3 统一当前 tab / 当前 section 状态

交付：

1. 页面上下文中可表达当前激活 tab
2. AI 可知道当前查看的是哪一块，而不是只知道整页

### 样板页

优先样板：

- [admin/ai/usage/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/usage/index.vue)
- [admin/ai/quotas/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/ai/quotas/index.vue)

### 验收

1. Usage 页 AI 能看懂统计卡片、趋势图、表格摘要。
2. Quotas 页 AI 能区分 Quota Tab 与 Rate Limit Tab。

---

## Batch 3：富文本并入统一能力体系

### 目标

让富文本能力成为统一 capability model 的一部分。

### 任务

#### B3-T1 重构 `useEditorPageOps`

交付：

1. 改为 editor capability provider
2. 不再直接作为独立 page AI 体系注册
3. 继续兼容现有 editor 行为

#### B3-T2 后端工具展开逻辑适配 capability model

涉及：

- [page_tool_expander.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/page_tool_expander.py)
- [sandbox.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/sandbox.py)
- [page_context_executor.py](E:/git_clone/novusai-saas-yudi/backend/app/ai/tools/executors/page_context_executor.py)

交付：

1. 仅在 editor capability 启用时展开 dedicated tools
2. 与 `mode` / `disabledCapabilities` 联动

#### B3-T3 editor 错误类型与确认流程统一

交付：

1. 统一 `error_type`
2. 统一返回结构
3. 统一确认流程

### 验收

1. 富文本页仍优先使用 dedicated tools。
2. `context_only` 页面不会暴露 editor tools。
3. 普通页面与富文本页共用同一套禁用机制。

---

## Batch 4：表策略运行时能力接入

### 目标

把表策略从“Skill 配置层”扩展到“页面运行时能力层”。

### 任务

#### B4-T1 定义 `tablePolicy` capability block

交付：

1. 前端能力声明结构
2. page_context 输出结构
3. 后端 prompt 展示规则

#### B4-T2 管理页样板：`admin/ai/table-policies`

交付：

1. 通过 capability block 自动输出该页支持的表策略动作
2. 去掉手写 `registerPageContext/registerPageOperations`
3. 保留特例动作，如 `sync_policies`

#### B4-T3 消费页样板：`skill-packages` / `skills`

交付：

1. AI 知道当前页是“表策略消费页”
2. AI 知道支持 `select_policy/filter_by_policy/show_related_policy_info`

#### B4-T4 后端 page context 展示增强

交付：

1. page_context 输出中专门展示 `table_policy_support`
2. 避免埋在 `Data: { ... }` 里不显眼

### 验收

1. 进入 `table-policies` 页面后，AI 能明确知道该页支持哪些策略动作。
2. 进入技能相关页面后，AI 能明确知道该页如何消费表策略。

---

## Batch 5：迁移混用页面

### 目标

优先消灭“自动 + 手动混用”的冲突页面。

### 任务

#### B5-T1 迁移 `admin/ai/providers`

删除：

1. 手写 `registerPageContext`
2. 手写 `registerPageOperations`

保留：

1. 必要的特例 `extra`

#### B5-T2 迁移 `admin/ai/models`

同上。

#### B5-T3 迁移 `admin/ai/api-keys`

同上。

#### B5-T4 迁移 `admin/ai/table-policies`

同上，但额外接入 `tablePolicy` capability。

### 验收

1. 页面功能行为不变。
2. 代码中不再同时出现 `ai: {}` 与手写 `registerPageContext/registerPageOperations` 的双轨模式。

---

## Batch 6：迁移纯手写页面

### 目标

把纯手写 page AI 的 AI 模块页面收口到统一能力协议。

### 任务

第一批：

1. `admin/ai/action-logs`
2. `admin/ai/call-logs`
3. `admin/ai/conversations`
4. `tenant/ai/action-logs`
5. `tenant/ai/call-logs`
6. `tenant/ai/conversations`

第二批：

1. `admin/ai/skill-packages`
2. `tenant/ai/usage`
3. `tenant/ai/quotas`

迁移方式：

1. 先接入统一 capability registry
2. 再把原来的手写逻辑收敛到 `extra`
3. 最后删除重复 register 代码

### 验收

1. 手写页面数量显著下降。
2. 纯手写只保留极少数特例。

---

## Batch 7：动态菜单、插件页、全站收口

### 目标

让动态菜单与插件页面同样支持页面级 AI 禁用策略。

### 任务

#### B7-T1 扩展前端动态菜单解析

涉及：

- `menu-transformer.ts`

#### B7-T2 扩展插件 page AI schema

涉及：

- `manifest.py`
- `plugin-slots.ts`
- `_extension_registrar.py`

#### B7-T3 统一文档与技能说明

涉及：

- page awareness 规范
- AI 模块规范
- 富文本规范

### 验收

1. 动态菜单页面也能声明禁用能力。
2. 插件独立页面也能声明禁用能力。

---

## 十二、建议的页面迁移顺序

推荐顺序如下：

### 第一批样板

1. `admin/ai/table-policies`
2. `admin/ai/providers`
3. `admin/ai/models`
4. `admin/ai/api-keys`
5. 一个富文本页面

### 第二批

1. `admin/ai/usage`
2. `admin/ai/quotas`
3. `admin/ai/skill-packages`

### 第三批

1. `admin/ai/action-logs`
2. `admin/ai/call-logs`
3. `admin/ai/conversations`
4. tenant 对应页

### 第四批

1. 详情页
2. 动态菜单页
3. 插件 standalone pages

---

## 十三、测试任务

## 13.1 前端单测

需要新增或补强：

1. capability -> operations 编译测试
2. `mode=context_only` 时不暴露操作测试
3. `disabledCapabilities` / `disabledOperations` 过滤测试
4. CRUD 自动能力测试
5. detail capability 测试
6. editor capability 测试
7. table policy capability 测试

## 13.2 前端集成测试

需要覆盖：

1. 页面切换后 AI 面板上下文更新
2. 页面操作确认流程
3. 富文本 dedicated tools 仍可执行
4. 复合页面 tab 切换后的上下文正确性

## 13.3 后端测试

需要覆盖：

1. `page_context_executor` 正确展示 capability 相关信息
2. `page_tool_expander` 在 editor 禁用时不扩展
3. `sandbox` 在 `context_only` 情况下不执行页面操作
4. 表策略运行时能力输出与提示正确

---

## 十四、验收标准

本次重构完成后，应满足：

1. 任意页面默认自动有基础 AI 上下文能力。
2. 标准 CRUD 页面无需手写 register，即可拥有标准 AI 能力。
3. 页面可以按能力组禁用 AI 能力，也可以按操作禁用。
4. `context_only` 与 `operate` 在运行时有明确差异。
5. 表策略能力进入页面运行时协议。
6. 富文本能力并入统一 capability model。
7. 动态菜单与插件页面同样支持 AI 禁用策略。
8. 旧页面在迁移期间不中断。

---

## 十五、风险与回滚策略

### 风险 1：行为变化范围大

缓解：

1. 先上 capability registry，不立刻删旧逻辑。
2. 页面分批迁移。

### 风险 2：`context_only` 生效后，部分页面会突然失去操作能力

缓解：

1. 样板页先切。
2. 批量梳理页面 meta.ai.mode。

### 风险 3：富文本与旧 prompt 兼容性

缓解：

1. 保留 `pageop_* -> invoke_page_operation` 兼容链路。
2. 后端保留旧工具名保护名单。

### 风险 4：动态菜单/插件页元信息未及时升级

缓解：

1. 缺省仍按 `context_only` 处理。
2. 新字段缺失时使用默认值。

---

## 十六、建议的立即执行项

建议先执行以下 6 个任务作为 P0：

1. `B0-T1` 定义统一 capability 类型与禁用规则。
2. `B0-T2` 真正落实 `mode` 语义。
3. `B0-T3` 扩展 route/menu/plugin AI meta。
4. `B1-T1` 重构 `use-ai-operations.ts` 为 capability 编译器。
5. `B5-T4` 迁移 `admin/ai/table-policies` 作为第一样板页。
6. `B3-T1` 重构 `useEditorPageOps` 并入统一 capability model。

如果只允许先做一个最小闭环，建议闭环顺序为：

1. `mode + disabledCapabilities`
2. `useCrudPage/useCrudList` capability 化
3. `table-policies` 页面样板迁移
4. `RichTextEditor` capability 化

