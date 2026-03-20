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

- 需要行级过滤的模型声明 `__data_permission__ = True`
- Model 必须具备 `created_by` 和 `dept_id`
- 创建时由 `TenantRepository.create()` 自动填充 `created_by` / `dept_id`
- 读操作由 Repository 自动走 `DataPermissionFilter`
- 当 `data_permission_ctx` 不存在时，不强行套过滤条件

## 禁止事项

- 禁止在 Service 层手动拼部门过滤 SQL
- 禁止跳过 `messages.json` 翻译直接交付 Controller
- 禁止新增 Controller 却不配置 `parent_resource`

## 参考

- `../skills/novusai-saas/references/rbac-permission-spec.md`
- `../skills/novusai-saas/references/data-permission-spec.md`
- [menu-i18n.md](menu-i18n.md)
