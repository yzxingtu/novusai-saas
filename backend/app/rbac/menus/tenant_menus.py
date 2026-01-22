"""
租户管理端菜单定义

定义租户管理后台的目录型菜单结构，叶子菜单通过控制器装饰器声明。

菜单层级示例:
- 仪表板 (dashboard)
- 权限管理 (system)
  ├── 用户管理 (tenant_user) - 由控制器声明
  └── 角色管理 (role) - 由控制器声明
- 业务管理 (business) - 预留，具体子菜单由业务控制器声明

name 字段使用 i18n key，前端渲染时翻译。
格式: menu.{scope}.{resource}

图标规范:
使用 Lucide 图标库: https://lucide.dev/icons
格式: "lucide:{icon-name}"
示例: "lucide:settings", "lucide:users", "lucide:layout-dashboard"
图标名称使用 kebab-case（小写字母，单词间用连字符分隔）
"""

from app.enums.rbac import PermissionType, PermissionScope
from app.rbac.decorators import PermissionMeta


# 租户管理端目录菜单
TENANT_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # 仪表板（首页，叶子菜单）
    # ========================================
    PermissionMeta(
        code="menu:tenant.dashboard",
        name="menu.tenant.dashboard",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.dashboard",
        icon="lucide:layout-dashboard",
        path="/dashboard",
        component="dashboard/Index",
        sort_order=0,
    ),
    
    # ========================================
    # 权限管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.system",
        name="menu.tenant.system",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.system",
        icon="lucide:settings",
        path="/system",
        sort_order=10,
    ),
    # 子菜单由控制器声明:
    # - menu:tenant.tenant_user (用户管理)
    # - menu:tenant.permission (权限管理) - 可选，一般隐藏
    # - menu:tenant.organization (组织架构) - 由 roles.py 控制器声明
    
    # ========================================
    # 系统管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.system_mgmt",
        name="menu.tenant.system_mgmt",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.system_mgmt",
        icon="lucide:wrench",
        path="/system-mgmt",
        sort_order=20,
    ),
    # 子菜单由控制器声明:
    # - menu:tenant.tenant_config (租户配置)
    # - menu:tenant.tenant_settings (租户设置)
    
    # ========================================
    # 业务管理（目录，预留）
    # ========================================
    # PermissionMeta(
    #     code="menu:tenant.business",
    #     name="menu.tenant.business",  # i18n key
    #     type=PermissionType.MENU,
    #     scope=PermissionScope.TENANT,
    #     resource="menu",
    #     action="tenant.business",
    #     icon="appstore",
    #     path="/business",
    #     sort_order=30,
    # ),
]


__all__ = ["TENANT_DIRECTORY_MENUS"]
