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

在 Model 上声明 `__data_permission__ = True` 才启用，默认不启用：

```python
class MyModel(TenantModel):
    __data_permission__ = True
    created_by = Column(Integer, nullable=True, comment="创建者 ID")
    dept_id = Column(Integer, nullable=True, comment="部门 ID")
```

**前置条件**：Model 必须有 `created_by` 和 `dept_id` 字段。

---

## 三、created_by / dept_id 自动填充

`TenantRepository.create()` 对声明 `__data_permission__ = True` 的 Model 自动注入：
- `created_by` ← `data_permission_ctx["current_user_id"]`
- `dept_id` ← `data_permission_ctx["primary_department_id"]`

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
1. 确保 Model 有 `created_by`、`dept_id` 字段（可 nullable）
2. 在 Model 类上声明 `__data_permission__ = True`
3. 新增 Alembic 迁移添加上述字段（若尚无）
4. 创建时 `TenantRepository.create()` 自动填充，无需 Service 手动传入

---

## 九、禁令

- 禁止在 Service 层手动拼接部门过滤条件，必须通过 `__data_permission__ = True` 声明式启用
