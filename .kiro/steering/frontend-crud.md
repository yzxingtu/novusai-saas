---
inclusion: fileMatch
fileMatchPattern: 'frontend/**/*.{ts,vue}'
---

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

export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    { field: 'name', title: '名称' },
    { field: 'status', title: '状态' },
  ];
}

export function useGridFormSchema() {
  return [
    searchInput('name', '名称'),
    statusSelect(),
  ];
}

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
  fields: ['name', 'expires_at', 'remark'],
  onSuccess: () => emits('success'),
});
```

### Step 4: 添加路由和 i18n

- 路由：`router/routes/{endpoint}/`
- 翻译：`locales/langs/zh-CN/{endpoint}/`

---

## 权限控制

```vue
<Button v-access:code="['notice:create']">新增</Button>
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

- key 前缀 = 文件路径：`zh-CN/admin/system.json` → `admin.system.*`
- 使用：`$t('admin.system.role.title')` 或 `import { $t } from '#/locales'`
- JSON 内不重复嵌套路径名

---

## 图标

- 优先 Lucide：`<IconifyIcon icon="lucide:user" class="size-4" />`
- Tailwind 类：`<span class="icon-[lucide--user] size-5" />`（用 `--` 代替 `:`）

---

## HTTP 请求

```typescript
import { requestClient } from '#/utils/request';
await requestClient.get('/admin/users');
await requestClient.post('/admin/users', data);
```

Token 按 URL 前缀自动选择。

---

## 命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 目录 / TS | kebab-case | `admin-user/` |
| Vue 组件 | PascalCase | `UserList.vue` |
| API 函数 | `{action}{Resource}Api` | `adminLoginApi` |
| Store | `use{Endpoint}AuthStore` | `useAdminAuthStore` |
| Composable | `use{Name}` | `useCrudPage` |

---

## 样式 Token

| Token | 用途 |
|-------|------|
| `text-foreground` | 主要文字 |
| `text-muted-foreground` | 次要文字 |
| `bg-primary/10` | 主色标签背景 |
| `bg-success/10` | 启用状态 |
| `bg-destructive/10` | 禁用状态 |

---

## 通用下拉 (select)

```typescript
import { select } from '#/adapter/form';

// 远程下拉
select('plan_id', '套餐', { api: getTenantPlanSelectApi, extraField: 'code' });

// 静态下拉
select('gender', '性别', { options: [{ label: '男', value: 1 }, { label: '女', value: 2 }] });
```

业务预设定义在业务模块 `data.ts`，不从 adapter 导出。

---

## useCrudDrawer 独立使用

```typescript
const { Drawer, openNew, openEdit } = useCrudDrawer<AdminInfo>({
  formApi,
  schema: (isEdit) => useFormSchema(isEdit),
  defaults: getFormDefaults,
  apiPath: '/admin/admins',
  detailApi: api.getAdminDetailApi,
  transform: (values, isEdit) => ({ ... }),
  toFormValues: (data) => ({ ... }),
  onSuccess: () => emits('success'),
});
```

---

## 拖拽排序

```typescript
import { useAutoTableDragSort, dragColumn } from '#/adapter/vxe-table';

// data.ts 添加 dragColumn 到列定义第一列
// index.vue 启用拖拽
useAutoTableDragSort(() => gridApi.grid, {
  onBatchUpdate: async (ids) => { await api.reorderApi(ids); },
  keyField: 'id',
});
```

---

## 列表 UI 设计规范

- 拒绝纯文字表格，拥抱视觉层次
- 编码/ID：`font-mono text-muted-foreground` + 复制图标
- 名称：图标容器/首字头像 + 双行文字
- 状态：`rounded-lg bg-{color}/10 text-{color}`
- 日期：相对时间 + Tooltip 完整时间
- 空值：`text-muted-foreground` + i18n `admin.common.notSet`

---

## 代码检查清单

- [ ] 无 `any` 类型
- [ ] 无 `console.log()`
- [ ] 无中文硬编码（全部 `$t()`）
- [ ] 搜索/表单用辅助函数生成
- [ ] 业务预设在 `data.ts` 定义，不在 adapter
- [ ] 无跨端导入
- [ ] i18n JSON key 无重复、路径正确
- [ ] 中英文翻译齐全
- [ ] Props 用 `defineProps<T>()`
