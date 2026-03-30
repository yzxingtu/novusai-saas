# RBAC 与数据权限规则

## Controller 权限注册

- 每个 Controller 都必须声明 `@permission_resource`
- `parent_resource` 必填，缺失会让权限树出现孤立节点
- 父资源 Controller 必须先于子资源导入，否则 `parent_id` 会变成 `null`

## 权限翻译

- 新 Controller 必须同步补齐 `backend/app/locales/zh_CN/messages.json`
- 对应 key 结构固定为 `action.{resource}.{action}`
- 必须在现有顶层 `"action"` 对象里追加，禁止新建第二个 `"action"` 顶层 key
- 缺少翻译时，权限树会退回显示原始英文 action 名

## 菜单一致性

- 新增页面必须同步完成后端菜单注册和前端页面落点
- 无菜单页面要走静态路由并标记 `hideInMenu`
- 开发时控制台不能残留 `[MenuCheck]` 或 `[DynamicMenu] [CRITICAL]`

## 插件权限同步

- 应用启动做全量同步：`sync_permissions()`
- 插件安装、修复、升级只同步当前插件：`sync_plugin_permissions(plugin.name)`
- 禁止在插件事务里做全量权限刷新

## 数据权限过滤

- 需要行级过滤的模型要么显式声明 `__data_permission__ = True`，要么提供标准归属字段（`created_by`、`org_node_id`、`dept_id` 或通过 `__data_permission_creator_field__` / `__data_permission_parent_model__` 指定的字段），`BaseRepository.is_data_permission_enabled()` 会自动检测并启用过滤。
- 创建记录时，`BaseRepository._apply_data_permission_create_defaults()`（`TenantRepository` 等子类都会调用）会从 `data_permission_ctx` 中把 `current_user_id`、`primary_org_id`、`primary_department_id` 等值写入 `created_by`、`org_node_id`、`dept_id`（字段存在时），无需业务层重复处理。
- 所有查询路径（`get_list`、`query_list`、`get_by_id`、`query_select_options` 等）在构建查询前都会调用 `_apply_data_permission_if_needed()` / `DataPermissionFilter`，它根据 `data_permission_ctx` 中的 `scope_mode`、`max_data_scope`、`effective_scope_org_ids`、`custom_org_ids`、`primary_org_id`、`primary_department_id` 等值生成额外的 `WHERE` 条件。
- `PermissionMiddleware` 通过 `OrgAuthorityResolver` 在每次请求开始时填充 `data_permission_ctx`，用户的 `DataScope`、可见 / 可管理组织、custom 组织列表都会被同步；公开接口、后台任务或无上下文时候 `data_permission_ctx` 为空，过滤器会返回 `None`（等同于 `DataScope.ALL`）。
- 若模型存在 `__data_permission_parent_model__`，过滤器会递归构造父级条件以保证上下游关系一致。

## RBAC 资源重命名检查清单

当需要重命名 `@permission_resource(resource="...")` 的资源名时（如 `ai_skill_registry` → `plugin_skill_registry`），必须**一次性**同步以下所有位置：

1. **后端 Controller**：`resource=`、`name=`、所有 `@action_read`/`@action_create` 装饰器中的 `action.{resource}.*` 字符串
2. **后端 `__init__.py`**：`import ... as` 别名和 `include_router()` 调用中的变量名
3. **i18n 菜单**：`locales/{en,zh_CN}/menu.json` 中 `menu.admin.{resource}` 键名
4. **i18n 权限**：`locales/{en,zh_CN}/messages.json` 中 `action.{resource}` 块名
5. **前端权限码**：所有 `v-access:code="['{resource}:*']"` 引用
6. **Alembic 迁移**：为已有数据库创建数据迁移，**必须使用 `migrations.helpers.safe_rename_permission_resource()`**（见 [alembic-migration-authoring.md](alembic-migration-authoring.md) 第 9 条），禁止手写 `REPLACE` SQL

遗漏任一处会导致：权限树孤立节点、前端按钮误拦截/漏拦截、迁移 `UniqueViolation` 崩溃。

---

## 禁止事项

- 禁止在 Service 层手动拼部门过滤 SQL
- 禁止跳过 `messages.json` 翻译直接交付 Controller
- 禁止新增 Controller 却不配置 `parent_resource`
- 禁止在迁移中手写 `REPLACE` 重命名权限资源——必须使用 `migrations.helpers.safe_rename_permission_resource()`

## 参考

- [../skills/novusai-saas/references/rbac-permission-spec.md](../skills/novusai-saas/references/rbac-permission-spec.md)
- [../skills/novusai-saas/references/data-permission-spec.md](../skills/novusai-saas/references/data-permission-spec.md)
- [menu-i18n.md](menu-i18n.md)
