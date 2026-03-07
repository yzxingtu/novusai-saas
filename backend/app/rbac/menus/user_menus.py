"""
用户端菜单定义

定义租户业务用户端的目录型菜单结构，叶子菜单通过控制器装饰器声明。

菜单层级示例:
- 仪表板 (dashboard)
- AI 对话 (ai_chat)
- 设置 (settings)

name 字段使用 i18n key，前端渲染时翻译。
格式: menu.user.{resource}

图标规范:
使用 Lucide 图标库: https://lucide.dev/icons
格式: "lucide:{icon-name}"
图标名称使用 kebab-case（小写字母，单词间用连字符分隔）
"""

from app.enums.rbac import PermissionScope, PermissionType
from app.rbac.decorators import PermissionMeta

# 用户端目录菜单
USER_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # 仪表板（首页，叶子菜单）
    # ========================================
    PermissionMeta(
        code="menu:user.dashboard",
        name="menu.user.dashboard",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT_USER,
        resource="menu",
        action="user.dashboard",
        icon="lucide:layout-dashboard",
        path="/dashboard",
        component="dashboard/Index",
        sort_order=0,
    ),

    # ========================================
    # AI 对话
    # ========================================
    PermissionMeta(
        code="menu:user.ai_chat",
        name="menu.user.ai_chat",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT_USER,
        resource="menu",
        action="user.ai_chat",
        icon="lucide:message-square",
        path="/ai-chat",
        component="ai-chat/Index",
        sort_order=100,
    ),

    # ========================================
    # 设置（目录）
    # ========================================
    PermissionMeta(
        code="menu:user.settings",
        name="menu.user.settings",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT_USER,
        resource="menu",
        action="user.settings",
        icon="lucide:settings",
        path="/settings",
        sort_order=900,
    ),
]

__all__ = ["USER_DIRECTORY_MENUS"]
