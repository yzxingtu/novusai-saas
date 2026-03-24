"""
Platform Admin Menu Definitions
平台管理端菜单定义

Defines directory menu structure for platform admin backend; leaf menus declared via controller decorators.
定义平台管理后台的目录型菜单结构，叶子菜单通过控制器装饰器声明。

Menu hierarchy example / 菜单层级示例:
- Dashboard / 仪表板 (dashboard)
- Permission Management / 权限管理 (system)
  ├── User Management / 用户管理 (admin_user) - declared by controller / 由控制器声明
  └── Role Management / 角色管理 (role) - declared by controller / 由控制器声明
- Tenant Management / 企业管理 (tenant_mgmt)
  └── Tenant List / 企业列表 (tenant) - declared by controller / 由控制器声明

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
from app.rbac.decorators import PermissionMeta

# Platform admin directory menus / 平台管理端目录菜单
ADMIN_DIRECTORY_MENUS: list[PermissionMeta] = [
    # ========================================
    # Dashboard (homepage, leaf menu) / 仪表板（首页，叶子菜单）
    # ========================================
    PermissionMeta(
        code="menu:admin.dashboard",
        name="menu.admin.dashboard",  # i18n key / 国际化键名
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
    # Permission Management (directory) / 权限管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.system",
        name="menu.admin.system",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.system",
        icon="lucide:settings",
        path="/system",
        sort_order=10,
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.admin_user (User Management / 用户管理)
    # - menu:admin.permission (Permission Management / 权限管理) - optional, usually hidden / 可选，一般隐藏
    # - menu:admin.organization (Organization / 组织架构) - declared by roles.py / 由 roles.py 声明

    # ========================================
    # Tenant Management (directory) / 企业管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.tenant_mgmt",
        name="menu.admin.tenant_mgmt",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.tenant_mgmt",
        icon="lucide:building-2",
        path="/tenant",
        sort_order=20,
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.tenant (Tenant List / 企业列表)

    # ========================================
    # System Management (directory) / 系统管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.system_mgmt",
        name="menu.admin.system_mgmt",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.system_mgmt",
        icon="lucide:wrench",
        path="/system-mgmt",
        sort_order=80,
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.platform_config (Platform Config / 平台配置)
    # - menu:admin.global_preferences (Global Preferences / 偏好设置) — declared below / 下方声明

    # ---- Global Preferences (leaf menu) / 偏好设置（叶子菜单） ----
    PermissionMeta(
        code="menu:admin.global_preferences",
        name="menu.admin.global_preferences",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.global_preferences",
        icon="lucide:palette",
        path="/system-mgmt/preferences",
        component="system/preferences/index",
        sort_order=20,
        parent_code="menu:admin.system_mgmt",
    ),

    # ========================================
    # AI Management (directory) / AI 管理（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.ai_mgmt",
        name="menu.admin.ai_mgmt",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.ai_mgmt",
        icon="lucide:brain-circuit",
        path="/ai",
        sort_order=30,
    ),

    # ---- Infrastructure (sub-directory) / 基础设施（子目录） ----
    PermissionMeta(
        code="menu:admin.ai_infra",
        name="menu.admin.ai_infra",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.ai_infra",
        icon="lucide:server",
        path="/ai/infra",
        sort_order=10,
        parent_code="menu:admin.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.ai_provider (Provider Management / 供应商管理)
    # - menu:admin.ai_model (Model Management / 模型管理)
    # - menu:admin.ai_api_key (API Key Management / API Key 管理)
    # - menu:admin.ai_health (Health Status / 健康状态)

    # ---- AI Apps (sub-directory, unified name with tenant) / 智能应用（子目录，与企业端统一名称） ----
    PermissionMeta(
        code="menu:admin.ai_app",
        name="menu.admin.ai_app",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.ai_app",
        icon="lucide:bot",
        path="/ai/app",
        sort_order=20,
        parent_code="menu:admin.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.ai_agent (Agent Management / 智能体管理)
    # - menu:admin.ai_tool (Tool Management / 工具管理)
    # - menu:admin.ai_knowledge_base (Knowledge Base / 知识库)
    # - menu:admin.admin_agent_chat (AI Chat / AI 对话)

    # ---- Data Analytics (sub-directory, unified name with tenant) / 数据分析（子目录，与企业端统一名称） ----
    PermissionMeta(
        code="menu:admin.ai_ops",
        name="menu.admin.ai_ops",  # i18n key / 国际化键名
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.ai_ops",
        icon="lucide:bar-chart-3",
        path="/ai/ops",
        sort_order=30,
        parent_code="menu:admin.ai_mgmt",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.ai_quota (Quota Management / 配额管理)
    # - menu:admin.ai_usage (Usage Statistics / 用量统计)
    # - menu:admin.ai_call_log (Call Log / 调用日志)
    # - menu:admin.ai_conversation (Conversation Management / 对话管理)
    # - menu:admin.ai_action_log (Action Audit / 操作审计)
    # - menu:admin.ai_platform_tool (Platform Tools / 平台工具)

    # ========================================
    # System Maintenance (directory) / 系统维护（目录）
    # ========================================
    PermissionMeta(
        code="menu:admin.system_maintenance",
        name="menu.admin.system_maintenance",
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.system_maintenance",
        icon="lucide:hard-drive",
        path="/system-maintenance",
        sort_order=90,
    ),

    # ---- Log Center (sub-directory) / 日志中心（子目录） ----
    PermissionMeta(
        code="menu:admin.logs",
        name="menu.admin.logs",
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.logs",
        icon="lucide:scroll-text",
        path="/system-maintenance/logs",
        sort_order=10,
        parent_code="menu:admin.system_maintenance",
    ),
    # Child menus declared by controllers / 子菜单由控制器声明:
    # - menu:admin.operation_log (Operation Log / 操作日志)
    # - menu:admin.system_log (System Log / 系统日志)
    # - menu:admin.task_log (Task Log / 任务日志)
    # - menu:admin.email_log (Email Log / 邮件日志)

    # Other child menus declared by controllers / 其他子菜单由控制器声明:
    # - menu:admin.periodic_task (Periodic Task / 定时任务)
    # - menu:admin.plugin (Plugin Management / 插件管理)
    # - menu:admin.recycle_bin (Recycle Bin / 回收站)

]


__all__ = ["ADMIN_DIRECTORY_MENUS"]
