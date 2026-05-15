"""
Tenant Admin Menu Definitions
企业管理端菜单定义

Defines directory menu structure for tenant admin backend; leaf menus declared via controller decorators.
定义企业管理后台的目录型菜单结构，叶子菜单通过控制器装饰器声明。

Menu hierarchy example / 菜单层级示例:
- Dashboard / 仪表板 (dashboard)
- Permission Management / 权限管理 (system)
  ├── User Architecture / 用户架构 (user_architecture) - declared by user_roles.py / 由 user_roles.py 声明
  └── Organization / 组织架构 (organization) - declared by roles.py / 由 roles.py 声明
- Business Management / 业务管理 (business) - reserved, child menus by business controllers / 预留

The name field uses i18n keys, translated during frontend rendering.
name 字段使用 i18n key，前端渲染时翻译。
Format / 格式: menu.{scope}.{resource}

Icon spec / 图标规范:
Uses Lucide icon library / 使用 Lucide 图标库: https://lucide.dev/icons
Format / 格式: "lucide:{icon-name}"
Examples / 示例: "lucide:settings", "lucide:users", "lucide:layout-dashboard"
Icon names use kebab-case / 图标名称使用 kebab-case
"""

from app.enums.rbac import PermissionScope, PermissionType
from app.rbac.decorators import MenuAIConfig, PermissionMeta

# Tenant admin directory menus / 企业管理端目录菜单
TENANT_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # Dashboard (homepage, leaf menu) / 仪表板（首页，叶子菜单）
    # ========================================
    PermissionMeta(
        code="menu:tenant.dashboard",
        name="menu.tenant.dashboard",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.dashboard",
        icon="lucide:layout-dashboard",
        path="/dashboard",
        component="dashboard/Index",
        sort_order=0,
        ai=MenuAIConfig(
            description="View the current tenant overview, key metrics, and quick entry points",
            keywords=["控制台", "首页", "dashboard", "overview", "总览"],
            capabilities=["view_dashboard", "check_metrics"],
            category="dashboard",
        ),
    ),
    # ========================================
    # Workspace (directory, for content/doc plugin mounting) / 工作台（目录，供内容/文档类插件挂载）
    # ========================================
    PermissionMeta(
        code="menu:tenant.tenant_workspace",
        name="menu.tenant.tenant_workspace",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.tenant_workspace",
        icon="lucide:layout-panel-left",
        path="/workspace",
        sort_order=5,
    ),
    # Child menus declared by plugins / 子菜单由插件声明:
    # - menu:tenant.plugin_novusdoc_* (Document Management / 文档管理)
    # ========================================
    # Permission Management (directory) / 权限管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.system",
        name="menu.tenant.system",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.system",
        icon="lucide:settings",
        path="/system",
        sort_order=10,
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.user_architecture (User Architecture / 用户架构) - declared by user_roles.py / 由 user_roles.py 声明
    # - menu:tenant.organization (Organization / 组织架构) - declared by roles.py / 由 roles.py 声明
    # permission 控制器无菜单，仅 API / permission controller has no menu
    # tenant_user 无独立菜单（权限挂在用户架构等页面）/ tenant_user has no menu entry
    # ========================================
    # System Management (directory) / 系统管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.system_mgmt",
        name="menu.tenant.system_mgmt",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.system_mgmt",
        icon="lucide:wrench",
        path="/system-mgmt",
        sort_order=20,
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.tenant_config — configs.py
    # - menu:tenant.tenant_domain — domains.py
    # - menu:tenant.attachment — attachments.py
    # - menu:tenant.global_preferences — 下方静态声明
    # ---- Global Preferences (leaf menu) / 偏好设置（叶子菜单） ----
    PermissionMeta(
        code="menu:tenant.global_preferences",
        name="menu.tenant.global_preferences",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.global_preferences",
        icon="lucide:palette",
        path="/system-mgmt/preferences",
        component="system/preferences/index",
        sort_order=20,
        parent_code="menu:tenant.system_mgmt",
        ai=MenuAIConfig(
            description="Manage global preferences, system settings, and UI behavior",
            keywords=["偏好设置", "系统设置", "preferences", "settings", "config"],
            capabilities=["view_settings", "edit_settings"],
            category="settings",
        ),
    ),
    # ========================================
    # AI Management (directory) / AI 管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.ai_mgmt",
        name="menu.tenant.ai_mgmt",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.ai_mgmt",
        icon="lucide:brain-circuit",
        path="/ai",
        sort_order=25,
    ),
    # ---- AI Apps (sub-directory, unified name with admin) / 智能应用（子目录，与管理端统一名称） ----
    PermissionMeta(
        code="menu:tenant.ai_workspace",
        name="menu.tenant.ai_workspace",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.ai_workspace",
        icon="lucide:bot",
        path="/ai/workspace",
        sort_order=10,
        parent_code="menu:tenant.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.agent (Agent Management / 智能体管理)
    # - menu:tenant.agent_chat (hidden menu entry for /ai/chat / 隐藏项，路由用)
    # - menu:tenant.knowledge_base (Knowledge Base / 知识库)
    # 无独立「工具管理」菜单（工具在智能体等页面内配置）/ No standalone tool menu in core tenant UI
    # ---- Settings (sub-directory) / 设置（子目录） ----
    PermissionMeta(
        code="menu:tenant.ai_settings",
        name="menu.tenant.ai_settings",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.ai_settings",
        icon="lucide:settings",
        path="/ai/settings",
        sort_order=20,
        parent_code="menu:tenant.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.ai_config (AI Config / AI 配置)
    # - menu:tenant.ai_quota (Quota Management / 配额管理)
    # ---- Data Analytics (sub-directory, unified name with admin) / 数据分析（子目录，与管理端统一名称） ----
    PermissionMeta(
        code="menu:tenant.ai_analytics",
        name="menu.tenant.ai_analytics",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.ai_analytics",
        icon="lucide:bar-chart-3",
        path="/ai/analytics",
        sort_order=30,
        parent_code="menu:tenant.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.ai_usage (Usage Statistics / 用量统计)
    # - menu:tenant.ai_call_log (Call Log / 调用日志)
    # - menu:tenant.agent_conversation (Conversation Management / 对话管理)
    # 中文: 独立 AI 操作审计页面已退役；操作证据账本仍继续保留。
    # EN: The standalone AI action-audit page is retired; the action ledger remains retained.
    # ========================================
    # System Maintenance (directory) / 系统维护（目录）
    # ========================================
    PermissionMeta(
        code="menu:tenant.system_maintenance",
        name="menu.tenant.system_maintenance",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.system_maintenance",
        icon="lucide:hard-drive",
        path="/system-maintenance",
        sort_order=30,
    ),
    # ---- Log Center (sub-directory) / 日志中心（子目录） ----
    PermissionMeta(
        code="menu:tenant.logs",
        name="menu.tenant.logs",
        type=PermissionType.MENU,
        scope=PermissionScope.TENANT,
        resource="menu",
        action="tenant.logs",
        icon="lucide:scroll-text",
        path="/system-maintenance/logs",
        sort_order=10,
        parent_code="menu:tenant.system_maintenance",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:tenant.operation_log (Operation Log / 操作日志)
    # - menu:tenant.task_log (Task Log / 任务日志)
    # Other child menus declared by controllers / 其他子菜单由控制器声明:
    # - menu:tenant.periodic_task (Periodic Task / 定时任务)
    # ========================================
    # Business Management (directory, reserved) / 业务管理（目录，预留）
    # ========================================
    # PermissionMeta(
    #     code="menu:tenant.business",
    #     name="menu.tenant.business",  # i18n key / 国际化键名
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
