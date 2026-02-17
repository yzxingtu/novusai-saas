"""
通用枚举模块

定义系统通用的状态枚举
"""

from app.enums.base import IntEnum, LabeledStrEnum, StrEnum


class StatusEnum(IntEnum):
    """通用状态枚举"""
    
    INACTIVE = (0, "enum.status.inactive")
    ACTIVE = (1, "enum.status.active")


class BoolEnum(IntEnum):
    """布尔枚举（用于数据库存储）"""
    
    NO = (0, "enum.bool.no")
    YES = (1, "enum.bool.yes")


class GenderEnum(IntEnum):
    """性别枚举"""
    
    UNKNOWN = (0, "enum.gender.unknown")
    MALE = (1, "enum.gender.male")
    FEMALE = (2, "enum.gender.female")


class AuditStatusEnum(IntEnum):
    """审核状态枚举"""
    
    PENDING = (0, "enum.audit.pending")
    APPROVED = (1, "enum.audit.approved")
    REJECTED = (2, "enum.audit.rejected")


class SortOrderEnum(StrEnum):
    """排序方向枚举"""
    
    ASC = ("asc", "enum.sort.asc")
    DESC = ("desc", "enum.sort.desc")


class OperationTypeEnum(StrEnum):
    """操作类型枚举（用于日志记录）"""
    
    CREATE = ("create", "enum.operation.create")
    UPDATE = ("update", "enum.operation.update")
    DELETE = ("delete", "enum.operation.delete")
    QUERY = ("query", "enum.operation.query")
    LOGIN = ("login", "enum.operation.login")
    LOGOUT = ("logout", "enum.operation.logout")
    EXPORT = ("export", "enum.operation.export")
    IMPORT = ("import", "enum.operation.import")


class PriorityEnum(IntEnum):
    """优先级枚举"""
    
    LOW = (1, "enum.priority.low")
    MEDIUM = (2, "enum.priority.medium")
    HIGH = (3, "enum.priority.high")
    URGENT = (4, "enum.priority.urgent")


class ResourceScopeEnum(LabeledStrEnum):
    """资源作用域枚举（知识库、智能体等共用）"""

    TENANT = ("tenant", "enum.resource_scope.tenant")
    GLOBAL = ("global", "enum.resource_scope.global")
    ADMIN = ("admin", "enum.resource_scope.admin")


class DeleteLevelEnum(LabeledStrEnum):
    """删除层级枚举（两级回收站）"""

    TENANT = ("tenant", "enum.delete_level.tenant")
    ADMIN = ("admin", "enum.delete_level.admin")


class UserRoleEnum(LabeledStrEnum):
    """用户角色枚举"""

    PLATFORM_ADMIN = ("platform_admin", "enum.user_role.platform_admin")
    TENANT_ADMIN = ("tenant_admin", "enum.user_role.tenant_admin")


__all__ = [
    "StatusEnum",
    "BoolEnum",
    "GenderEnum",
    "AuditStatusEnum",
    "SortOrderEnum",
    "OperationTypeEnum",
    "PriorityEnum",
    "ResourceScopeEnum",
    "DeleteLevelEnum",
    "UserRoleEnum",
]
