# 页面感知系统规范 / Page Awareness System Specification

> AI 页面感知系统的完整架构、接入方式和数据流规范。

---

## 一、架构概述 / Architecture Overview

页面感知系统采用三层架构，使 AI 能够感知用户当前页面的上下文并执行页面操作：

| 层级 | 组件 | 职责 |
|------|------|------|
| Layer 1 | `page_context` → `input_variables` → `system prompt` | 基础页面感知（页面标题、数据统计） |
| Layer 2 | `get_page_context` builtin skill | 深度上下文（表单字段、实体描述、可用操作列表） |
| Layer 3 | `invoke_page_operation` builtin skill | 通过 WebSocket 执行前端操作（填表、搜索、导航） |

### 核心文件 / Core Files

| 文件 | 职责 |
|------|------|
| `composables/use-ai-operations.ts` | Schema 提取、标准操作生成、远程选项预加载 |
| `composables/use-form-state-tracker.ts` | 表单状态追踪单例（open/close/values/validation） |
| `composables/use-crud-form.ts` | useCrudDrawer 自动集成 formStateTracker |
| `composables/use-crud-list.ts` | useCrudList 自动注册 context + operations |
| `components/business/ai-slide-panel/page-context-registry.ts` | 页面上下文注册表 |
| `components/business/ai-slide-panel/page-operation-registry.ts` | 页面操作注册表 |
| `components/business/ai-slide-panel/page-key-utils.ts` | pageKey 规范化工具 |

---

## 二、pageKey 规范 / Page Key Convention

所有注册表使用 **点号格式** 的 pageKey 作为唯一标识：

```
admin.ai.agents       ← normalizePageKey('/admin/ai/agents')
tenant.ai.agents      ← normalizePageKey('tenant/ai/agents')
admin.ai.quotas       ← 已经是点号格式，原样返回
```

**规则**：
- `normalizePageKey()` 是唯一权威的规范化函数
- 有 `pageop_*` 专用工具时优先使用，仅不可用时回退到 `invoke_page_operation`
- 去除前导 `/`，将所有 `/` 替换为 `.`
- 所有注册和查找必须经过此函数

---

## 三、formComponent 模式接入 / formComponent Mode Integration

适用于 `useCrudList` 的 `formComponent` 配置指向表单组件的页面（标准模式）。

### 步骤

1. **data.ts 中导出 schema 工厂函数**：

```typescript
export function useFormSchema(isEdit = false): VbenFormSchema[] { ... }
export function useGridFormSchema(): VbenFormSchema[] { ... }
```

2. **index.vue 中配置 ai**：

```typescript
const { list, FormDrawer, onCreate, onEdit, ... } = useCrudList<ItemType>({
  api: { list: getListApi, resource: '/admin/items' },
  formComponent: Form,
  i18nPrefix: 'admin.module',
  ai: {
    formSchema: useFormSchema,                    // ← 表单 schema
    searchSchema: useGridFormSchema,              // ← 搜索 schema（可选）
    entityName: $t('admin.module.name'),          // ← AI 可读的实体名
    entityDescription: '管理模块的配置和状态',       // ← 业务描述
    openRecycleBin: () => recycleBinRef.value?.open(),
    contextExtras: () => ({                       // ← 额外 context 数据
      custom_stat: someComputed.value,
    }),
  },
});
```

3. **禁止手动 registerPageContext** — `useCrudList` 已自动注册，手动注册会覆盖增强数据。

### 自动获得的能力

配置 `formSchema` 后，自动生成以下操作：
- `refresh_list` — 刷新列表
- `search` / `clear_search` — 搜索（需 `searchSchema`）
- `create_record` / `edit_record` — 打开表单（需 `formPopupApi`）
- `get_form_state` — 获取表单状态
- `fill_form` — 填充表单字段
- `validate_form` — 触发验证
- `get_form_options` — 获取远程下拉选项

---

## 四、ref 模式接入 / Ref Mode Integration

适用于表单组件通过 `ref` 管理（非 `formComponent` 配置）的页面。

### 步骤

1. **定义 AI_PAGE_KEY 常量**：

```typescript
const AI_PAGE_KEY = 'admin.ai.agents';
```

2. **useCrudList 配置**：

```typescript
const { list, loadList, searchKeyword, onSearch, ... } = useCrudList<ItemType>({
  api: { ... },
  customActions: {
    edit: (row) => formRef.value?.openEdit(row, { _aiPageKey: AI_PAGE_KEY }),
  },
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: (isEdit?: boolean) => useFormSchema(isEdit ?? false),
    entityName: $t('admin.ai.agent.name'),
    entityDescription: '管理智能体的配置和发布状态',
    contextExtras: () => ({ published: stats.value.published }),
    extra: [
      {
        name: 'create_agent',
        label: $t('shared.pageOperation.createRecord'),
        description: 'Open create form / 打开新建表单',
        readonly: false,
        handler: async (params) => {
          formRef.value?.openNew({ _aiPageKey: AI_PAGE_KEY, ...overrides });
          return { success: true, message: 'Form opened / 表单已打开' };
        },
      },
    ],
  },
});
```

3. **所有表单打开入口传递 `_aiPageKey`**（包括模板中的按钮）：

```typescript
// 包装函数
function onCreateItem() {
  formRef.value?.openNew({ _aiPageKey: AI_PAGE_KEY });
}
function onEditItem(row: ItemType) {
  formRef.value?.openEdit(row, { _aiPageKey: AI_PAGE_KEY });
}
```

```vue
<!-- 模板中使用包装函数，不直接调用 ref -->
<Button @click="onCreateItem">新建</Button>
<MenuItem @click="onEditItem(row)">编辑</MenuItem>
```

### 关键：`_aiPageKey` 传递链路

```
页面 openNew({ _aiPageKey }) / onEdit({ _aiPageKey })
  → useCrudDrawer.onOpenChange() 读取 data._aiPageKey
    → formStateTracker.open(aiPageKey, { formApi, fieldDescriptors, ... })
      → AI 可查询 get_form_state / fill_form / validate_form
```

---

## 五、contextExtras 替代手动注册 / contextExtras Replaces Manual Registration

**问题**：页面手动调用 `registerPageContext('admin/ai/agents', ...)` 会覆盖 `useCrudList` 自动注册的增强 context（含 `form_fields`、`form_is_open` 等），因为使用了相同的 pageKey。

**解决方案**：使用 `ai.contextExtras` 将自定义数据合并到自动注册中：

```typescript
// ✅ 正确：使用 contextExtras
ai: {
  contextExtras: () => ({
    published: stats.value.published,
    system: stats.value.system,
  }),
}

// ❌ 错误：手动注册覆盖自动注册
const cleanup = registerPageContext('admin/ai/agents', () => ({ ... }));
```

**何时仍需手动注册**：
- 页面不使用 `useCrudList`（如详情页、仪表板）
- 页面的 `ai` 配置为 `false` 或未提供

---

## 六、useCrudDrawer 自动集成 / useCrudDrawer Auto-Integration

`useCrudDrawer` 自动从 drawer 数据中读取 `_aiPageKey`，无需显式传入 `aiPageKey` 参数：

```typescript
// useCrudDrawer 内部逻辑（自动执行）：
onOpenChange(isOpen) {
  if (isOpen) {
    const data = drawerApi.getData();
    if (!aiPageKey && data?._aiPageKey) {
      aiPageKey = data._aiPageKey;  // 从 setData 传入的数据中读取
    }
    // ... 后续自动注册到 formStateTracker
  }
}
```

`useCrudList` 的 `onCreate()` 和 `onEdit()` 已自动在 `setData` 中加入 `_aiPageKey`。

---

## 七、标准操作列表 / Standard Operations

| 操作名 | 条件 | readonly | 说明 |
|--------|------|----------|------|
| `refresh_list` | 始终 | true | 刷新列表 |
| `search` | 有 `searchSchema` | true | 按字段搜索 |
| `clear_search` | 有 `searchSchema` | true | 清空搜索 |
| `create_record` | 有 `formSchema` + `formPopupApi` | false | 打开新建表单 |
| `edit_record` | 有 `formSchema` + `formPopupApi` | false | 打开编辑表单 |
| `navigate_to_detail` | 有 `detailRoute` | true | 跳转详情页 |
| `view_recycle_bin` | `hasRecycleBin=true` | true | 打开回收站 |
| `get_form_state` | 有 `formSchema` + `pageKey` | true | 获取表单状态 |
| `fill_form` | 有 `formSchema` + `pageKey` | false | 填充表单字段 |
| `validate_form` | 有 `formSchema` + `pageKey` | true | 触发表单校验 |
| `get_form_options` | 有远程下拉字段 | true | 获取远程选项 |

`extra` 操作可覆盖同名标准操作。

### 截图能力 / Screenshot Capability

- 平台默认提供只读页面操作 `capture_screenshot`
- `capture_screenshot` 只用于视觉/布局判断或文本上下文不足的场景；默认先用 `read_current_view` / `read_current_sections` / `get_page_context`
- 前端截图统一复用 `use-page-screenshot.ts`，必须走附件上传链路，禁止返回本地 base64 或只回传截图 URL 字符串假装“已看图”
- 若当前运行模型 `supports_vision=false`，后端必须拒绝 `capture_screenshot`
- 若截图成功，工具结果必须把图片附件作为**内部多模态输入**注入下一轮 LLM，而不是仅把附件元数据写进 tool 文本消息
- 内部截图消息属于运行时中间态，禁止写入会话持久化历史
- 专用工具展开允许把 `capture_screenshot` 展开为 `pageop_capture_screenshot`，与其它高频页面操作一致

---

## 八、CrudListAiOptions 完整配置 / Full CrudListAiOptions

```typescript
interface CrudListAiOptions {
  pageKey?: string;                              // 页面标识覆盖
  disabled?: string[];                           // 禁用的操作名
  searchSchema?: () => VbenFormSchema[];          // 搜索 schema
  formSchema?: (isEdit?: boolean) => VbenFormSchema[]; // 表单 schema
  detailRoute?: string;                          // 详情路由模板
  openRecycleBin?: () => void;                   // 打开回收站
  extra?: PageOperation[];                       // 额外操作
  entityName?: string;                           // 实体名称
  entityDescription?: string;                    // 业务描述
  formPurpose?: { create?: string; edit?: string }; // 表单用途
  contextExtras?: () => Record<string, unknown>;  // 额外 context 数据
}
```

---

## 九、后端 Prompt 对接 / Backend Prompt Integration

后端 `page_context_executor.py` 自动解析前端传来的增强 context：

- `entity_name` / `entity_description` — 用于 LLM 理解当前页面业务
- `form_fields` — 表单字段 schema（含 component/type/options/constraints）
- `form_is_open` — 表单是否已打开
- `form_purpose` — create/edit 用途描述
- `available_operations` — 可用操作列表（由 `enrichPageContextWithOperations` 注入）

后端迁移 `20260313_enhance_page_awareness_tool_descriptions.py` 更新了 `get_page_context` 和 `invoke_page_operation` 的 LLM 描述，包含详细的表单操作工作流指引。

---

## 十、检查清单 / Checklist

### 新页面接入

- [ ] 确认使用 formComponent 模式还是 ref 模式
- [ ] `ai` 配置中提供了 `formSchema`（至少）
- [ ] 无手动 `registerPageContext`（除非不用 `useCrudList`）
- [ ] ref 模式：所有 `openNew()`/`openEdit()` 传递 `{ _aiPageKey }`
- [ ] ref 模式：模板按钮使用包装函数而非直接 `ref?.openNew()`
- [ ] `entityName` 使用 `$t()` 国际化

### 常见错误

| 错误 | 后果 | 修复 |
|------|------|------|
| 手动 `registerPageContext` 与 `useCrudList` 的 `ai` 配置共存 | context 被覆盖，AI 看不到 `form_fields` | 删除手动注册，用 `contextExtras` |
| 未传 `formSchema` 到 `ai` 配置 | `create_record`/`fill_form` 等操作不会生成 | 补充 `formSchema` |
| ref 模式表单入口未传 `_aiPageKey` | `formStateTracker` 无法激活 | 所有入口补上 `{ _aiPageKey }` |
| `TrackableFormApi` 缺少 `setValues` | `fill_form` 需要 `as any` 绕过 | 接口已修复 |

---

## 十一、增强能力 / Enhanced Capabilities

以下功能扩展了基础页面感知，为 AI 提供更深层的页面理解和自主操作能力。

### 11.1 视觉状态感知（visual_state）

**文件**: `AIChatSlidePanel.vue` — `collectVisualState()` + `enrichPageContextWithOperations()`

每次发送消息时，`page_data` 自动注入 `visual_state`：

```typescript
{
  visual_state: {
    url: "/admin/ai/agents",           // 当前路由路径
    viewport: { w: 1920, h: 1080 },   // 视口尺寸
    scroll_y: 0,                       // 垂直滚动位置
    has_modal: true,                   // 是否有弹窗打开
    has_drawer: false,                 // 是否有抽屉打开
    open_overlays: [                   // 结构化弹窗信息（仅有弹窗时出现）
      { type: "modal", title: "新建智能体", visible: true }
    ]
  }
}
```

**后端展示**：`PageContextExecutor` 将 `visual_state` 转为 `Visual: URL: /admin/ai/agents | Overlays: modal(新建智能体)` 格式输出给 LLM。

### 11.2 弹窗/抽屉检测器（useModalDetector）

**文件**: `composables/use-modal-detector.ts`

通过 `MutationObserver` 自动检测 Ant Design 弹窗和抽屉的打开/关闭：

```typescript
interface ModalDetection {
  type: 'modal' | 'drawer';
  title: string;
  visible: boolean;
}

const { modalState, scan } = useModalDetector();
// modalState.value: ModalDetection[]
```

**规范**：
- 在 `AIChatSlidePanel.vue` 的 setup 中调用一次
- MutationObserver 使用 150ms 防抖（`DEBOUNCE_MS = 150`）
- 监听 `body` 的 `childList`、`subtree`、`attributes`（class/style）
- 自动在组件卸载时 disconnect

### 11.3 DOM 语义快照（降级机制）

**文件**: `components/business/ai-slide-panel/dom-semantic-scanner.ts`

当页面未调用 `registerPageContext()` 时，自动扫描 DOM 提取语义信息作为降级 context：

```typescript
interface DomSnapshot {
  page_title: string;                            // 页面标题
  breadcrumb: string[];                          // 面包屑
  tables: Array<{ columns: string[]; row_count: number }>; // 表格结构
  forms: Array<{ labels: string[] }>;            // 表单标签（不含值）
  action_buttons: string[];                      // 可操作按钮文本
  tabs: Array<{ label: string; active: boolean }>; // Tab 标签
}
```

**安全约束**：
- 不提取 `input` / `textarea` 的值（防止敏感数据泄露）
- 总输出限制 2KB（`MAX_OUTPUT_BYTES = 2048`）
- 扫描时间预算 ~50ms（内部 `performance.now()` 检查）

**降级逻辑**（`page-context-registry.ts`）：
- `resolvePageContext(key)` 无匹配 resolver → 调用 `buildDomFallbackContext(key)`
- 无 key 且所有 resolver 返回 null → 调用 `buildDomFallbackContext()`（从 `window.location.pathname` 推断 key）
- 返回的 `page_data.source = 'dom_snapshot'`，用于后端区分来源

### 11.4 fill_form 读回验证（field_feedback）

**文件**: `composables/use-ai-operations.ts` — `buildFillFormFeedback()`

`fill_form` 操作执行 `setValues` 后，自动读回表单实际值并与请求值逐字段对比：

```typescript
// 返回结构
{
  success: true,
  message: "Filled 5 field(s), 1 may need attention",
  data: {
    filled: ["name", "description", "provider_id"],
    skipped: ["unknown_field"],
    field_feedback: {
      name:        { requested: "Test", actual: "Test", match: true },
      provider_id: { requested: "OpenAI", actual: null, match: false }  // Select 传了 label 而非 value
    }
  }
}
```

**用途**：
- AI 据此判断哪些字段需要重试
- 检测 Select 字段传 label 而非 value 的常见错误
- `buildFillFormFeedback` 内部 try-catch 兜底：formApi 未就绪时返回乐观反馈

### 11.5 操作结果上下文对比（context_diff）

**文件**: `components/business/ai-slide-panel/page-operation-registry.ts` — `executePageOperation()`

每次执行操作时，自动记录操作前后的状态变化：

```typescript
// 操作结果中自动附加
{
  data: {
    context_diff: {
      form_opened: true,    // 表单从关闭变为打开
      form_closed: false,
      modal_opened: false,
      modal_closed: false,
      drawer_opened: true,  // 抽屉从关闭变为打开
      drawer_closed: false,
    }
  }
}
```

**后端利用**：`PageOperationExecutor` 根据 `context_diff.form_opened` 自动追加 Agent Loop 指引。

### 11.6 列表数据摘要（list_summary）

**文件**: `composables/use-crud-list.ts` — `registerPageContext` resolver

`useCrudList` 自动在 `page_data` 中包含当前页数据摘要：

```typescript
{
  list_summary: {
    total_rows: 150,        // 总记录数
    page_size: 20,          // 每页条数
    current_page: 1,        // 当前页码
    sample_rows: [          // 前 5 行数据摘要
      { name: "GPT-4o", provider: "OpenAI", status: "active" },
      // ... 最多 5 行，每行 6 字段，每值截断 50 字符
    ]
  }
}
```

**后端展示**：`PageContextExecutor` 输出 `List: 150 total rows, 5 sample rows shown` 并展示前 3 行。

### 11.7 Agent Loop（多步自主执行）

Agent Loop 允许 AI 在用户一次请求内自主执行多步操作，无需用户逐步确认。

#### 后端引导

**文件**: `backend/app/ai/tools/executors/page_context_executor.py`

LLM 收到的 `get_page_context` 结果中包含工作流指引：

```
## Agent Loop — Form Operation Workflow:
Execute ALL steps in sequence WITHOUT waiting for user input between steps:
1. Call create_record/edit_record to open the form
2. Immediately call get_form_state to inspect current values and schema
3. Immediately call fill_form to fill ALL fields with intelligent values
4. Check fill_form result field_feedback for mismatches, retry if needed
5. User reviews the pre-filled form and submits manually
IMPORTANT: Do NOT stop after step 1. Continue all steps in this single turn.
```

**文件**: `backend/app/ai/tools/executors/page_operation_executor.py`

操作成功后，根据 `context_diff` 追加下一步指引：
- `form_opened` → `[Agent Loop] Form opened. Next: call get_form_state then fill_form`
- `form_closed` → `[Agent Loop] Form closed. Call refresh_list to see updated data.`

### 11.8 专用 Page Tools（pageop_*）

**文件**: `backend/app/ai/tools/page_tool_expander.py`、`useEditorPageOps.ts`、`page-context-registry.ts`、`page-operation-registry.ts`

当 `page_context.available_operations` 含可展开页面操作时，后端自动展开专用动态 tools。范围不再只限富文本编辑器，也包含高频通用页面操作。

**当前展开范围**：
- 编辑器 / 文档类：`get_editor_html`、`get_editor_text`、`replace_section`、`replace_content`、`insert_content`、`append_content`、`update_title`、`insert_table`、`manage_link`
- 通用页面类：`search`、`clear_search`、`read_visible_rows`、`read_row_detail`、`refresh_list`、`get_form_state`、`fill_form`、`validate_form`、`get_form_options`、`create_record`、`edit_record`、`submit_form`、`go_to_page`、`next_page`、`prev_page`、`set_page_size`

对应展开结果示例：`pageop_search`、`pageop_read_visible_rows`、`pageop_fill_form`、`pageop_get_editor_html`、`pageop_replace_section` 等。

**tool-first 原则**：有 pageop_* 时，模型应**优先直调专用 tools**，不要用 `invoke_page_operation` 猜测参数；仅在 pageop_* 不可用时才回退到 `invoke_page_operation`。

**content_format 契约**：`replace_content` / `replace_section` / `insert_content` 的参数为 `{ content, content_format?: 'html'|'markdown' }`，默认 `content_format='html'`；传 `markdown` 时自动转为 HTML 插入。

**规则**：
- 禁止向用户展示 HTML、JSON、tool 参数或调用示例；工具仅用于内部执行，完成后只返回自然语言结果
- `replace_section` 失败时返回细粒度 `error_type`：`target_not_found`、`non_unique_match`、`invalid_html`
- `get_editor_html` 输出提示：优先使用短且唯一的 HTML 片段作为 `old_html`
- 前端页面操作通道必须按 `invoke_id` 做幂等保护；重复事件应复用首个执行结果，禁止重复执行或重复弹确认
- 前端页面操作通道必须校验 `event.page_key === 当前活动页面 page_key`；不匹配时返回 `page_key_mismatch`，禁止在错误页面执行操作
- 连续 3 次 pageop_*/invoke 失败（含 JSON parse error）后中止 tool loop，避免道歉循环
- NovusDoc DocumentEditor 使用 `registerPageContextExtras` 合并上下文，`appendPageOperations` 追加文档操作（save_document、update_title 等），不覆盖平台 editor ops

#### 前端链式确认

**文件**: `composables/use-page-operation-channel.ts`

用户确认 `create_record` / `edit_record` 后，60 秒内同一 `page_key` 的 `fill_form` 操作可自动批准；仅限当前页面会话，切页/离房/断线必须清空状态：

```typescript
const CHAIN_CONFIRM_TTL_MS = 60_000;
const CHAIN_TRIGGER_OPS = new Set(['create_record', 'edit_record']);
const CHAIN_AUTO_OPS = new Set(['fill_form']);
```

流程：
1. 用户说"帮我创建一个测试套餐"
2. AI 调用 `create_record` → 前端弹出确认 → 用户确认 → `markChainConfirmed(pageKey)`
3. AI 调用 `get_form_state`（readonly，自动执行）
4. AI 调用 `fill_form` → `isChainConfirmed(pageKey)` = true → 自动执行，无需确认
5. AI 返回预填结果，用户检查并提交

**安全约束**：
- 确认有效期 60 秒（`CHAIN_CONFIRM_TTL_MS`）
- 仅 `fill_form` 可自动批准，其他写操作仍需确认
- readonly 操作（如 `get_form_state`、`validate_form`）始终自动执行
- 同一个 `invoke_id` 的重复下发必须直接回放缓存结果，不能重复打开确认卡片或重复执行页面动作
- 页面会话切换、`leavePageSessionRoom()`、Socket 断开连接时必须执行 `clearChainConfirmed()`，禁止跨会话残留自动批准状态
- 若操作事件携带的 `page_key` 与当前活动页不一致，前端返回 `page_key_mismatch`，不执行任何页面动作
- 既有的 `MAX_TOOL_CALL_ROUNDS = 10`（后端）限制了最大循环次数

### 11.9 page_data 大小保护

**文件**: `AIChatSlidePanel.vue` — `truncateFormFields()` + `guardPageDataSize()`

`enrichPageContextWithOperations` 在最终发送前执行两层保护：

1. **form_fields 截断**：超过 20 个字段时只保留前 20 个，附加 `_truncated` 字段
2. **总大小保护**（7KB 前端预算，后端限制 8KB）：
   - 第一步：减少 `list_summary.sample_rows` 到 2 行
   - 第二步：清空 `sample_rows`
   - 第三步：分阶段精简 `available_operations`，先保留描述与参数，再逐步去掉参数、描述，最后整块移除
   - 第四步：截断 `document_body_text`（NovusDoc / DocumentEditor）到 `2400 → 1600 → 800 → 400` bytes
   - 第五步：分阶段压缩 `form_fields`（保留约束/选项 → 去掉选项 → 去掉约束），只有最后才整块移除
3. **document_body_text 源头限制**：`useEditorPageOps` 与 `DocumentEditor` 中 `DOCUMENT_BODY_EXCERPT_LEN = 800`（≈2.4KB UTF-8），避免超 8KB

---

## 十二、已知限制与缓解措施 / Known Limitations & Mitigations

### 12.1 L1: page_data 8KB 限制

- **缓解方式**：见 11.9 page_data 大小保护（前端 7KB 预算 + 后端 8KB 校验）

### 12.2 L2: 多 resolver 冲突

**文件**: `page-context-registry.ts` — `resolvePageContext()`

无 key 调用时，先用 `window.location.pathname` 推断 key 做精确匹配，命中则直接返回，避免遍历全部 resolver 取最后一个的不确定行为。

解析优先级：
1. 路由匹配：`normalizePageKey(pathname)` → 精确 registry 查询
2. 遍历所有 resolver，返回最后非空结果
3. DOM 语义快照降级

### 12.3 L3: formStateTracker pageKey 断裂

**文件**: `composables/use-form-state-tracker.ts`

当 `_aiPageKey` 传递断裂导致精确 key 无匹配时，以下方法提供 fallback：
- `isOpenWithFallback(pageKey)` — 精确匹配失败时，若全局仅一个表单被追踪，视为目标
- `getStateWithFallback(pageKey)` — 同上，返回唯一追踪表单的状态
- `getFormApi(pageKey)` — 精确匹配失败时，若仅一个表单，返回其 formApi
- `getFieldDescriptors(pageKey)` — 同上模式，返回实时 fieldDescriptors

使用场景：`use-ai-operations.ts` 中 `fill_form`、`get_form_state`、`validate_form` 均使用 fallback 版本。

**限制**：当多个表单同时被追踪（如嵌套表单场景），fallback 不生效，仍依赖精确 key。

### 12.4 L5: 操作确认超时保护

**文件**: `composables/use-page-operation-channel.ts` — `confirmAndExecute()`

- `CONFIRM_TIMEOUT_MS = 60_000`（60 秒超时）
- 使用 `Promise.race([confirmPromise, timeoutPromise])` 竞争
- 超时哨兵值为 `null`，与用户取消（`false`）可区分
- 超时后自动调用 `resolvePageOp(invokeId, false)` 清理 pending 确认卡片

### 12.5 L7: form_fields 动态更新

**文件**: `AIChatSlidePanel.vue` — `enrichPageContextWithOperations()`

`formStateTracker` 在每次 drawer 打开时刷新 `fieldDescriptors`。
`enrichPageContextWithOperations` 在构建 `page_data` 时检查：
- 若 `formStateTracker.isOpenWithFallback(page_key)` 为 true
- 且 `getFieldDescriptors()` 返回非空描述
- 则用实时 `fieldDescriptors` 替换注册时固定的 `form_fields`

这确保了动态 schema（条件字段、权限变化）能被 AI 感知。

### 12.6 L4 / L6 说明

- **L4 (page_session_id 单点)**：前端仍采用 SPA 当前活跃 `page_session_id` 单例，但后端 active-session fallback 已改为“唯一候选才恢复”；同用户同页面存在多个活跃标签页时返回 `None`，避免跨 tab 猜测
- **L6 (工具不被 optimizer 过滤)**：`get_page_context` / `invoke_page_operation` 列入 `_PROTECTED_TOOL_NAMES` 白名单属于有意设计

---

## 十三、增强能力核心文件 / Enhanced Capability Core Files

| 文件 | 职责 |
|------|------|
| `composables/use-modal-detector.ts` | MutationObserver 弹窗/抽屉检测 |
| `composables/use-form-state-tracker.ts` | 表单状态追踪 + pageKey fallback |
| `components/business/ai-slide-panel/dom-semantic-scanner.ts` | DOM 语义快照（降级机制） |
| `composables/use-page-operation-channel.ts` | WebSocket 操作通道 + page_key 校验 + Agent Loop 链式确认 + 超时保护 |
| `backend/app/ai/tools/page_tool_expander.py` | 将编辑器与高频通用页面操作展开为专用 `pageop_*` tools |
| `backend/app/ai/tools/executors/page_context_executor.py` | 后端 page_context 展示（含 visual_state / list_summary / Agent Loop 指引） |
| `backend/app/ai/tools/executors/page_operation_executor.py` | 后端操作执行（含 Agent Loop 下一步指引） |
