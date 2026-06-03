# 删除依赖保护规范

## 一、何时需要声明 `__delete_deps__`

任何 Model 只要有 **其他 Model 通过 FK 引用它**，就必须在被引用方声明 `__delete_deps__`。
声明的是"谁引用了我，删我时怎么办"。

---

## 二、五种策略选择标准

| 策略 | 行为 | 选择标准 | 典型场景 |
|------|------|---------|---------|
| `BLOCK` | 有依赖就拒绝删除 | 子记录有独立业务价值，不应随父消失 | Provider→Model, Model→Agent, Role→Admin |
| `CASCADE_SOFT` | 子记录跟着软删除进回收站 | 子记录依附父记录，父删子也该进回收站 | Provider→ApiKey, Model→Quota, Agent→Conversation |
| `CASCADE_DELETE` | 子记录物理删除 | 子记录是纯关联/绑定，无独立价值 | Agent→SkillBinding |
| `NULLIFY` | FK 字段置 NULL | FK 是可选的引用 | AIModel→fallback_model_id |
| `IGNORE` | 不处理 | 日志/统计类，不影响数据完整性 | CallLog, UsageStat |

---

## 三、声明语法

```python
# backend/app/models/xxx.py
from app.core.deletion import DeletionDep, DeletionStrategy

class MyModel(BaseModel):
    __delete_deps__ = [
        DeletionDep("ChildModel", "parent_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="child_model"),
        DeletionDep("RelatedModel", "my_model_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="related_model"),
    ]
```

**参数说明：**
- `model`: 引用本模型的目标模型类名（字符串）
- `fk_field`: 目标模型中的 FK 字段名
- `strategy`: 五种策略之一
- `label_field`: 用于前端展示的字段（默认 `"name"`）
- `i18n_key`: 前端 `common.dependency.model.{i18n_key}` 的翻译 key

**示例：AIModel 与知识库可选模型**
删除 AIModel 时，引用其作为 `audio_model_id` / `video_model_id` 的知识库将对应字段置为 NULL（NULLIFY）；前端需在 `common.dependency.model` 中提供 `knowledge_base_audio`、`knowledge_base_video` 展示名称。

---

## 四、前端 DependencyBlockModal

`useCrudPage` / `useCrudList` 已统一接入：删除被 4221 阻止时会自动弹出依赖详情弹窗。

**非 useCrudPage / useCrudList 页面手动使用：**

```vue
<script setup lang="ts">
import { showDependencyBlockModal } from '#/components/business/dependency-block-modal/service';

async function onDelete(record) {
  try {
    await requestClient.delete(`/resource/${record.id}`, { showCodeMessage: false });
  } catch (error) {
    const resp = error?.response?.data;
    if (resp?.code === 4221 && resp?.dependencies) {
      await showDependencyBlockModal(resp.dependencies, record.name);
    }
  }
}
</script>
```

---

## 五、useCrudPage 回收站配置

```typescript
const { Grid } = useCrudPage({
  // ... 其他配置
  recycleBin: true,  // 启用回收站（使用默认配置）
  // 或自定义：
  recycleBin: {
    nameField: 'title',
    columns: [{ title: '标题', dataIndex: 'title', width: 200 }],
  },
});
```

---

## 六、两阶段回收站架构

- 普通 CRUD 页统一使用**模块回收站**；管理端和企业端都走同一套弹窗交互。
- **总回收站只有一个**，固定在管理端：`/admin/system/recycle-bin`。
- 企业端**没有**总回收站页面；模块回收站二次删除后，数据进入管理端总回收站，由平台统一恢复或清理。
- 模块回收站查询阶段：
  - 管理端：`delete_level='admin'` + `recycle_stage='module'`
  - 企业端：`delete_level='tenant'` + `recycle_stage='module'`
- 总回收站查询阶段：查 `recycle_stage='global'` 的二阶段记录，覆盖管理端与企业端来源。

### 关键实现约束

- 控制器里 `register_admin_recycle_bin_routes()` / `register_tenant_recycle_bin_routes()` 必须放在 `/{id}`、`/{task_id}` 等动态路由之前，否则 `/recycle-bin` 会被误解析成路径参数。
- `batch`、`batch-restore` 这类静态子路径也必须先于 `/recycle-bin/{item_id}` 注册。
- 企业端模型如果实际归属字段是 `owner_tenant_id`，回收站查询和计数必须使用归属列，不要再硬编码 `tenant_id` 过滤。

---

## 七、新模块 Checklist

每次新增模块时，按以下清单逐项完成：

- [ ] **Model 声明 `__delete_deps__`** — 分析所有引用此模型的 FK，选择合适策略
- [ ] **Service 验证** — 尝试删除有依赖的记录，确认返回 4221 + 依赖详情
- [ ] **useCrudPage 启用 `recycleBin`** — 列表页配置 `recycleBin: true`
- [ ] **RECYCLABLE_MODELS 注册** — `backend/app/tasks/recycle_bin.py` 添加模型路径，注意顺序（叶子先父后）
- [ ] **总回收站模块注册** — `backend/app/api/admin/recycle_bin.py` 的 `RECYCLABLE_MODULES` 添加条目
- [ ] **i18n 模型名称** — 后端 `deletion.model.xxx` + 前端 `common.dependency.model.xxx`（zh-CN + en-US）
- [ ] **路由顺序验证** — `recycle-bin` 静态路由必须先于动态 `/{id}` 路由
- [ ] **浏览器回归** — 管理端模块页能跳总回收站，企业端模块页没有总回收站入口，企业端总回收站 URL 为 404

---

## 八、错误码

| 错误码 | 含义 | 前端处理 |
|--------|------|---------|
| 4221 | 删除被依赖阻止 | 弹出 DependencyBlockModal |
