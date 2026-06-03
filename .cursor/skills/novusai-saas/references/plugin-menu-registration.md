# 插件菜单注册规范（2026-03-22 整改后）

## 1. 单一事实来源

- 页面声明只允许使用 `extensions.frontend.pages[*]`。
- 菜单入口只允许来自 `pages[*].menu`。
- 不允许再并存：
  - `frontend.menus`
  - `frontend.standalone_pages`

页面示例：

```yaml
extensions:
  frontend:
    pages:
      - name: storage_migration_home
        path: /admin/plugins/storage-migration
        component: StorageMigrationPage
        scope: admin
        icon: lucide:hard-drive-download
        title:
          zh-CN: "存储迁移"
          en: "Storage Migration"
        menu:
          parent: system_mgmt
          sort_order: 60
          icon: lucide:hard-drive-download
          title:
            zh-CN: "存储迁移"
            en: "Storage Migration"
```

## 2. 职责边界

### 页面声明负责

- 路由 path
- 导出 component 名
- 页面标题
- 页面 AI 元数据
- 页面属于 `admin` 或 `tenant`

### 菜单声明负责

- 是否出现在菜单
- 默认父级
- 排序
- 图标
- 菜单标题

## 3. 后端链路

- manifest 校验：`backend/app/plugins/manifest.py`
- 菜单注册：`backend/app/plugins/registry.py`
- 权限同步：`sync_plugin_permissions(plugin.name)`
- 菜单配置更新：只重建 `menu` 域，不重跑整套扩展注册

当前要求：
- `menu-config` 更新时只能：
  - 更新 `plugin.config.menu_overrides`
  - 注销该插件 `menu` 域
  - 重建该插件菜单导航
  - 同步菜单权限
- 不允许 `unregister_all() + register_all_extensions()`

## 4. 前端链路

- 宿主先通过 `/plugins/slots` 拉取当前端已启用且可见的页面/slots。
- `pages` 只注册动态路由，不在宿主里重复声明路径。
- 菜单树仍由后端 RBAC 权限系统返回。

## 5. 管理端交互

菜单位置配置必须以“页面”为单位，而不是另一套独立菜单对象。

配置页至少要让管理员看清：
- 页面名
- 所属端别
- 默认父级
- 当前覆盖父级

当前实现原则：
- 菜单变化只影响导航层
- 不影响 API / webhook / task / skill / slots 等其他扩展

## 6. 端别语义

- `pages[*].scope` 只允许 `admin` / `tenant`
- 当前不支持 `user` 端插件
- 菜单父级选择 API 也只返回 `admin` / `tenant`

## 7. i18n

- 菜单标题以 `pages[*].menu.title` 为源
- 页面标题以 `pages[*].title` 为源
- 插件自己的 locale 可以使用嵌套 `plugin.{name}` 结构组织页面内部文案，但动态菜单标题仍以 manifest 中的 `pages[*].menu.title` 为准
- 动态菜单由后端返回翻译后的文本；前端不要再维护一套 `menu.*` 翻译副本
