"""
枚举模块

提供应用的枚举类定义
"""

from app.enums.base import BaseEnum, IntEnum, StrEnum
from app.enums.common import (
    StatusEnum,
    BoolEnum,
    GenderEnum,
    AuditStatusEnum,
    SortOrderEnum,
    OperationTypeEnum,
    PriorityEnum,
)
from app.enums.rbac import (
    PermissionType,
    PermissionScope,
)
from app.enums.role import RoleType
from app.enums.error_code import ErrorCode
from app.enums.config import ConfigScope, ConfigValueType
from app.enums.billing import BillingCycle
from app.enums.log import UserTypeEnum, LogModuleEnum, LogCategoryEnum
from app.enums.attachment import AttachmentVisibility, AttachmentStatus, AttachmentSource

__all__ = [
    # 基类
    "BaseEnum",
    "IntEnum",
    "StrEnum",
    # 通用枚举
    "StatusEnum",
    "BoolEnum",
    "GenderEnum",
    "AuditStatusEnum",
    "SortOrderEnum",
    "OperationTypeEnum",
    "PriorityEnum",
    # RBAC
    "PermissionType",
    "PermissionScope",
    # 角色/组织架构
    "RoleType",
    # 配置
    "ConfigScope",
    "ConfigValueType",
    # 计费
    "BillingCycle",
    # 日志
    "UserTypeEnum",
    "LogModuleEnum",
    "LogCategoryEnum",
    # 附件
    "AttachmentVisibility",
    "AttachmentStatus",
    "AttachmentSource",
    # 错误码
    "ErrorCode",
]
