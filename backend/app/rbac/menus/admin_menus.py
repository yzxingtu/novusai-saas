"""
平台管理端菜单定义

定义平台管理后台的目录型菜单结构，叶子菜单通过控制器装饰器声明。

菜单层级示例:
- 仪表板 (dashboard)
- 权限管理 (system)
  ├── 用户管理 (admin_user) - 由控制器声明
  └── 角色管理 (role) - 由控制器声明
- 租户管理 (tenant_mgmt)
  └── 租户列表 (tenant) - 由控制器声明

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


# 平台管理端目录菜单
ADMIN_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # 仪表板（首页，叶子菜单）
    # ========================================
    PermissionMeta(
        code="menu:admin.dashboard",
        name="menu.admin.dashboard",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.dashboard",
        icon="lucide:gauge",
        path="/dashboard",
        component="dashboard/Index",
        sort_order=0,
    ),
    
    # ========================================
    # 权限管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.system",
        name="menu.admin.system",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.system",
        icon="lucide:settings",
        path="/system",
        sort_order=10,
    ),
    # 子菜单由控制器声明:
    # - menu:admin.admin_user (用户管理)
    # - menu:admin.permission (权限管理) - 可选，一般隐藏
    # - menu:admin.organization (组织架构) - 由 roles.py 控制器声明
    
    # ========================================
    # 租户管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.tenant_mgmt",
        name="menu.admin.tenant_mgmt",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.tenant_mgmt",
        icon="lucide:building-2",
        path="/tenant",
        sort_order=20,
    ),
    # 子菜单由控制器声明:
    # - menu:admin.tenant (租户列表)
    
    # ========================================
    # 系统管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.system_mgmt",
        name="menu.admin.system_mgmt",  # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.system_mgmt",
        icon="lucide:wrench",
        path="/system-mgmt",
        sort_order=30,
    ),
    # 子菜单由控制器声明:
    # - menu:admin.platform_config (平台配置)
]


__all__ = ["ADMIN_DIRECTORY_MENUS"]
