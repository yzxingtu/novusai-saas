# 前端 CRUD 开发完整指南

## 架构分层

```
views/{endpoint}/     页面组件（按端分离）
composables/          组合式函数
adapter/vxe-table/    声明式表格
store/{endpoint}/     状态管理（按端分离）
api/{endpoint}/       API 调用（按端分离）
router/               路由 + 权限
utils/                纯工具函数
```

依赖方向：`views → composables → store/api → utils`

端隔离：admin → 仅导入 `api/admin`、`store/admin`

---

## 新增 CRUD 页面步骤

### Step 1: data.ts — 定义列、搜索、表单 Schema

```typescript
import { searchInput, statusSelect, inputField, dateField, textareaField } from '#/adapter/form';
import { planSelect } from './data';  // 业务预设在本模块定义

// 列定义
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    { field: 'name', title: '名称' },
    { field: 'status', title: '状态' },
  ];
}

// 搜索 Schema（必须用辅助函数）
export function useGridFormSchema() {
  return [
    searchInput('name', '名称'),       // → filter[name][ilike]
    statusSelect(),                     // → filter[is_active]
  ];
}

// 表单 Schema（必须用辅助函数）
export function useFormSchema(isEdit: boolean) {
  return [
    inputField('name', '名称', { required: true }),
    dateField('expires_at', '到期时间'),
    textareaField('remark', '备注'),
  ];
}
```

### Step 2: list.vue — 使用 useCrudPage

```typescript
import { adminApi as admin } from '#/api';
import { useCrudPage } from '#/adapter/vxe-table';
import Form from './modules/form.vue';

const { Grid, FormDrawer, onCreate, onRefresh } = useCrudPage<ItemInfo>({
  api: {
    list: admin.getItemListApi,
    resource: '/admin/items',
    toggles: { is_active: admin.toggleItemStatusApi },
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  i18nPrefix: 'admin.system.item',
  nameField: 'name',
});
```

### Step 3: form.vue — 使用 useCrudDrawer

```typescript
import { useCrudDrawer } from '#/composables';
import { useFormSchema } from '../data';

const { Drawer, isEdit } = useCrudDrawer<ItemInfo>({
  formApi,
  schema: useFormSchema,
  fields: ['name', 'expires_at', 'remark'],  // 自动 camelCase ↔ snake_case
  onSuccess: () => emits('success'),
});
```

### Step 4: 添加路由和 i18n

- 路由：`router/routes/{endpoint}/`
- 翻译：`locales/langs/zh-CN/{endpoint}/`

---

## 自定义布局页面（useCrudList）

当页面不适合表格（如卡片网格、Master-Detail、配置面板）时，使用 `useCrudList`。

### 模式选择指南

| 场景 | Composable | 说明 |
|------|-----------|------|
| 数据密集型列表（日志、用户、配置项） | `useCrudPage` | 返回 `Grid` + `FormDrawer`，自动表格渲染 |
| 卡片网格（知识库、智能体、插件） | `useCrudList` | 返回响应式数据，自定义卡片模板 |
| Master-Detail（技能包：左列表+右详情） | `useCrudList` × 2 | 左侧用 `selectable: true`，右侧过滤 `selectedId` |
| 配置面板（域名、配额） | `useCrudList` | 返回列表数据，自定义 inline 编辑 |

### useCrudList API 参考

```typescript
import { useCrudList } from '#/composables';

const {
  // 响应式数据
  list,              // Ref<T[]> — 当前列表
  filteredList,      // ComputedRef<T[]> — 客户端过滤后的列表
  total,             // Ref<number> — 总条数
  loading,           // Ref<boolean>
  currentPage,       // Ref<number>
  pageSize,          // Ref<number>
  searchKeyword,     // Ref<string> — 通用搜索关键词
  searchParams,      // Ref<Record<string, unknown>>

  // 选中状态（Master-Detail）
  selectedId,        // Ref<number | string | null>
  selectedItem,      // ComputedRef<T | null>

  // 组件
  FormDrawer,        // Component | null — 表单抽屉/弹窗

  // CRUD 操作
  loadList,          // () => Promise<void>
  reload,            // () => Promise<void> — 回到第一页
  onCreate,          // () => void
  onEdit,            // (row: T) => void
  onDelete,          // (row: T) => Promise<void> — 含防抖 + 依赖阻止
  onToggleStatus,    // (val: boolean, row: T) => Promise<boolean>
  onSelect,          // (row: T) => void — 选中一条记录

  // 搜索/分页
  onSearch,          // (params?: Record<string, unknown>) => void
  onPageChange,      // (page: number) => void

  // 回收站
  openRecycleBin,    // () => void
  recycleBinCount,   // Ref<number>

  // 辅助
  handleMenuAction,  // (code: string, row: T) => void — 菜单操作分发（含 'edit'/'delete'）
} = useCrudList<ItemType>({
  // === 必填 ===
  api: {
    list: getListApi,                    // 列表 API（支持返回 {items, total} 或裸数组）
    resource: '/admin/ai/knowledge-bases', // DELETE 路径前缀
    delete: deleteApi,                   // 可选：自定义删除 API
    toggles: { is_active: toggleApi },   // 可选：快捷开关
  },
  i18nPrefix: 'admin.knowledgeBase',     // i18n 前缀

  // === 可选 ===
  formComponent: Form,                   // 表单组件（不传则无 FormDrawer/onCreate/onEdit）
  formDefaults: getFormDefaults,         // 新建默认值
  nameField: 'name',                     // 显示名称字段（删除确认用）
  defaultSort: '-created_at',            // 排序
  pageSize: 12,                          // 每页条数
  pager: true,                           // 是否分页
  recycleBin: true,                      // 启用回收站
  createPermission: 'kb:create',         // 创建权限码

  // === 高级 ===
  keyField: 'feature_code',              // 自定义主键字段（默认 'id'），支持无 id 的类型
  responseAdapter: (data) => ({ ... }),  // 非标准 API 响应适配
  autoRefreshInterval: 30000,            // 自动刷新（毫秒），如健康监控 30s 轮询
  selectable: true,                      // 启用选中状态
  defaultSelect: 'first',               // 加载后自动选中第一条
  clientFilter: (item, kw) => ...,       // 客户端过滤函数
  defaultFilters: { scope: 'admin' },    // 固定过滤条件
  customActions: { detail: (row) => ... }, // 自定义操作
});
```

### 示例 1：卡片网格页面（知识库）

```vue
<script setup>
const {
  list, total, loading, currentPage, pageSize, searchKeyword,
  FormDrawer, loadList, onCreate, onSearch, onPageChange, handleMenuAction,
} = useCrudList<KBItem>({
  api: { list: getListApi, delete: deleteApi, resource: '/admin/ai/knowledge-bases' },
  formComponent: Form,
  i18nPrefix: 'admin.knowledgeBase',
  pageSize: 12,
  recycleBin: true,
});
</script>

<template>
  <Page>
    <FormDrawer @success="loadList" />
    <RecycleBinDrawer ref="recycleBinRef" resource="/admin/ai/knowledge-bases" @restored="loadList" />
    <!-- 搜索栏 + 创建按钮 -->
    <div class="flex items-center gap-3">
      <Input v-model:value="searchKeyword" @press-enter="doSearch" />
      <Button type="primary" @click="onCreate">{{ $t('create') }}</Button>
    </div>
    <!-- 卡片网格 -->
    <div class="grid grid-cols-3 gap-4">
      <div v-for="item in list" :key="item.id" class="rounded-xl border bg-card p-4">
        <h4>{{ item.name }}</h4>
        <!-- Dropdown 菜单用 handleMenuAction('edit', item) / handleMenuAction('delete', item) -->
      </div>
    </div>
    <Pagination :current="currentPage" :total="total" :page-size="pageSize" @change="onPageChange" />
  </Page>
</template>
```

### 示例 2：Master-Detail（技能包）

```vue
<script setup>
// 左侧：包列表（启用选中）
const { list: packages, selectedId, selectedItem, onSelect, loadList } =
  useCrudList<PackageInfo>({
    api: { list: getPackageListApi, resource: '/admin/ai/skill-packages' },
    i18nPrefix: 'admin.ai.skillPackage',
    selectable: true,
    defaultSelect: 'first',
    clientFilter: (item, kw) => item.name.toLowerCase().includes(kw),
  });

// 右侧：技能列表（过滤 selectedId）
const { list: skills, loadList: loadSkills } = useCrudList<SkillInfo>({
  api: { list: getSkillListApi, resource: '/admin/ai/skills' },
  i18nPrefix: 'admin.ai.skill',
  defaultFilters: computed(() => ({ 'filter[package_id][eq]': selectedId.value })),
});

watch(selectedId, () => loadSkills());
</script>
```

### 示例 3：AgentForm ref 模式

当表单组件提供 `openNew()` / `openEdit()` 方法时，不使用 `FormDrawer`：

```vue
<script setup>
const { list, loadList, handleMenuAction } = useCrudList<AgentInfo>({
  api: { list: getListApi, delete: deleteApi, resource: '/admin/ai/agents' },
  i18nPrefix: 'admin.ai.agent',
  customActions: { edit: (row) => formRef.value?.openEdit(row) },
});

const formRef = ref<InstanceType<typeof AgentForm>>();
</script>

<template>
  <AgentForm ref="formRef" @success="loadList" />
  <RecycleBinDrawer ref="recycleBinRef" resource="/admin/ai/agents" @restored="loadList" />
  <!-- 卡片模板，菜单用 handleMenuAction -->
</template>
```

### 回收站与依赖阻止

**回收站**：页面自行渲染 `RecycleBinDrawer`，通过 ref 管理 open/count：

```vue
<script setup>
import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
const recycleBinRef = ref<{ open: () => void; deletedCount: number } | null>(null);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() { recycleBinRef.value?.open(); }
</script>

<template>
  <RecycleBinDrawer ref="recycleBinRef" resource="/admin/ai/xxx" @restored="loadList" />
</template>
```

**依赖阻止**：`useCrudList` 与 `useCrudPage` 已统一接入共享 `DependencyBlockModal` helper；删除遇到 4221 时会自动弹出统一依赖详情弹窗，无需页面额外拼装第二套 `Modal.warning`。

---

## 权限控制

```vue
<!-- 模板指令 -->
<Button v-access:code="['notice:create']">新增</Button>

<!-- 操作列（自动鉴权） -->
options: ['edit', 'delete']  // 自动检查 {resource}:update / {resource}:delete
```

编程式：

```typescript
import { useAccess } from '#/utils/access';
const { hasAccessByCodes, isSuperAdmin } = useAccess();
```

---

## 搜索（JSON:API）

| 操作符 | 用途 | fieldName 示例 |
|--------|------|----------------|
| `ilike` | 模糊匹配 | `filter[name][ilike]` |
| `eq` / 无 | 精确匹配 | `filter[is_active]` |
| `gte/lte` | 范围 | `filter[created_at][gte]` |
| `in` | 多值 | `filter[status][in]` |

---

## 国际化

- 翻译文件 key 前缀 = 文件路径：`zh-CN/admin/system.json` → `admin.system.*`
- 使用：`$t('admin.system.role.title')` 或 `import { $t } from '#/locales'`
- JSON 内不重复嵌套路径名
- 避免同一 JSON 中重复 key

---

## 图标

- 优先 Lucide：`<IconifyIcon icon="lucide:user" class="size-4" />`
- Tailwind 类：`<span class="icon-[lucide--user] size-5" />`（用 `--` 代替 `:`）
- 自定义 SVG：放 `packages/icons/src/svg/icons/`，用 `svg:icon-name`

---

## HTTP 请求

```typescript
import { requestClient } from '#/utils/request';

await requestClient.get('/admin/users');
await requestClient.post('/admin/users', data);
await requestClient.put('/admin/users/1', data);
await requestClient.delete('/admin/users/1');
```

Token 按 URL 前缀自动选择：`/admin/*` → admin，`/tenant/*` → tenant，`/api/user/*` → user

---

## 命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 目录 / TS | kebab-case | `admin-user/` |
| Vue 组件 | PascalCase | `UserList.vue` |
| API 函数 | `{action}{Resource}Api` | `adminLoginApi` |
| Store | `use{Name}Store` | `useMultiAuthStore` |
| Composable | `use{Name}` | `useCrudPage` |

---

## 样式 Token

| Token | 用途 |
|-------|------|
| `text-foreground` | 主要文字 |
| `text-muted-foreground` | 次要文字 |
| `text-primary` | 链接、强调 |
| `bg-primary/10` | 主色标签背景 |
| `bg-success/10` | 启用状态 |
| `bg-destructive/10` | 禁用状态 |
| `bg-warning/10` | 警告状态 |
