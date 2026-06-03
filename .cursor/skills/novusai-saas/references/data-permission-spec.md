# 数据权限过滤规范

本文档覆盖：DataScope 枚举、Model 启用方式、created_by/dept_id 自动填充、DataPermissionFilter 调用链路、PermissionMiddleware 预加载、前端 OrgNodeDialog 配置。

---

## 一、DataScope 枚举

| 值 | 含义 |
|----|------|
| `all` | 全部数据（管理员） |
| `dept_children` | 本部门及下级部门 |
| `dept_only` | 仅本部门 |
| `self` | 仅自己的数据 |
| `custom` | 自定义部门列表 |

定义位置：`app.enums.role.DataScope`

---

## 二、Model 启用方式

在 Model 上声明 `__data_permission__ = True` 才显式启用，默认不启用。但 `BaseRepository.is_data_permission_enabled()` 在模型上发现 `__data_permission_parent_model__` 或常用归属字段（`org_node_id`、`dept_id`、`created_by`、`__data_permission_creator_field__`）时也会自动启用过滤，无需额外声明。例如，只需提供这些字段即可被默认视为受组织约束的数据表。

```python
class MyModel(TenantModel):
    __data_permission__ = True
    created_by = Column(Integer, nullable=True, comment="创建者 ID")
    dept_id = Column(Integer, nullable=True, comment="部门 ID")
    org_node_id = Column(Integer, nullable=True, comment="组织节点 ID")
```

**前置条件**：Model 必须至少定义 `created_by`/`org_node_id`/`dept_id` 中的一个字段（可以通过 `__data_permission_creator_field__` 自定义），否则自动检测无法确定归属；若使用 `__data_permission_parent_model__`，则要同步保证父模型也支持数据权限过滤。

---

## 三、created_by / dept_id 自动填充

`TenantRepository.create()` 对支持数据权限的 Model 自动注入上下文字段，`BaseRepository._apply_data_permission_create_defaults()` 会在：
 - `created_by` 缺失时写入 `current_user_id`
 - `org_node_id`/`dept_id` 缺失时写入 `primary_org_id`/`primary_department_id`
 - `__data_permission_creator_scope_field__` 在模型存在且上下文有 `current_user_scope` 时也会填充 scope
数据来自 `PermissionMiddleware` 预先设置的 `data_permission_ctx`，几乎无需业务层手动传参。

---

## 四、DataPermissionFilter 调用链路

- `BaseRepository` 的 `query_list` / `get_by_id` / `get_list` / `count` / `exists` / `get_one_by` / `get_select_options` / `query_deleted` 中，若 model 有 `__data_permission__ = True`，则调用 `_apply_data_permission_if_needed(query)`
- **ctx 为空时**：当 `data_permission_ctx` 未被 PermissionMiddleware 填充时（如公开接口、内部调用、Celery 任务），不应用数据权限过滤，直接返回原 query（等同于 ALL）
- `DataPermissionFilter.apply()` 从 `data_permission_ctx` 读取 `max_data_scope`、`all_visible_dept_ids`、`custom_dept_ids`、`current_user_id`，按规则添加 WHERE 条件

---

## 五、PermissionMiddleware 预加载

在 `_load_admin_permissions`、`_load_tenant_admin_permissions`、`_load_tenant_user_permissions` 中：
- 计算 `max_data_scope`、`all_visible_dept_ids`、`primary_department_id`、`custom_dept_ids`
- 通过 `data_permission_ctx.set(ctx)` 写入 ContextVar
- Admin 默认 `DataScope.ALL`，TenantUser 默认 `DataScope.SELF_ONLY`

---

## 六、作用范围

- **仅影响读操作**：列表查询、详情查询
- **不影响**：创建、更新、删除（由 RBAC 权限控制）

---

## 七、前端 OrgNodeDialog

- 角色编辑表单增加 **数据范围** 下拉框（5 个 DataScope 选项）
- 当选择「自定义」时，显示部门树多选组件（`TreeSelect`，仅部门类型节点）
- i18n keys：`common.role.dataScope`、`common.role.dataScopeAll`、`common.role.dataScopeDeptChildren`、`common.role.dataScopeDeptOnly`、`common.role.dataScopeSelf`、`common.role.dataScopeCustom`、`common.role.customDepts`

---

## 八、Model 接入指南

**何时启用**：当业务数据需要按部门或创建者做行级过滤时（如 TenantUser 按部门可见、业务订单按创建者可见）。

**推荐优先接入**：TenantUser、业务订单/工单类 Model、知识库/智能体等企业资源（若需部门隔离）。

**接入步骤**：
1. 确保 Model 至少包含 `created_by`、`dept_id` 或 `org_node_id` 其中一个字段（可 nullable），也可以通过 `__data_permission_creator_field__` 或 `__data_permission_parent_model__` 显式指定关联字段
2. 在 Model 类上声明 `__data_permission__ = True`
3. 新增 Alembic 迁移添加上述字段（若尚无）
4. 创建时 `TenantRepository.create()` 自动填充，无需 Service 手动传入

---

## 九、禁令

- 禁止在 Service 层手动拼接部门过滤条件，必须通过 `__data_permission__ = True` 声明式启用
