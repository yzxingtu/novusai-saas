"""
Menu Definition Module
菜单定义模块

Centrally manages platform and tenant directory menu definitions.
集中管理平台端和租户端的目录型菜单定义。

Directory menus (no actual API) are defined here; leaf menus (with actual API)
are declared via controller's @permission_resource decorator.
目录型菜单（无实际 API）在此定义，叶子菜单（有实际 API）通过控制器的
@permission_resource 装饰器声明。

Usage / 使用方式:
    from app.rbac.menus import register_directory_menus

    # Called on app startup / 在应用启动时调用
    register_directory_menus()
"""

from app.rbac.menus.admin_menus import ADMIN_DIRECTORY_MENUS
from app.rbac.menus.tenant_menus import TENANT_DIRECTORY_MENUS
from app.rbac.menus.user_menus import USER_DIRECTORY_MENUS
from app.rbac.registry import permission_registry


def register_directory_menus() -> int:
    """
    Register all directory menus.
    注册所有目录菜单。

    Registers platform, tenant, and user directory menus to the permission registry.
    Should be called before controllers are imported, ensuring parent menus registered before children.
    将平台、租户、用户端的目录菜单统一注册到权限注册中心。
    应在控制器导入之前调用，确保父菜单先于子菜单注册。

    Returns:
        Number of registered menus / 注册的菜单数量
    """
    count = 0

    # Platform admin directory menus / 平台管理端目录菜单
    for menu in ADMIN_DIRECTORY_MENUS:
        permission_registry.register(menu)
        count += 1

    # Tenant directory menus / 租户端目录菜单
    for menu in TENANT_DIRECTORY_MENUS:
        permission_registry.register(menu)
        count += 1

    # User directory menus / 用户端目录菜单
    for menu in USER_DIRECTORY_MENUS:
        permission_registry.register(menu)
        count += 1

    return count


# Export all menu definitions (for external access) / 导出所有菜单定义（用于外部访问）
ALL_DIRECTORY_MENUS = ADMIN_DIRECTORY_MENUS + TENANT_DIRECTORY_MENUS + USER_DIRECTORY_MENUS


__all__ = [
    "ADMIN_DIRECTORY_MENUS",
    "TENANT_DIRECTORY_MENUS",
    "USER_DIRECTORY_MENUS",
    "ALL_DIRECTORY_MENUS",
    "register_directory_menus",
]
