# Fix Permission Tree Nodes And Translations

## Goal
修复管理端权限接口与套餐可分配权限接口中出现的缺失父节点、缺失翻译或展示原始权限名的问题，并将约束补充到项目规范中，避免再次发生。

## Requirements
- 检查 `/admin/permissions` 接口返回的权限树，定位缺少节点或缺少翻译的根因。
- 检查 `/admin/plans/available-permissions` 接口是否存在相同类型的问题。
- 修复权限树构建、父节点挂载或翻译解析中的缺陷，确保两个接口输出一致且稳定。
- 在项目规范中写明权限资源注册、父级资源、翻译维护和套餐权限树的注意事项。

## Acceptance Criteria
- [ ] `/admin/permissions` 中的权限节点都能正确挂到父菜单或资源下，不再出现异常缺失。
- [ ] `/admin/permissions` 中不再出现应翻译却回退为原始 action/resource 名称的异常项。
- [ ] `/admin/plans/available-permissions` 与权限树构建规则保持一致，不再出现同类问题。
- [ ] 项目规范明确记录权限注册与翻译约束，并覆盖套餐权限树的生成要求。

## Technical Notes
- 重点检查 `PermissionService`、权限注册装饰器、菜单定义、`messages.json` 翻译与套餐权限树构建逻辑。
- 优先保持改动在既有权限体系内，避免引入新的权限数据格式。
