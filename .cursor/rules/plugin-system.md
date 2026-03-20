# 插件系统规则

## 核心原则

**插件采用零侵入架构，插件代码只能存在于 `backend/plugins/{name}/` 内。**

## 目录与入口

- 插件根目录：`backend/plugins/{plugin-name}/`
- 必需文件：`plugin.yaml`、`backend/main.py`
- 前端扩展通过 UMD 动态加载，不进入主系统源码目录
- 插件国际化只能放在插件自身 `locales/` 内

## manifest / plugin.yaml

- `name` 必须为 kebab-case
- `version` 必须为 semver
- `display_name` / `description` 必须提供 i18n 结构
- `capabilities` 必须如实声明，不能偷跑未申报能力
- `extensions.skills[*].type` 只能使用系统现有 7 种 SkillType
- API 路由、Webhook、任务、菜单、权限都要通过 manifest 声明

## 生命周期

必须按 `PluginBase` 生命周期实现和清理资源：

- `on_install`
- `on_enable`
- `on_disable`
- `on_uninstall`
- `on_upgrade`

## PluginContext

- 配置读取用 `ctx.get_config()`
- DB 访问用 `ctx.get_db()`，仅允许操作 `px_{name}_*` 表
- 外部请求用 `ctx.http_request()`，前提是声明 `http:outbound`
- AI 能力通过 `ctx.call_ai_feature()` / `ctx.call_ai_feature_stream()`

## 命名规则

- DB 表名前缀：`px_{name_underscored}_*`
- Alembic 分支：`plugin_{name_underscored}`
- API 路径：`/admin/plugins/{name}/api/*`
- 迁移文件必须声明 `branch_labels = ('plugin_{name_underscored}',)`

## 权限与菜单

- 插件权限同步必须使用 `sync_plugin_permissions(plugin.name)`
- 插件菜单注册必须与 manifest、前端组件路径、权限树同步一致
- 不要在插件安装事务里调用全量 `sync_permissions()`

## 禁止事项

- 禁止在主系统代码目录写入插件组件、插件业务逻辑、插件 locale
- 禁止自定义新的 Skill 类型
- 禁止越过 `PluginDbProxy` 操作非 `px_{name}_*` 表
- 禁止 `eval`、`exec`、`subprocess`
- 禁止未声明 capability 就调用对应上下文 API

## 参考

- `../skills/novusai-saas/references/plugin-spec.md`
- `../skills/novusai-saas/references/plugin-menu-registration.md`
- `../skills/novusai-saas/references/rbac-permission-spec.md`
