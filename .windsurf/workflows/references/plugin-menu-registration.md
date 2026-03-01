# 插件菜单注册全链路规范

> 审计时间：2026-02-28  
> 覆盖范围：plugin.yaml 声明 → 后端注册 → 权限同步 → 前端路由 → 管理员动态配置

---

## 一、核心设计原则

| 职责 | 负责方 |
|------|--------|
| 菜单层级、图标、i18n | **后端权限系统**（`rbac/sync.py`）|
| 路由注册（页面可导航） | **前端插件初始化**（`use-plugin-frontend-init.ts`）|
| 菜单目录位置配置 | **管理员界面**（启用插件时弹窗 / 已启用后调整）|

**禁止在 `standalone_pages` 中重复添加侧边栏菜单**。`standalone_pages` 仅注册路由，`menus` 声明才驱动侧边栏条目。

---

## 二、plugin.yaml 完整菜单声明

```yaml
extensions:
  frontend:
    # ① 菜单声明 → 后端注册到 permissions 表，驱动侧边栏
    menus:
      - name: my_plugin          # 唯一名称（用于 menu_overrides key）
        path: /plugins/my-plugin # 前端路由路径（相对于 /admin 或 /tenant）
        icon: lucide:puzzle       # Lucide 图标
        parent: system_mgmt      # 默认父级目录 short_name（可被管理员覆盖）
        sort_order: 60
        scope: admin_only        # admin_only | all_tenants | admin_and_all
        title:
          zh-CN: "我的插件"
          en: "My Plugin"
        hidden: false            # false = 侧边栏可见

    # ② 页面路由声明 → 仅注册 Vue Router 路由，不产生菜单条目
    standalone_pages:
      - name: my_plugin_page
        path: /admin/plugins/my-plugin  # 必须带 /admin/ 或 /tenant/ 前缀
        component: MyPluginPage         # 对应 frontend/src/index.ts export 的组件名
        title:
          zh-CN: "我的插件"
          en: "My Plugin"
        # 不声明 hidden：框架自动将 standalone_pages 设为 hidden=true
```

### scope 取值说明

| scope | 菜单出现在 | 常见错误 |
|-------|-----------|----------|
| `admin_only` | 仅管理端侧边栏 | ~~`"admin"`~~ |
| `all_tenants` | 仅租户端侧边栏 | ~~`"tenant"`~~ |
| `admin_and_all` | 管理端 + 租户端（拆分为两条独立权限） | — |

> ⚠️ **旧 bug 记录**：novusdoc 曾使用 `scope: "tenant"` 和 `scope: "admin"`，导致 admin 菜单被错误注册为 `ALL_TENANTS` 作用域。正确值必须是上表中的枚举字符串。

### 真实示例：novusdoc（管理端 + 租户端双侧菜单）

```yaml
frontend:
  # 菜单声明：驱动侧边栏条目（不含 component 字段）
  menus:
    - name: novusdoc_docs_tenant      # 租户端文档入口
      path: /tenant/plugins/novusdoc/docs
      icon: lucide:file-text
      scope: all_tenants              # ✅ 不是 "tenant"
      parent: tenant_workspace        # 管理员可覆盖
      title:
        zh-CN: "文档"
        en: "Documents"

    - name: novusdoc_docs_admin       # 管理端文档入口
      path: /plugins/novusdoc/docs
      icon: lucide:file-text
      scope: admin_only               # ✅ 不是 "admin"
      parent: system_mgmt             # 管理员可覆盖
      title:
        zh-CN: "文档管理"
        en: "Documents"

  # 页面路由声明：注册可导航路由（不产生菜单条目）
  standalone_pages:
    - name: novusdoc_docs_list_tenant
      path: /tenant/plugins/novusdoc/docs
      component: DocumentList
    - name: novusdoc_editor_tenant
      path: /tenant/plugins/novusdoc/docs/:docId   # 支持动态路由参数
      component: DocumentEditor
    - name: novusdoc_docs_list_admin
      path: /admin/plugins/novusdoc/docs
      component: DocumentList
    - name: novusdoc_editor_admin
      path: /admin/plugins/novusdoc/docs/:docId
      component: DocumentEditor
```

配置弹窗效果：
```
┌─ 菜单位置配置 ─────────────────────────────┐
│ ── 🖥 管理端菜单 ──────────────────────    │
│  📄 文档管理    [系统管理 ▼]               │
│                                           │
│ ── 👥 租户端菜单 ──────────────────────   │
│  📄 文档        [工作台 ▼]                │
└────────────────────────────────────────────┘
```

---

## 三、后端注册链路

```
plugin.yaml
  └─ ExtensionRegistry.register_menu()          # registry.py
       └─ PermissionMeta(code, i18n_key, icon, path, parent_code, scope)
            └─ permission_registry.register()
                 └─ rbac/sync.py: sync_permissions()
                      └─ permissions 表（含 parent_id, icon, path, scope）
                           └─ permission_service.get_admin_menus() / get_tenant_menus()
                                └─ 前端 /api/v1/rbac/menus 返回树形菜单
```

### i18n key 规则

```python
# registry.py register_menu()
safe_name = plugin_name.replace("-", "_")  # "storage-migration" → "storage_migration"
i18n_key = f"{safe_name}.menu.title"       # "storage_migration.menu.title"
```

插件必须在 `locales/zh-CN.json` 和 `locales/en.json` 中提供对应 key：

```json
{
  "storage_migration": {
    "menu": { "title": "存储迁移" }
  }
}
```

### parent_code 规则

```python
# registry.py
scope_prefix = "admin" if scope == "admin_only" else "tenant"
parent_code = f"menu:{scope_prefix}.{parent}"
# parent="system_mgmt" → "menu:admin.system_mgmt"
```

可用的系统父级目录（`short_name`）：

| short_name | 中文名 | 作用域 |
|------------|--------|--------|
| `system_mgmt` | 系统管理 | admin |
| `system_maintenance` | 系统维护 | admin |
| `tenant_mgmt` | 租户管理 | admin |
| `ai_mgmt` | AI 管理 | admin |
| *(租户目录见数据库 permissions 表)* | | tenant |

---

## 四、前端路由注册链路

```
/api/v1/admin/plugins/frontend-config
  └─ use-plugin-frontend-init.ts: ensurePluginRoutes()
       └─ registerPluginSlots()
            ├─ menus → sidebarMenus slot（hidden=false → 侧边栏可见）
            └─ standalone_pages → sidebarMenus slot（强制 hidden=true → 仅注册路由）
                 └─ registerPluginPageRoutes()
                      └─ router.addRoute('AdminRoot' | 'TenantRoot', ...)
```

**关键规则**：`standalone_pages` 的 `path` 必须以 `/admin/plugins/` 或 `/tenant/plugins/` 开头，否则被忽略。

---

## 五、管理员动态配置菜单位置

### 5.1 启用时配置

`POST /api/v1/admin/plugins/{id}/enable`

```json
{
  "menu_overrides": [
    { "name": "my_plugin", "parent": "system_maintenance" },
    { "name": "my_plugin_both", "parent": "system_mgmt", "tenant_parent": "tenant_home" }
  ]
}
```

### 5.2 已启用后调整

`PUT /api/v1/admin/plugins/{id}/menu-config`

```json
{
  "menu_overrides": [
    { "name": "my_plugin", "parent": "ai_mgmt" }
  ]
}
```

调用后自动：1) 重新注册扩展点，2) 调用 `sync_permissions()` 使变更立即生效。

### 5.3 可用父级菜单树

`GET /api/v1/admin/plugins/menu-parent-options`

> **只返回目录型菜单**（有子菜单的节点）。叶子页面菜单不作为父级候选，避免插件挂到页面节点下导致页面不可访问。

返回：
```json
{
  "admin": [
    { "value": "system_mgmt", "label": "系统管理", "icon": "lucide:wrench",
      "children": [
        { "value": "system_maintenance", "label": "系统维护", "icon": "lucide:hard-drive" }
      ]
    }
  ],
  "tenant": [...]
}
```

### 5.4 配置存储位置

`Plugin.config.menu_overrides`（JSON 字段）：

```json
{
  "menu_overrides": {
    "my_plugin": { "parent": "system_maintenance" },
    "my_plugin_both": { "parent": "system_mgmt", "tenant_parent": "tenant_home" }
  }
}
```

---

## 六、admin_and_all 双端菜单处理（必读）

`scope: admin_and_all` 的菜单声明，`_extension_registrar.py` **始终**拆分为两条独立权限：

```python
# name="my_menu", scope="admin_and_all"
# override = {"parent": "system_mgmt", "tenant_parent": "tenant_home"}
#
# → 注册 name="my_menu_admin", scope="admin_only",  parent="system_mgmt"
# → 注册 name="my_menu_tenant", scope="all_tenants", parent="tenant_home"
#
# 若未配置 tenant_parent，降级使用 admin parent：
# → 注册 name="my_menu_admin", scope="admin_only",  parent="system_mgmt"
# → 注册 name="my_menu_tenant", scope="all_tenants", parent="system_mgmt"
```

**禁止**在 plugin.yaml 中用 `admin_and_all` 替代分别声明两个单端菜单。推荐做法：

```yaml
# ✅ 推荐：明确声明两个菜单，分别设置 scope
menus:
  - name: my_admin_menu
    scope: admin_only
    parent: system_mgmt
  - name: my_tenant_menu
    scope: all_tenants
    parent: tenant_home

# ⚠️ 允许但慎用：admin_and_all 会自动拆分，name 会变成 my_menu_admin / my_menu_tenant
menus:
  - name: my_menu
    scope: admin_and_all
    parent: system_mgmt  # admin 默认父级（tenant 未配置时也用此）
```

**弹窗 UI**：`PluginMenuConfigModal` 将菜单按 scope 分为两个区块：
- **管理端菜单**（`admin_only` + `admin_and_all` 的 admin 侧）
- **租户端菜单**（`all_tenants` + `admin_and_all` 的 tenant 侧）

每个区块用 TreeSelect 独立选择父级目录，`admin_and_all` 菜单会同时出现在两个区块中。

---

## 七、前端插件入口文件规范

`backend/plugins/{name}/frontend/src/index.ts`：

```typescript
export { default as MyPluginPage } from './MyPluginPage.vue';

// 可选：setup 钩子（插件初始化时调用）
export function setup() { /* ... */ }
```

`component` 名称必须与 `standalone_pages[].component` 完全一致。

---

## 八、常见问题

| 症状 | 原因 | 排查 |
|------|------|------|
| 菜单显示为顶级 | `parent` 写错 short_name | 查询 `permissions` 表确认 `parent_id` |
| 菜单无图标 | `register_menu` 时 icon 为空 | 确认 plugin.yaml `menus[].icon` 不为空 |
| 菜单名称显示 key | i18n 未加载 | 确认 `locales/{zh-CN\|en}.json` 存在且 key 正确 |
| 路由 404 | `standalone_pages.path` 缺少 `/admin/plugins/` 前缀 | 对比 `_FRONTEND_PLUGIN_ROUTE_PREFIXES` |
| 菜单重复出现 | `menus` 和 `standalone_pages` 都声明了同一路径 | `standalone_pages` 不要设 `hidden: false` |
| 租户端不显示 | scope 设为 `admin_only` | 改为 `all_tenants` 或 `admin_and_all` |
