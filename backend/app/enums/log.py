"""
日志相关枚举模块

定义操作日志所需的枚举类型
"""

from app.enums.base import StrEnum


class UserTypeEnum(StrEnum):
    """
    用户类型枚举
    
    标识操作日志中的用户来源
    """
    
    # 平台管理员
    ADMIN = ("admin", "enum.user_type.admin")
    # 租户管理员
    TENANT_ADMIN = ("tenant_admin", "enum.user_type.tenant_admin")
    # 租户用户
    TENANT_USER = ("tenant_user", "enum.user_type.tenant_user")
    # 匿名用户（未登录）
    ANONYMOUS = ("anonymous", "enum.user_type.anonymous")


class LogModuleEnum(StrEnum):
    """
    业务模块枚举
    
    标识操作日志中的业务模块分类
    """
    
    # 认证模块
    AUTH = ("auth", "enum.log_module.auth")
    # 权限模块
    PERMISSION = ("permission", "enum.log_module.permission")
    # 角色模块
    ROLE = ("role", "enum.log_module.role")
    # 平台管理员模块
    ADMIN_USER = ("admin_user", "enum.log_module.admin_user")
    # 租户模块
    TENANT = ("tenant", "enum.log_module.tenant")
    # 租户管理员模块
    TENANT_ADMIN = ("tenant_admin", "enum.log_module.tenant_admin")
    # 租户用户模块
    TENANT_USER = ("tenant_user", "enum.log_module.tenant_user")
    # 配置模块
    CONFIG = ("config", "enum.log_module.config")
    # 套餐模块
    PLAN = ("plan", "enum.log_module.plan")
    # 域名模块
    DOMAIN = ("domain", "enum.log_module.domain")
    # 日志模块
    LOG = ("log", "enum.log_module.log")
    # 组织架构模块
    ORGANIZATION = ("organization", "enum.log_module.organization")
    # 系统模块
    SYSTEM = ("system", "enum.log_module.system")
    # 其他/未分类
    OTHER = ("other", "enum.log_module.other")


class LogCategoryEnum(StrEnum):
    """
    系统日志分类枚举
    
    用于文件日志的分类管理
    """
    
    # 应用日志
    APP = ("app", "enum.log_category.app")
    # 错误日志
    ERROR = ("error", "enum.log_category.error")
    # 数据库日志
    DB = ("db", "enum.log_category.db")
    # 计划任务日志
    TASK = ("task", "enum.log_category.task")
    # 队列日志
    QUEUE = ("queue", "enum.log_category.queue")


__all__ = [
    "UserTypeEnum",
    "LogModuleEnum",
    "LogCategoryEnum",
]
