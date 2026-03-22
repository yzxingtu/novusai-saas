"""
User Menu Definitions
用户端菜单定义

Defines directory menu structure for tenant business user; leaf menus declared via controller decorators.
定义企业业务用户端的目录型菜单结构，叶子菜单通过控制器装饰器声明。

Menu hierarchy example / 菜单层级示例:
- Home / 首页 (legacy dashboard resource code)
- Agents / 智能体广场
- AI Chat / AI 对话 (ai_chat)
- Help / 帮助中心
- Settings / 设置 (settings)

The name field uses i18n keys, translated during frontend rendering.
name 字段使用 i18n key，前端渲染时翻译。
Format / 格式: menu.user.{resource}

Icon spec / 图标规范:
Uses Lucide icon library / 使用 Lucide 图标库: https://lucide.dev/icons
Format / 格式: "lucide:{icon-name}"
Icon names use kebab-case / 图标名称使用 kebab-case
"""

from app.enums.rbac import PermissionScope, PermissionType
from app.rbac.decorators import PermissionMeta

# User directory menus / 用户端目录菜单
USER_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # Home (legacy dashboard resource code, canonical route=/) / 首页（保留 dashboard 资源码，规范路由=/）
    # ========================================
    PermissionMeta(
        code="menu:user.dashboard",
        name="menu.user.dashboard",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.dashboard",
        icon="lucide:home",
        path="/",
        component="user/home/Index",
        sort_order=0,
    ),

    # ========================================
    # Agents / 智能体广场
    # ========================================
    PermissionMeta(
        code="menu:user.agents",
        name="menu.user.agents",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.agents",
        icon="lucide:sparkles",
        path="/agents",
        component="user/agents/Index",
        sort_order=50,
    ),

    # ========================================
    # AI Chat / AI 对话
    # ========================================
    PermissionMeta(
        code="menu:user.ai_chat",
        name="menu.user.ai_chat",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.ai_chat",
        icon="lucide:bot",
        path="/ai-chat",
        component="user/ai-chat/Index",
        sort_order=100,
    ),

    # ========================================
    # Help / 帮助中心
    # ========================================
    PermissionMeta(
        code="menu:user.help",
        name="menu.user.help",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.help",
        icon="lucide:life-buoy",
        path="/help",
        component="user/help/Index",
        sort_order=150,
    ),

    # ========================================
    # Settings (directory) / 设置（目录）
    # ========================================
    PermissionMeta(
        code="menu:user.settings",
        name="menu.user.settings",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.settings",
        icon="lucide:settings",
        path="/settings",
        sort_order=900,
    ),

    # ---- Profile / 个人资料 ----
    PermissionMeta(
        code="menu:user.profile",
        name="menu.user.profile",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.profile",
        icon="lucide:user",
        path="/settings/profile",
        component="user/profile/Index",
        parent_code="menu:user.settings",
        sort_order=10,
    ),

    # ---- Change Password / 修改密码 ----
    PermissionMeta(
        code="menu:user.change_password",
        name="menu.user.change_password",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.change_password",
        icon="lucide:key-round",
        path="/settings/password",
        component="user/profile/change-password",
        parent_code="menu:user.settings",
        sort_order=20,
        hidden=True,
    ),
]

__all__ = ["USER_DIRECTORY_MENUS"]
