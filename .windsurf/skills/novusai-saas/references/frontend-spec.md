# 前端开发手册

> 基于 Vben Admin 5.x + Vue 3 + TypeScript + Ant Design Vue

---

## 一、架构概览

### 多端分离

```
admin  → /admin/*    平台管理端
tenant → /tenant/*   租户管理端
user   → /*          用户端
```

### 核心分层

```
┌─────────────────────────────────────────────────┐
│  views/{endpoint}/     页面组件（按端分离）        │
├─────────────────────────────────────────────────┤
│  composables/          组合式函数                 │
│  adapter/vxe-table/    声明式表格                 │
├─────────────────────────────────────────────────┤
│  store/{endpoint}/     状态管理（按端分离）        │
│  api/{endpoint}/       API 调用（按端分离）        │
├─────────────────────────────────────────────────┤
│  router/               路由 + 权限               │
│  directives/           指令（v-access）          │
│  utils/                工具函数                  │
└─────────────────────────────────────────────────┘
```

---

## 二、耦合关系（重要）

### ✅ 正确的依赖方向

```
views → composables → store/api
views → adapter/vxe-table → api
router/access → api/menu → store/accessStore
```

### ❌ 禁止的依赖

```
api 不依赖 views
store 不依赖 views
utils 不依赖 store/api（纯函数）
adapter 不依赖具体业务代码
```

### 各层职责

| 层级           | 职责               | 可依赖            |
| -------------- | ------------------ | ----------------- |
| `views/`       | UI 展示、用户交互  | 所有层            |
| `composables/` | 可复用逻辑（Hook） | store, api, utils |
| `adapter/`     | 框架适配封装       | utils, types      |
| `store/`       | 状态管理           | api, utils        |
| `api/`         | 后端通信           | utils, types      |
| `utils/`       | 纯工具函数         | 无                |
| `router/`      | 路由 + 权限守卫    | store, api        |

### 端隔离原则

```
admin/   → 仅导入 api/admin, store/admin
tenant/  → 仅导入 api/tenant, store/tenant
_shared/ → 导入 api/shared, store/shared
```

---

## 三、CRUD 列表页开发 (Schema Driven)

### 核心原则

1. **Zero Boilerplate**：禁止手写重复的 `componentProps` 配置
2. **Schema Driven**：所有表单配置必须通过 `#/adapter/form` 导出的辅助函数生成
3. **Auto Mapping**：表单组件必须使用 `fields` 选项，自动处理 camelCase ↔ snake_case 映射
4. **业务与通用分离**：`adapter/form` 仅包含通用辅助函数，业务预设（如 `planSelect`）必须定义在业务模块内，避免 adapter 依赖具体业务 API

### 核心代码（list.vue）

```typescript
import { adminApi as admin } from '#/api';
import { useCrudPage } from '#/adapter/vxe-table';
import Form from './modules/form.vue';

const { Grid, FormDrawer, onCreate, onRefresh } = useCrudPage<AdminInfo>({
  api: {
    list: admin.getAdminListApi,
    resource: '/admin/admins',
    toggles: { is_active: admin.toggleAdminStatusApi },
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(), // 使用辅助函数生成的 Schema
  formComponent: Form,
  i18nPrefix: 'admin.system.admin',
  nameField: 'username',
});
```

### 搜索表单 (data.ts)

**禁止**手写原始 Schema 对象。必须使用 `searchInput`, `statusSelect` 等辅助函数。

```typescript
import { searchInput, statusSelect } from '#/adapter/form';
// ⚠️ 业务预设必须在当前模块内定义，不从 adapter 导入
import { planSelect } from './data';

export function useGridFormSchema() {
  return [
    searchInput('code', '编码'), // => fieldName: 'filter[code][ilike]'
    searchInput('name', '名称'), // => fieldName: 'filter[name][ilike]'
    statusSelect(), // => fieldName: 'filter[is_active]'
    planSelect({ search: true }), // => fieldName: 'filter[plan_id]'
  ];
}
```

### 编辑表单 (data.ts)

使用 `inputField`, `dateField` 等函数。

```typescript
import { inputField, dateField, textareaField } from '#/adapter/form';
import { planSelect } from './data';

export function useFormSchema(isEdit: boolean) {
  return [
    inputField('username', '用户名', { required: true }),
    planSelect({ required: true }),
    dateField('expires_at', '过期时间'),
    textareaField('remark', '备注'),
  ];
}
```

### 表单组件 (form.vue)

**核心规范**：直接使用 `fields` 选项，自动处理所有映射。

```typescript
import { useCrudDrawer } from '#/composables';
import { useFormSchema } from '../data';

const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
  formApi,
  schema: useFormSchema,
  // ✅ 标准写法：仅提供字段列表，框架自动处理 camelCase ↔ snake_case 映射
  fields: ['username', 'plan_id', 'expires_at', 'remark'],
  onSuccess: () => emits('success'),
});
```

### 批量选择（Checkbox）

```typescript
import { checkboxColumn, getSelectedRows, getSelectedIds, clearSelection } from '#/adapter/vxe-table';

// data.ts - 添加复选框列
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    checkboxColumn,  // 复选框列（放第一列）
    { field: 'name', title: '名称' },
  ];
}

// index.vue - 获取选中数据
const rows = getSelectedRows(gridApi.grid);
const ids = getSelectedIds(gridApi.grid, 'id');
clearSelection(gridApi.grid);
```

---

## 四、权限控制

### 权限码来源

菜单接口 `permissions` 字段 → `router/access.ts` 提取 → `accessStore.setAccessCodes()`

### 使用方式

```vue
<!-- 模板中 -->
<Button v-access:code="['admin_user:create']">新增</Button>

<!-- 表格操作列（自动鉴权） -->
options: ['edit', 'delete'] // 自动检查 {resource}:update/delete
```

### 权限码格式

`{resource}:{action}` → `admin_user:create`, `tenant:impersonate`

### CRUD 操作自动映射

| 按钮 code | 自动计算的权限码 |
|-----------|------------------|
| `edit` | `{resource}:update` |
| `delete` | `{resource}:delete` |
| `create` | `{resource}:create` |
| `view` / `detail` | `{resource}:read` |

### 超级管理员

拥有 `*` 权限码的用户自动拥有所有权限：

```typescript
if (userCodes.includes('*')) return true;
```

### useAccess Hook

```typescript
import { useAccess } from '#/utils/access';

const { hasAccessByCodes, isSuperAdmin } = useAccess();

if (hasAccessByCodes(['admin_user:delete'])) {
  // 有删除权限
}
```

---

## 五、搜索筛选（JSON:API）

### 字段命名

```typescript
// 搜索表单 fieldName 直接使用 JSON:API 格式
fieldName: 'filter[username][ilike]'; // 模糊搜索
fieldName: 'filter[is_active]'; // 精确匹配
fieldName: 'filter[created_at][gte]'; // 大于等于
```

### 常用操作符

| 操作符    | 用途                   |
| --------- | ---------------------- |
| `ilike`   | 模糊匹配（忽略大小写） |
| `eq` / 无 | 精确匹配               |
| `gte/lte` | 范围（日期、数字）     |
| `in`      | 多值匹配               |

---

## 六、国际化

### Key 计算规则

文件路径决定 key 前缀：

```
zh-CN/admin/system.json → admin.system.*
```

### 使用方式

```typescript
import { $t } from '#/locales';
const title = $t('admin.system.role.title');
```

### 注意

**子目录 JSON 不要重复嵌套路径名**

```json
// ✅ zh-CN/admin/system.json
{ "role": { "title": "角色" } }  // → admin.system.role.title

// ❌ 错误
{ "system": { "role": { "title": "角色" } } }  // → admin.system.system.role.title
```

### 常见问题

#### 重复键导致翻译失败

`[intlify] Not found 'xxx' key` — JSON 文件中同一个 key 出现多次，后者覆盖前者。

```json
// ❌ type 键重复
{ "domain": { "type": "类型", "type": { "default": "默认" } } }

// ✅ 使用不同 key
{ "domain": { "typeLabel": "类型", "type": { "default": "默认" } } }
```

#### key 路径与文件路径不匹配

文件 `langs/zh-CN/shared/common.json` 生成 key 为 `shared.common.*`，不是 `common.*`。

```typescript
// ❌ $t('common.save')     — 找不到
// ✅ $t('shared.common.save')
```

#### API 字段名与前端不一致

API 返回 `is_verified` (boolean)，前端期望 `verificationStatus` (string) 时，在 API 层做转换：

```typescript
function transformData(raw: RawType): FrontendType {
  return {
    verificationStatus: raw.is_verified ? 'verified' : 'pending',
  };
}
```

### 待重构事项

1. `zh-CN/admin.json` 与 `zh-CN/admin/*.json` 内容重复 → 逐步拆分
2. `zh-CN/tenant.json` 与 `zh-CN/tenant/*.json` 内容重复 → 逐步拆分
3. 部分大文件需拆分为模块化 JSON
4. 缺少模块化的 index.json 导入文件

---

## 七、图标

### 推荐用法

```vue
import { IconifyIcon } from '@vben/icons';

<IconifyIcon icon="lucide:user" class="size-4" />
```

### 图标来源

- Lucide（预加载，优先）: `lucide:user`
- 自定义 SVG: `svg:my-icon`（放入 `packages/icons/src/svg/icons/`）

### Tailwind CSS 图标类（离线）

```vue
<!-- 格式：icon-[图标集--图标名] (用 -- 代替 :) -->
<span class="icon-[lucide--user] size-5" />
<span class="icon-[lucide--check] size-4 text-success" />
<span class="icon-[tabler--home] size-5" />
```

构建时自动打包，无需联网。

### 菜单图标配置

```typescript
{
  path: '/admin/dashboard',
  meta: { icon: 'lucide:layout-dashboard' },  // Lucide 图标
}
{
  path: '/admin/settings',
  meta: { icon: 'svg:my-settings' },  // 自定义 SVG
}
```

### 最佳实践

1. **优先 Lucide**：已全部预加载，性能最佳，离线可用
2. **统一 IconifyIcon**：不要混用其他图标组件
3. **尺寸控制**：使用 Tailwind `size-*` 类（`size-4`、`size-5`）
4. **颜色继承**：默认继承父元素颜色，可用 `text-*` 覆盖
5. **按钮内图标**：添加 `mr-1` 间距

---

## 八、HTTP 请求

### 基本使用

```typescript
import { requestClient } from '#/utils/request';

// GET 请求
const data = await requestClient.get('/admin/users');

// POST 请求
const result = await requestClient.post('/admin/users', { name: 'test' });

// PUT/DELETE
await requestClient.put('/admin/users/1', { name: 'updated' });
await requestClient.delete('/admin/users/1');
```

### 请求选项

```typescript
// 带选项的请求
const data = await requestClient.post('/admin/users', userData, {
  loading: true, // 显示 Loading
  showSuccessMessage: true, // 显示成功提示
  successMessage: '创建成功', // 自定义成功消息
  showCodeMessage: false, // 不显示业务错误
});
```

### 文件上传

```typescript
await requestClient.upload('/api/upload', { file }, {}, (progress) => {
  console.log(`上传进度: ${progress.percent}%`);
});
```

### SSE 流式请求

```typescript
await requestClient.postSSE(
  '/api/chat',
  { message },
  {
    onMessage: (msg) => console.log(msg),
    onEnd: () => console.log('结束'),
  },
);
```

### 多端 Token

请求根据 URL 前缀自动选择 Token：

- `/admin/*` → admin Token
- `/tenant/*` → tenant Token
- `/api/v1/*` → user Token

### 业务错误码

参考 API 错误码规范文档（文档 ID 204）：

- 4010: 未认证
- 4011: 令牌已过期
- 4012: 无效的令牌
- 4030: 禁止访问
- 4031: 权限不足

---

## 九、工具函数

```typescript
import {
  formatDate,
  formatDateOnly,
  generateCode,
  confirmDelete,
} from '#/utils/common';

formatDate('2026-01-15T10:30:00'); // '2026-01-15 10:30:00'
formatDateOnly('2026-01-15'); // '2026-01-15'
generateCode({ length: 8 }); // 'A3Km9Xp7'
```

---

## 十、命名规范

| 类型       | 格式                     | 示例                |
| ---------- | ------------------------ | ------------------- |
| 目录       | kebab-case               | `admin-user/`       |
| Vue 组件   | PascalCase               | `UserList.vue`      |
| TS 文件    | kebab-case               | `token-storage.ts`  |
| API        | `{action}{Resource}Api`  | `adminLoginApi`     |
| Store      | `use{Endpoint}AuthStore` | `useAdminAuthStore` |
| Composable | `use{Name}`              | `useCrudPage`       |

---

## 十一、开发流程

1. **创建 data.ts**：定义列、搜索、表单 Schema
2. **创建 list.vue**：使用 `useCrudPage` 一行搞定
3. **创建 form.vue**：使用 `useCrudDrawer` 自动处理 create/update
4. **添加路由**：`router/routes/{endpoint}/`
5. **添加 i18n**：`locales/langs/zh-CN/{endpoint}/`

### 表单组件示例（form.vue）

#### 简化用法（推荐）

使用 `fields` 选项自动处理 camelCase ↔ snake_case 转换：

```typescript
import { useCrudDrawer } from '#/composables';
import { useFormSchema } from './data';

const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
  formApi,
  schema: useFormSchema,
  // 字段列表：自动处理数据映射
  fields: [
    'name',
    'contact_name',
    'contact_phone',
    'plan_id',
    'expires_at',
    'remark',
  ],
  onSuccess: () => emits('success'),
});
// 无需手写 transform 和 toFormValues！
```

**fields 自动处理：**

- 编辑模式：后端 `contactName` → 表单 `contact_name`
- 提交时：表单 `contact_name` → API `contact_name`（空值转 null）

#### 完整用法（复杂场景）

```typescript
import { useCrudDrawer } from '#/composables';
import { useFormSchema, getFormDefaults } from './data';

const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => ({
    // 表单值 -> API 请求体
    name: values.name,
    contact_name: values.contact_name || null,
  }),
  toFormValues: (data) => ({
    // 编辑模式：后端数据 -> 表单值
    name: data.name,
    contact_name: data.contactName,
  }),
  onSuccess: () => emits('success'),
});
```

### Schema 辅助函数

从 `#/adapter/form` 导入通用辅助函数：

```typescript
import {
  searchInput, // 搜索输入框（自动 filter[field][ilike]）
  statusSelect, // 状态选择器（自动 filter[is_active]）
  inputField, // 文本输入框
  textareaField, // 多行文本
  numberField, // 数字输入框
  dateField, // 日期选择
  switchField, // 开关
  dividerField, // 分隔线（表单分组）
  select, // 通用选择器（支持远程 API 和静态选项）
  apiSelect, // 远程下拉
} from '#/adapter/form';

// 搜索表单示例
export function useGridFormSchema() {
  return [
    searchInput('code', '租户编码'), // => filter[code][ilike]
    searchInput('name', '租户名称'),
    statusSelect(), // => filter[is_active]
    planSelect({ search: true }),
  ];
}

// 编辑表单示例
export function useFormSchema(isEdit: boolean) {
  return [
    inputField('name', '租户名称', { required: true, maxLength: 100 }),
    inputField('contact_name', '联系人'),
    planSelect(),
    dateField('expires_at', '到期时间'),
    textareaField('remark', '备注'),
  ];
}
```

### CRUD 请求约定

框架自动构造以下请求：

- **创建**：`POST {resource}` + 请求体
- **更新**：`PUT {resource}/{id}` + 请求体
- **删除**：`DELETE {resource}/{id}`

### 只读详情页（无 Form）

`useCrudDrawer` 也可以用于纯展示的详情页，只需提供 `detailApi` 即可自动处理 Loading 和数据获取。

```typescript
import { useCrudDrawer } from '#/composables';
import { getOperationLogDetailApi } from '#/api/admin/operation-log';

// 解构 detailData 获取详情数据
const { Drawer, detailData: detail } = useCrudDrawer<OperationLogInfo>({
  // 只需提供详情 API
  detailApi: (id) => getOperationLogDetailApi(id as number),
});

// 打开抽屉时
function open(id: number) {
  // 关键：必须指定 mode: 'view' 才会触发详情加载
  drawerApi.setData({ id, mode: 'view' }).open();
}
```

```vue
<template>
  <Drawer title="详情">
    <!-- detailData 会在打开抽屉并加载完成后自动赋值 -->
    <template v-if="detail">
      <Descriptions>
        <DescriptionsItem label="名称">{{ detail.name }}</DescriptionsItem>
      </Descriptions>
    </template>
  </Drawer>
</template>
```

### useCrudDrawer 独立使用（无表格场景）

`useCrudDrawer` 不依赖表格，可在任意场景单独使用，如列表页、详情页、卡片组件等。

#### 配置选项

```typescript
interface UseCrudDrawerOptions<T> {
  formApi?: any; // Form API (详情模式可选)
  schema?: (isEdit: boolean) => any[]; // Schema 工厂函数 (详情模式可选)
  transform?: (values, isEdit) => any; // 表单值 -> API 请求体
  defaults?: (() => Record<string, any>) | Record<string, any>; // 新建模式默认值
  toFormValues?: (data: T) => Record<string, any>; // 编辑模式数据映射
  detailApi?: (id: number | string) => Promise<T>; // 详情 API（自动处理 loading）
  idField?: string; // 主键字段，默认 'id'
  onSuccess?: () => void; // 成功回调
}
```

#### 用法示例

```typescript
// 引用组件
const formDrawerRef = ref<InstanceType<typeof AdminFormDrawer>>();

// 调用方法
formDrawerRef.value?.openCreate(); // 新建
formDrawerRef.value?.openEdit(record); // 编辑
```

#### 组件内部实现

```typescript
import { useCrudDrawer } from '#/composables';
import { useFormSchema, getFormDefaults } from '../data';

const {
  Drawer,
  openNew,
  openEdit
} = useCrudDrawer<AdminInfo>({
  formApi,
  schema: (isEdit) => useFormSchema(isEdit),
  defaults: getFormDefaults,              // 新建模式默认值（声明式配置）
  apiPath: '/admin/admins',               // ✅ 指定 API 路径，简化 open 调用
  detailApi: api.getAdminDetailApi,       // ✅ 编辑模式调用详情接口（可选）
  transform: (values, isEdit) => ({ ... }),
  toFormValues: (data) => ({ ... }),      // 编辑模式数据映射
  onSuccess: () => emits('success'),
});

// 暴露方法
defineExpose({
  openCreate: openNew,
  openEdit
});
```

#### 关键点

1. **`apiPath`**：独立使用时为必填，指定 API 路径（如 `/admin/admins`）；配合 `useCrudPage` 时可由 `resource` 自动推导
2. **`mode`**：`openNew`/`openEdit` 自动设置模式
3. **`defaults`**：新建模式默认值，统一在 `data.ts` 中声明
4. **`toFormValues`**：仅处理编辑模式的数据映射

---

## 十二、拖拽排序

### 推荐用法（与 useCrudPage 配合）

```typescript
import {
  useAutoTableDragSort,
  useCrudPage,
  dragColumn,
} from '#/adapter/vxe-table';

// 1. data.ts 添加拖拽列
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    dragColumn, // 拖拽手柄列（放第一列）
    { field: 'name', title: '名称' },
    // ...
  ];
}

// 2. index.vue
const { Grid, gridApi } = useCrudPage({
  columns: useColumns,
  defaultSort: 'sort_order', // ❗ 改为排序字段升序
  // ...
});

// 3. 启用拖拽（使用批量更新 API）
useAutoTableDragSort(() => gridApi.grid, {
  // 推荐：批量更新模式，backend 接收有序 ID 列表
  onBatchUpdate: async (ids) => {
    await api.reorderApi(ids);
  },
  keyField: 'id',
});
```

### DragSortConfig

```typescript
interface DragSortConfig {
  /**
   * 批量更新 API（推荐）
   * @param ids 有序的 ID 列表
   */
  onBatchUpdate?: (ids: (number | string)[]) => Promise<any>;

  /**
   * 单条更新 API（旧模式，不推荐）
   * @param id 记录 ID
   * @param sortOrder 新的排序值
   */
  onUpdate?: (id: number | string, sortOrder: number) => Promise<any>;

  keyField?: string; // 默认 'id'
  disabled?: boolean; // 禁用拖拽
  successMessage?: string; // 成功提示
  errorMessage?: string; // 失败提示
}
```

### 设计特点

- **实例隔离**：支持同一页面多个表格
- **精确定位**：通过 `gridApi.grid.$el` 查找 DOM
- **自动初始化**：`useAutoTableDragSort` 轮询等待 grid 实例可用后初始化
- **自动重新初始化**：拖拽后刷新数据时自动重新初始化 Sortable

---

## 十三、列表 UI 设计规范

### 核心理念

**拒绝纯文字表格，拥抱视觉层次**。每个列表都应该有自己的个性，根据数据特点设计最合适的呈现方式。

### Vben 设计 Token

#### 文本颜色

| Token | 用途 |
|-------|------|
| `text-foreground` | 主要文字（标题、名称，配合 `font-medium`） |
| `text-muted-foreground` | 次要文字（描述、时间、编码、空值提示） |
| `text-primary` | 链接、强调内容 |
| `text-destructive` | 错误状态 |

#### 背景颜色（透明度模式）

| Token | 用途 |
|-------|------|
| `bg-primary/10` | 主色标签背景 |
| `bg-success/10` | 启用状态背景 |
| `bg-destructive/10` | 禁用/过期状态背景 |
| `bg-warning/10` | 警告/即将过期背景 |

#### 图标容器样式

```vue
<!-- 方形容器 -->
<div class="flex size-8 items-center justify-center rounded-lg bg-primary/10">
  <IconifyIcon icon="lucide:package" class="size-4 text-primary" />
</div>

<!-- 圆形首字头像 -->
<span class="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
  :class="getAvatarColor(row.name)">
  {{ getFirstChar(row.name) }}
</span>
```

### 列渲染规范

| 列类型 | 样式 |
|--------|------|
| 编码/ID | `font-mono text-muted-foreground hover:text-primary transition-colors` + 复制图标 |
| 名称 | 图标容器/首字头像 + 双行文字 |
| 链接/域名 | `text-primary hover:underline transition-colors` + 外链图标 |
| 价格 | `rounded-lg bg-primary/10 px-3 py-1` 卡片式 Tag |
| 状态 | `rounded-lg bg-{color}/10 text-{color}` |
| 日期 | 相对时间 + Tooltip 显示完整时间 |
| 空值 | `text-muted-foreground` + i18n `admin.common.notSet` |

### 设计原则

1. **信息层次清晰**：主要信息突出，次要信息弱化
2. **视觉引导自然**：用户能快速定位关键数据
3. **交互反馈及时**：hover、点击等状态要有响应
4. **风格统一但不死板**：遵循设计语言，但允许创意

### 常用视觉元素（按需选用）

| 元素 | 适用场景 | 示例 |
| --- | --- | --- |
| **首字头像** | 名称、用户、租户等需要辨识度的字段 | 圆形/方形，背景色根据内容生成 |
| **等宽字体** | 编码、ID、哈希值等需要对齐的字段 | `font-mono text-gray-500` |
| **Tag 标签** | 状态、分类、数量、价格等离散值 | 不同颜色区分不同状态 |
| **外链图标** | URL、域名等可跳转的字段 | `lucide:external-link` |
| **复制图标** | 需要复制的编码、链接等 | 点击复制 + toast 反馈 |
| **相对时间** | 创建时间、更新时间等 | 「3 天前」，完整时间放 Tooltip |
| **进度条/数值** | 配额使用、完成度等 | 可视化比例 |
| **Switch 开关** | 可直接切换的布尔状态 | 启用/禁用 |
| **淡色占位** | 空值、未设置 | `text-gray-300` 显示「未设置」 |

### 颜色语义

| 语义           | 颜色              | 适用场景                     |
| -------------- | ----------------- | ---------------------------- |
| 成功/启用/永久 | `success` (绿)    | 启用状态、永久有效、验证通过 |
| 错误/禁用/过期 | `error` (红)      | 禁用状态、已过期、验证失败   |
| 警告/即将到期  | `warning` (橙)    | 30天内到期、需要注意         |
| 进行中/处理中  | `processing` (蓝) | 审核中、同步中               |
| 默认/普通      | `default` (灰)    | 普通状态、免费套餐           |
| 高级/推荐      | `gold/purple`     | VIP、企业版、推荐标识        |

### 创意示例

- **套餐列表**：名称用渐变背景卡片，价格用大字号突出，特性用小图标展示
- **用户列表**：头像 + 用户名组合，角色用不同颜色徽章，最后登录用相对时间
- **订单列表**：订单号等宽字体可复制，金额右对齐加粗，状态用流程图标

### 工具函数

```typescript
// 首字提取（中英文兼容）
function getFirstChar(name: string): string {
  if (!name) return '?';
  if (/^[a-z]/i.test(name)) return name[0]!.toUpperCase();
  return name[0] || '?';
}

// 名称生成背景色
function getAvatarColor(name: string): string {
  const colors = [
    'bg-blue-500',
    'bg-green-500',
    'bg-purple-500',
    'bg-orange-500',
    'bg-pink-500',
    'bg-cyan-500',
    'bg-indigo-500',
    'bg-teal-500',
  ];
  const hash = name
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length]!;
}

// 相对时间
import { formatRelativeTime, formatDate } from '#/utils/common';
// formatRelativeTime('2026-01-15') → '4 天前'
// formatDate('2026-01-15T10:30:00') → '2026-01-15 10:30:00'
```

### 禁止事项

- ❌ 整个列表全是纯文字
- ❌ 空值显示 `-` 或 `null`
- ❌ 时间列只显示完整时间戳
- ❌ 所有列表长得一模一样

---

## 十四、通用下拉 (select)

### 核心理念

使用统一的 `select()` 函数，智能判断是使用远程 API 还是静态选项。屏蔽组件差异，保持代码一致性。

### 标准用法

```typescript
import { select } from '#/adapter/form';

// 1. 远程下拉 (ApiSelect)
select('plan_id', '套餐', {
  api: getTenantPlanSelectApi,
  extraField: 'code',
});

// 2. 静态下拉 (Select) - 对象数组
select('gender', '性别', {
  options: [
    { label: '男', value: 1 },
    { label: '女', value: 2 },
  ],
});

// 3. 静态下拉 - 简单数组 (自动转 label=value)
select('tags', '标签', {
  options: ['Vue', 'React', 'Angular'],
});
```

### 业务预设定义规范

业务预设（如 `planSelect`、`roleSelect`）应定义在业务模块的 `data.ts` 中，**不从 adapter 导出**：

```typescript
// views/admin/tenant/list/data.ts
import { select } from '#/adapter/form';
import { getTenantPlanSelectApi } from '#/api/admin/plan';

/** 套餐选择器 */
export function planSelect(
  options: { search?: boolean; required?: boolean } = {},
): VbenFormSchema {
  const { search = false, required = false } = options;
  return select(search ? 'filter[plan_id]' : 'plan_id', '套餐', {
    api: getTenantPlanSelectApi,
    params: { is_active: 'true' },
    extraField: 'code',
    required,
  });
}
```

### ApiSelect 响应规范 (仅远程)

后端 `/select` 接口返回格式（遵循《通用远程下拉方案》）：

```json
{
  "items": [
    { "label": "基础版", "value": "basic", "extra": { "code": "P001" } }
  ],
  "total": 100
}
```

---

## 十五、代码风格规范

### 代码检查命令

```bash
pnpm run lint          # ESLint + Stylelint 检查
pnpm run lint:fix      # 自动修复
pnpm run check         # 类型检查 + 循环依赖检测
```

### ESLint 常见规则

| 规则 | 错误写法 | 正确写法 |
| --- | --- | --- |
| `unicorn/no-array-callback-reference` | `.map(fn)` | `.map((x) => fn(x))` |
| `unicorn/no-array-sort` | `.sort()` | `.toSorted()` |
| `unicorn/prefer-math-trunc` | `(n * 16) \| 0` | `Math.trunc(n * 16)` |
| `unicorn/no-nested-ternary` | `a ? b : c ? d : e` | if-else |
| `no-console` | `console.log()` | `console.warn/error()` |
| `prefer-const` | `let x = 1` | `const x = 1` |
| `@typescript-eslint/no-invalid-void-type` | `post<void>()` | `post()` |

### 注释与备注规范

- 新增代码注释、说明性备注、`TODO`、`FIXME`、`NOTE` 等文本时，**必须同时包含中文和英文**
- **禁止只写中文注释/备注**
- **禁止只写英文注释/备注**
- 如果代码本身已经足够清晰，**优先不新增注释**

示例：

```typescript
// Correct usage / 正确用法
const title = $t('admin.system.role.title');

// TODO: handle empty state fallback / TODO：处理空状态兜底
```

```typescript
// ❌ 错误：只写中文
// 处理空状态

// ❌ 错误：只写英文
// Handle empty state
```

### 需要 eslint-disable 的场景

```typescript
// 非空断言
// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
const value = obj.prop!;

// Vue emit 类型
/* eslint-disable @typescript-eslint/unified-signatures */
const emits = defineEmits<{ ... }>();
/* eslint-enable @typescript-eslint/unified-signatures */

// 占位空文件
/* eslint-disable unicorn/no-empty-file */
```

### Stylelint 属性顺序

```css
.element {
  /* 1. 定位 */ position, top, left, z-index
  /* 2. 盒模型 */ display, width, height, padding, margin, overflow
  /* 3. 视觉 */ background, border, border-radius
  /* 4. 动画 */ transition, max-height, opacity
}
```

---

### 代码规范检查清单

提交前请逐项确认：

#### TypeScript
- [ ] 无 `any` 类型（使用 `unknown` 或具体类型）
- [ ] 无 `@ts-ignore`（用 `@ts-expect-error` + 注释原因替代）
- [ ] 泛型函数正确推断（`post<ResponseType>()`）
- [ ] `void` 返回值不滥用（不作为泛型参数 `post<void>()`）
- [ ] 新增代码注释/备注必须中英双语，禁止只写中文或英文

#### 国际化
- [ ] 无中文硬编码，全部使用 `$t()` 或 `t()`
- [ ] JSON key 无重复
- [ ] key 路径与文件路径一致（无多余嵌套）
- [ ] 中英文均已翻译

#### 控制台
- [ ] 无 `console.log()`（用 `console.warn()` / `console.error()` 代替）
- [ ] 生产环境无调试输出

#### 组件 & 命名
- [ ] 组件用 PascalCase，文件用 kebab-case
- [ ] 无未使用的 import / 变量
- [ ] Props 定义使用 `defineProps<T>()`，非 runtime 声明

#### API & 请求
- [ ] API 函数放在正确端（admin / tenant）
- [ ] 无跨端导入（admin 页面不导入 tenant API）
- [ ] 请求错误有 catch 处理

---

## 十六、CSS 动画

### 内置 Transition

```vue
<!-- 淡入淡出 -->
<Transition name="fade">
  <div v-if="show">内容</div>
</Transition>

<!-- 上滑渐入 -->
<Transition name="slide-up">
  <div v-if="show">内容</div>
</Transition>

<!-- 缩放 -->
<Transition name="zoom">
  <div v-if="show">内容</div>
</Transition>
```

### Tailwind 动画工具类

```vue
<!-- 旋转 loading -->
<span class="icon-[lucide--loader-2] animate-spin" />

<!-- 脉冲提示 -->
<span class="animate-pulse rounded-full bg-success size-2" />

<!-- 弹跳 -->
<div class="animate-bounce">↓</div>

<!-- 自定义过渡 -->
<button class="transition-all duration-200 hover:scale-105 active:scale-95">
  按钮
</button>
```

### 列表动画

```vue
<TransitionGroup name="list" tag="div">
  <div v-for="item in items" :key="item.id">
    {{ item.name }}
  </div>
</TransitionGroup>

<style scoped>
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
.list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
```

### 注意事项

1. 动画时长统一 `150ms`（微交互）/ `300ms`（内容切换）
2. 优先用 `transform` + `opacity`（GPU 加速，不触发重排）
3. 禁止对 `width`、`height`、`top`、`left` 做动画（性能差）
4. `prefers-reduced-motion` 媒体查询下自动禁用动画

---

## 十一、Ant Design 组件 Flex 高度陷阱

在 `<Page auto-content-height>` 内使用 Master-Detail 等需要固定高度+独立滚动的布局时，**禁止直接用 Ant Design `<Card>` 作为 flex 容器**。

### 问题根因

Ant Design 的 `<Card>`、`<Spin>` 等组件内部会生成额外的 wrapper div（如 `.ant-card-head` + `.ant-card-body`、`.ant-spin-nested-loading` + `.ant-spin-container`），这些 wrapper **不继承 flex 属性**，会扩展到内容高度，导致：
- `h-full` 无效（内部 wrapper 不遵守高度约束）
- `overflow-y-auto` 无效（内部 wrapper 的 overflow 为 visible）
- 页面整体溢出，无法滚动

### ✅ 正确做法

```vue
<!-- 1. Page 不要用 content-class，用显式 wrapper div -->
<Page auto-content-height>
  <div class="flex h-full gap-4 overflow-hidden">
    <!-- 2. 面板用纯 div，不用 <Card> -->
    <div class="flex h-full w-[280px] shrink-0 flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div class="shrink-0 border-b px-3 py-2">标题栏</div>
      <div class="min-h-0 flex-1 overflow-y-auto p-3">
        <!-- 3. Spin 不要放 overflow-y-auto，包裹在外层 div 上 -->
        <Spin :spinning="loading">
          <!-- 列表内容 -->
        </Spin>
      </div>
    </div>
    <div class="flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm">
      <div class="shrink-0">头部信息</div>
      <div class="min-h-0 flex-1 overflow-auto">
        <Table />
      </div>
    </div>
  </div>
</Page>
```

### ❌ 错误做法

```vue
<!-- Card 内部 .ant-card-body 不遵守 flex 高度 -->
<Card class="h-full flex-1" :body-style="{ height: '100%', display: 'flex' }">

<!-- Spin 内部 .ant-spin-nested-loading 会扩展到内容高度 -->
<Spin class="overflow-y-auto flex-1 min-h-0">

<!-- content-class 设置在 Page 内部 wrapper 上，可能缺少 overflow 约束 -->
<Page content-class="flex gap-4">
```

### 参考页面

- `views/admin/system/organization/index.vue` — 正确的 Master-Detail 布局（纯 div）
- `views/admin/ai/skill-packages/index.vue` — 修复后的 Master-Detail 布局

---

## 相关文档

详细文档请查阅 DevGenius 文档管理系统：

- 前端开发规范-概述（目录结构详情）
- 前端开发规范-表格开发（完整 Schema 示例）
- 前端开发规范-远程下拉（ApiSelect 使用）
- 前端开发规范-权限控制（v-access 详解）
- 前端开发规范-列表筛选（JSON:API 详解）
- 前端开发规范-国际化（i18n 详解）
- 前端开发规范-图标使用（Iconify 详解）
- 前端开发规范-代码风格（ESLint/Prettier/Stylelint 规则）
