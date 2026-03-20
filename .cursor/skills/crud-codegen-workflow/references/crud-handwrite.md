# 手写 CRUD 完整代码示例

> 以 tenant 模块下 Notice（公告）为例，展示完整 7 步后端 + 前端代码。
> 仅当 codegen 不适用（纯配置面板、Dashboard 聚合、已有模块增量修改）时手写。

---

## 后端 7 步

### Step 1: Model

```python
# backend/app/models/tenant/notice.py
from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.base_model import TenantModel
from app.core.deletion_deps import DeletionDep, DeletionStrategy

class Notice(TenantModel):
    __tablename__ = "notices"
    __table_args__ = {"comment": "公告"}

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否发布")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    # 前端过滤字段
    __filterable__ = {
        "title": "title",
        "is_published": "is_published",
        "created_at": "created_at",
    }

    # 前端可排序字段
    __sortable__ = ["created_at", "sort_order"]

    # 下拉选项配置
    __selectable__ = {
        "label": "title",
        "value": "id",
        "search": ["title"],
    }

    # 被 FK 引用时必须声明删除依赖
    __delete_deps__ = [
        DeletionDep("NoticeAttachment", "notice_id",
                    DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="notice_attachment"),
    ]
```

### Step 2: Schema

```python
# backend/app/schemas/tenant/notice.py
from typing import Optional
from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema, BaseResponseSchema

class NoticeCreate(BaseCreateSchema):
    title: str
    content: str
    is_published: bool = False

class NoticeUpdate(BaseUpdateSchema):
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[bool] = None

class NoticeResponse(BaseResponseSchema):
    title: str
    content: str
    is_published: bool
    sort_order: int
```

### Step 3: Repository

```python
# backend/app/repositories/tenant/notice_repository.py
from app.core.base_repository import TenantRepository
from app.models.tenant.notice import Notice

class NoticeRepository(TenantRepository[Notice]):
    model = Notice
```

### Step 4: Service

```python
# backend/app/services/tenant/notice_service.py
from app.core.base_service import TenantService
from app.repositories.tenant.notice_repository import NoticeRepository
from app.models.tenant.notice import Notice

class NoticeService(TenantService[Notice]):
    def __init__(self, db, tenant_id: int):
        super().__init__(db, tenant_id)
        self.repo = NoticeRepository(db, tenant_id)
```

### Step 5: Controller

```python
# backend/app/api/tenant/notices.py
from app.core.base_controller import TenantController
from app.rbac.decorators import permission_resource
from app.services.tenant.notice_service import NoticeService
from app.schemas.tenant.notice import NoticeCreate, NoticeUpdate, NoticeResponse

@permission_resource("notice", parent_resource="system_mgmt")
class NoticeController(TenantController):
    service_class = NoticeService
    create_schema = NoticeCreate
    update_schema = NoticeUpdate
    response_schema = NoticeResponse
```

### Step 6: 注册路由

```python
# backend/app/api/tenant/__init__.py 中确保 import
from .notices import NoticeController  # noqa: F401
```

### Step 7: 生成迁移

```bash
novusai db autogenerate -m "add notices table"
```

---

## 前端 CRUD

### 模式选择

| 场景 | Composable | 说明 |
|------|-----------|------|
| 表格列表（日志、配置、用户管理） | `useCrudPage` | 标准 VxeTable 表格 |
| 卡片网格（知识库、智能体、插件） | `useCrudList` | 自定义卡片模板 |
| Master-Detail（左列表+右详情） | `useCrudList` × 2 | 分栏布局 |

### data.ts — 列/搜索/表单定义

```typescript
// frontend/apps/web-antd/src/views/tenant/{module}/{resource_plural}/data.ts
import { searchInput, statusSelect, inputField, textareaField } from '#/adapter/form';

export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    { field: 'title', title: $t('tenant.notice.title') },
    { field: 'isPublished', title: $t('tenant.notice.isPublished') },
    { field: 'createdAt', title: $t('common.createdAt') },
  ];
}

export function useGridFormSchema() {
  return [
    searchInput('title', $t('tenant.notice.title')),
    statusSelect(),
  ];
}

export function useFormSchema(isEdit: boolean) {
  return [
    inputField('title', $t('tenant.notice.title'), { required: true }),
    textareaField('content', $t('tenant.notice.content'), { required: true }),
  ];
}
```

### index.vue — useCrudPage 模式

```vue
<script setup lang="ts">
import { tenantApi as api } from '#/api';
import { useCrudPage } from '#/adapter/vxe-table';
import Form from './modules/form.vue';

const { Grid, FormDrawer } = useCrudPage<NoticeInfo>({
  api: {
    list: api.getNoticeListApi,
    resource: '/tenant/notices',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  i18nPrefix: 'tenant.notice',
  nameField: 'title',
  recycleBin: true,
});
</script>

<template>
  <Grid />
  <FormDrawer />
</template>
```

### form.vue — useCrudDrawer

```vue
<script setup lang="ts">
import { useCrudDrawer } from '#/composables';
import { useFormSchema } from '../data';

const { FormDrawer, formApi, isEdit } = useCrudDrawer({
  createApi: api.createNoticeApi,
  updateApi: api.updateNoticeApi,
  getApi: api.getNoticeApi,
  schema: useFormSchema,
  fields: ['title', 'content', 'isPublished'],
  i18nPrefix: 'tenant.notice',
});
</script>

<template>
  <FormDrawer />
</template>
```

### useCrudList（卡片模式）示例

```vue
<script setup lang="ts">
import { tenantApi as api } from '#/api';
import { useCrudList } from '#/composables';

const {
  list, loading, pagination,
  handleSearch, handleCreate, handleEdit, handleDelete,
} = useCrudList<KnowledgeBaseInfo>({
  api: {
    list: api.getKnowledgeBaseListApi,
    delete: api.deleteKnowledgeBaseApi,
  },
  i18nPrefix: 'tenant.knowledgeBase',
});
</script>

<template>
  <div class="grid grid-cols-3 gap-4">
    <div v-for="item in list" :key="item.id" class="card">
      <h3>{{ item.name }}</h3>
      <p>{{ item.description }}</p>
    </div>
  </div>
</template>
```

---

## i18n 文件示例

```json
// frontend/apps/web-antd/src/locales/langs/zh-CN/tenant.json（合并）
{
  "notice": {
    "title": "标题",
    "content": "内容",
    "isPublished": "已发布",
    "_name": "公告"
  }
}
```

```json
// frontend/apps/web-antd/src/locales/langs/en-US/tenant.json（合并）
{
  "notice": {
    "title": "Title",
    "content": "Content",
    "isPublished": "Published",
    "_name": "Notice"
  }
}
```

---

## API Composable 示例

```typescript
// frontend/apps/web-antd/src/composables/use-notice-apis.ts
import { tenantApi } from '#/api';

export function useNoticeApis() {
  return {
    getNoticeListApi: (params: any) =>
      tenantApi.get('/notices', { params }),
    getNoticeApi: (id: number) =>
      tenantApi.get(`/notices/${id}`),
    createNoticeApi: (data: any) =>
      tenantApi.post('/notices', data),
    updateNoticeApi: (id: number, data: any) =>
      tenantApi.put(`/notices/${id}`, data),
    deleteNoticeApi: (id: number) =>
      tenantApi.delete(`/notices/${id}`),
  };
}
```
