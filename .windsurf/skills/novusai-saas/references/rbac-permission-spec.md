# RBAC 权限注册规范

> 本文档覆盖权限注册、权限树构建、i18n 翻译、插件权限同步的完整规范。违反任何一条均会导致权限树出现孤立节点或显示原始 action 名称（乱码）。

---

## 一、Controller 权限注册必填字段

### 基础格式

```python
@permission_resource(
    "resource_name",
    parent_resource="parent_name",   # ⚠️ 必填，缺失会导致权限孤立
    label="资源中文名称",              # 可选，用于管理端权限树显示
)
class MyController(GlobalController):
    @action_read
    async def list(self): ...

    @action_create
    async def create(self): ...
```

### `parent_resource` 规则（核心）

**每个 Controller 都必须声明 `parent_resource`**，缺失时该资源下所有 action 权限的 `parent_id=null`，在权限树中成为孤立节点，用户无法通过角色分配看到这些权限。

**父资源命名对照表**（与 `admin_menus.py` 保持一致）：

| 资源 | parent_resource |
|------|----------------|
| AI Gateway、AI 健康检查、AI 用量统计 | `ai_infra` |
| AI 供应商、AI 模型、AI API Key | `ai_provider` |
| AI 配额（平台级） | `ai_quota_mgmt` |
| 知识库（平台管理）、Agent（平台管理） | `ai_agent_mgmt` |
| 技能包（平台管理） | `ai_skill_mgmt` |
| 系统日志、任务日志、定时任务、缓存管理 | `system_maintenance` |
| 操作日志、系统配置 | `system_config` |
| 租户、套餐、插件 | `platform_mgmt` |

### 新增 Controller 的完整权限注册模板

```python
from app.rbac.decorators import (
    permission_resource, action_read, action_create, action_update, action_delete,
    public, auth_only,
)

@permission_resource(
    "my_resource",
    parent_resource="system_maintenance",  # ← 根据资源归属选择
    label="我的资源",
)
class MyResourceController(GlobalController):

    @action_read
    async def list(self, ...): ...

    @action_read
    async def detail(self, ...): ...

    @action_create
    async def create(self, ...): ...

    @action_update
    async def update(self, ...): ...

    @action_delete
    async def delete(self, ...): ...
```

---

## 二、权限 i18n 翻译规范

### 翻译 key 路径

权限名称由 `PermissionService._translate_name()` 解析，key 格式为：

```
action.{resource_name}.{action_name}
```

文件位置：`backend/app/locales/zh_CN/messages.json` → `action` 对象

### 强制要求：新 Controller 必须同时在 messages.json 注册翻译

在 `messages.json` 的 `"action"` 段中添加对应子对象：

```json
{
  "action": {
    "my_resource": {
      "list": "查看我的资源列表",
      "detail": "查看我的资源详情",
      "create": "创建我的资源",
      "update": "更新我的资源",
      "delete": "删除我的资源"
    }
  }
}
```

### 翻译缺失的后果

`_translate_name()` 回退逻辑：

```python
@staticmethod
def _translate_name(name: str) -> str:
    if name and "." in name:
        translated = _(name)
        if translated == name:       # ← i18n key 未命中
            return name.split(".")[-1]   # ← 返回原始 action 名（英文）
        return translated
    return name or ""
```

**翻译 key 缺失时，权限树中显示 `list` / `create` / `delete` 等原始英文 action 名，而非中文描述**。

### messages.json 编辑规则（防止重复 key）

`messages.json` 已有顶层 `"action"` 对象（约 line 737），**禁止再次写入第二个 `"action"` 对象**。Python 的 `json` 模块和大多数 JSON 解析器在遇到重复 key 时会静默覆盖，导致先定义的翻译丢失。

**正确做法**：找到现有 `"action"` 对象，在其 `}` 前插入新子对象：

```json
"action": {
  ...现有条目...,
  "my_resource": {        ← 在此追加，不要新建第二个 "action"
    "list": "...",
    "create": "..."
  }
}
```

---

## 三、权限同步机制

### 启动时自动同步

应用启动（`lifespan`）→ `init_database()` → `PermissionSyncService.sync_permissions()` 自动将所有注册的 `@permission_resource` 写入 DB，并更新 `parent_id`。

### 孤立权限的清理

`sync.py` 自动处理被删除控制器留下的权限：

```python
# 代码中移除的控制器 → 对应权限自动禁用（不物理删除）
orphan_keys = set(existing_map.keys()) - registered_keys
for key in orphan_keys:
    db_perm.is_enabled = False
```

**结论**：无需手动删除权限记录，重启后孤立权限自动 `is_enabled=False`，不出现在权限树中。

### 插件权限同步（关键区分）

| 场景 | 正确用法 | 错误用法 |
|------|---------|---------|
| 应用启动全量同步 | `perm_sync.sync_permissions()` | — |
| 插件安装/修复时的权限同步 | `perm_sync.sync_plugin_permissions(plugin.name)` | `perm_sync.sync_permissions()`（会触发全量 flush，可能在事务中间产生副作用） |

```python
# ✅ 正确：插件修复时仅同步该插件的权限
try:
    from app.rbac.sync import PermissionSyncService
    perm_sync = PermissionSyncService(db)
    await perm_sync.sync_plugin_permissions(plugin.name)
except Exception as _perm_exc:
    logger.warning("Repair: permission sync failed for %s: %s", plugin.name, _perm_exc)
```

---

## 四、用户端（tenant_user）权限扩展

### 新增 Scope

用户端 RBAC 使用独立的 `tenant_user` scope，通过 `PermissionScope.USER` 枚举值标识。

### 菜单定义

用户端菜单定义在 `backend/app/rbac/menus/user_menus.py`：

```python
USER_DIRECTORY_MENUS: list[PermissionMeta] = [
    PermissionMeta(
        code="menu:user.dashboard",
        name="menu.user.dashboard",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.dashboard",
        icon="lucide:layout-dashboard",
        path="/dashboard",
        sort_order=10,
    ),
]
```

### 注册流程

1. `user_menus.py` 中定义 `USER_DIRECTORY_MENUS`
2. `register_directory_menus()` 新增 `USER_DIRECTORY_MENUS` 注册
3. `ResourceScopeEnum` 新增 `TENANT_USER` 值
4. Permission 中间件 `_load_permissions()` 新增 `TOKEN_SCOPE_TENANT_USER` 分支

### 用户端 Controller 权限模式

用户端大多数 API 使用 `@auth_only` 或 `@public`，不需要细粒度权限：

```python
# 公开端点（注册/忘记密码）→ @public
# 登录后端点（个人信息/菜单）→ @auth_only
# 需要 RBAC 控制的端点 → @permission_resource + @action_*
```

### 前端对接

```typescript
// api/user/menu.ts
export function getUserMenusWithPermissionsApi() {
  return requestClient.get('/user/permissions/menus');
}
```

→ 完整规范：[user-endpoint-spec.md](user-endpoint-spec.md) § 四

---

## 五、权限树层级结构

```
菜单（Menu）
└── 资源（Resource）         ← @permission_resource("name", parent_resource="menu_name")
    ├── action:list          ← @action_read
    ├── action:create        ← @action_create
    ├── action:update        ← @action_update
    └── action:delete        ← @action_delete
```

- `parent_resource` 必须与 `admin_menus.py` / `tenant_menus.py` 中定义的菜单 `code` 完全一致
- 权限 key 格式：`{resource_name}:{action_name}`（如 `cache_management:clear`）
- i18n key 格式：`action.{resource_name}.{action_name}`（如 `action.cache_management.clear`）

---

## 五、新增 Controller 完整 Checklist

- [ ] `@permission_resource` 声明了 `parent_resource`（对照菜单 code 选择）
- [ ] `messages.json` 的 `"action"` 段中新增了对应子对象（不是新增第二个 `"action"` 顶层 key）
- [ ] 每个 `@action_*` 方法在 `messages.json` 中都有对应的翻译 key
- [ ] 如果是插件内的权限同步，使用 `sync_plugin_permissions(plugin_name)` 而非全量 `sync_permissions()`
- [ ] 修改后重启服务，在权限树页面验证新权限已出现在正确的父菜单下且显示中文名称
