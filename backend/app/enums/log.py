"""
日志相关枚举模块 / Logging Enum Module

定义操作日志所需的枚举类型
Defines enum types for audit/operation logging.
"""

from app.enums.base import StrEnum


class UserTypeEnum(StrEnum):
    """
    User Type Enum / 用户类型枚举

    Identifies user source in audit logs / 标识操作日志中的用户来源
    """

    # Platform admin / 平台管理员
    ADMIN = ("admin", "enum.user_type.admin")
    # Tenant admin / 企业管理员
    TENANT_ADMIN = ("tenant_admin", "enum.user_type.tenant_admin")
    # Tenant user / 企业用户
    TENANT_USER = ("tenant_user", "enum.user_type.tenant_user")
    # Anonymous user (not logged in) / 匿名用户（未登录）
    ANONYMOUS = ("anonymous", "enum.user_type.anonymous")


class LogModuleEnum(StrEnum):
    """
    Business Module Enum / 业务模块枚举

    Identifies business module category in audit logs / 标识操作日志中的业务模块分类
    """

    # Auth module / 认证模块
    AUTH = ("auth", "enum.log_module.auth")
    # Permission module / 权限模块
    PERMISSION = ("permission", "enum.log_module.permission")
    # Role module / 角色模块
    ROLE = ("role", "enum.log_module.role")
    # Platform admin module / 平台管理员模块
    ADMIN_USER = ("admin_user", "enum.log_module.admin_user")
    # Tenant module / 企业模块
    TENANT = ("tenant", "enum.log_module.tenant")
    # Tenant admin module / 企业管理员模块
    TENANT_ADMIN = ("tenant_admin", "enum.log_module.tenant_admin")
    # Tenant user module / 企业用户模块
    TENANT_USER = ("tenant_user", "enum.log_module.tenant_user")
    # Config module / 配置模块
    CONFIG = ("config", "enum.log_module.config")
    # Plan module / 套餐模块
    PLAN = ("plan", "enum.log_module.plan")
    # Domain module / 域名模块
    DOMAIN = ("domain", "enum.log_module.domain")
    # Log module / 日志模块
    LOG = ("log", "enum.log_module.log")
    # Organization module / 组织架构模块
    ORGANIZATION = ("organization", "enum.log_module.organization")
    # System module / 系统模块
    SYSTEM = ("system", "enum.log_module.system")
    # Other / uncategorized / 其他/未分类
    OTHER = ("other", "enum.log_module.other")


class LogCategoryEnum(StrEnum):
    """
    System Log Category Enum / 系统日志分类枚举

    Used for file log category management / 用于文件日志的分类管理
    """

    # Application log / 应用日志
    APP = ("app", "enum.log_category.app")
    # Error log / 错误日志
    ERROR = ("error", "enum.log_category.error")
    # Database log / 数据库日志
    DB = ("db", "enum.log_category.db")
    # Scheduled task log / 计划任务日志
    TASK = ("task", "enum.log_category.task")
    # Queue log / 队列日志
    QUEUE = ("queue", "enum.log_category.queue")
    # Captcha log / 验证码日志
    CAPTCHA = ("captcha", "enum.log_category.captcha")
    # Storage log / 存储日志
    STORAGE = ("storage", "enum.log_category.storage")
    # Auth log / 认证日志
    AUTH = ("auth", "enum.log_category.auth")
    # Impersonate audit log / 一键登录审计日志
    IMPERSONATE = ("impersonate", "enum.log_category.impersonate")


__all__ = [
    "UserTypeEnum",
    "LogModuleEnum",
    "LogCategoryEnum",
]
