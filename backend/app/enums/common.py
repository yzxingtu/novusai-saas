"""
通用枚举模块 / Common Enum Module

定义系统通用的状态枚举
Defines common system status enums.
"""

from app.enums.base import IntEnum, LabeledStrEnum, StrEnum


class StatusEnum(IntEnum):
    """通用状态枚举 / Common Status Enum"""

    INACTIVE = (0, "enum.status.inactive")
    ACTIVE = (1, "enum.status.active")


class BoolEnum(IntEnum):
    """布尔枚举（用于数据库存储） / Boolean Enum (for DB storage)"""

    NO = (0, "enum.bool.no")
    YES = (1, "enum.bool.yes")


class GenderEnum(IntEnum):
    """性别枚举 / Gender Enum"""

    UNKNOWN = (0, "enum.gender.unknown")
    MALE = (1, "enum.gender.male")
    FEMALE = (2, "enum.gender.female")


class AuditStatusEnum(IntEnum):
    """审核状态枚举 / Audit Status Enum"""

    PENDING = (0, "enum.audit.pending")
    APPROVED = (1, "enum.audit.approved")
    REJECTED = (2, "enum.audit.rejected")


class SortOrderEnum(StrEnum):
    """排序方向枚举 / Sort Direction Enum"""

    ASC = ("asc", "enum.sort.asc")
    DESC = ("desc", "enum.sort.desc")


class OperationTypeEnum(StrEnum):
    """操作类型枚举（用于日志记录） / Operation Type Enum (for audit logging)"""

    CREATE = ("create", "enum.operation.create")
    UPDATE = ("update", "enum.operation.update")
    DELETE = ("delete", "enum.operation.delete")
    QUERY = ("query", "enum.operation.query")
    LOGIN = ("login", "enum.operation.login")
    LOGOUT = ("logout", "enum.operation.logout")
    EXPORT = ("export", "enum.operation.export")
    IMPORT = ("import", "enum.operation.import")


class PriorityEnum(IntEnum):
    """优先级枚举 / Priority Enum"""

    LOW = (1, "enum.priority.low")
    MEDIUM = (2, "enum.priority.medium")
    HIGH = (3, "enum.priority.high")
    URGENT = (4, "enum.priority.urgent")


class ResourceScopeEnum(LabeledStrEnum):
    """统一资源作用域枚举 / Unified Resource Scope Enum

    仅描述「资源」在管理端与企业端的投放范围，与 RBAC 权限端别、JWT、ASGI 无关。
    Describes resource visibility only; not RBAC endpoint, not JWT, not ASGI.

    五类 / Five scopes:
      - GLOBAL_SHARED:                 管理端 + 全部企业可用 / Admin + all tenants
      - ADMIN_ONLY:                    仅管理端可用 / Admin only
      - ALL_TENANTS:                   全部企业可用（管理端业务不消费）/ All tenants (tenant-side consumption)
      - ADMIN_AND_SELECTED_TENANTS:    管理端 + 指定企业 / Admin + selected tenants (assignments)
      - SELECTED_TENANTS:              仅指定企业 / Selected tenants only (assignments)
    """

    GLOBAL_SHARED = ("global_shared", "enum.scope.global_shared")
    ADMIN_ONLY = ("admin_only", "enum.scope.admin_only")
    ALL_TENANTS = ("all_tenants", "enum.scope.all_tenants")
    ADMIN_AND_SELECTED_TENANTS = (
        "admin_and_selected_tenants",
        "enum.scope.admin_and_selected_tenants",
    )
    SELECTED_TENANTS = ("selected_tenants", "enum.scope.selected_tenants")


class SkillBindModeEnum(LabeledStrEnum):
    """技能包绑定模式枚举 / Skill Bind Mode Enum

    控制技能包如何绑定到智能体 / Controls how skill packages bind to agents:
      - AUTO:   自动绑定 / Auto-bind by scope matching rules, no AgentSkillBinding needed
      - MANUAL: 手动绑定 / Manual bind via AgentSkillBinding (default)
    """

    AUTO = ("auto", "enum.skill_bind_mode.auto")
    MANUAL = ("manual", "enum.skill_bind_mode.manual")


class ApprovalStatusEnum(LabeledStrEnum):
    """用户审批状态枚举 / User Approval Status Enum"""

    PENDING = ("pending", "enum.approval_status.pending")
    APPROVED = ("approved", "enum.approval_status.approved")
    REJECTED = ("rejected", "enum.approval_status.rejected")


class DeleteLevelEnum(LabeledStrEnum):
    """删除层级枚举（两级回收站） / Delete Level Enum (two-tier recycle bin)"""

    TENANT = ("tenant", "enum.delete_level.tenant")
    ADMIN = ("admin", "enum.delete_level.admin")


class UserRoleEnum(LabeledStrEnum):
    """用户角色枚举 / User Role Enum"""

    PLATFORM_ADMIN = ("platform_admin", "enum.user_role.platform_admin")
    TENANT_ADMIN = ("tenant_admin", "enum.user_role.tenant_admin")
    TENANT_USER = ("tenant_user", "enum.user_role.tenant_user")


class AudienceEnum(LabeledStrEnum):
    """目标受众枚举（三端隔离） / Target Audience Enum (three-endpoint isolation)

    控制智能体和技能包的可见端 / Controls agent and skill package visibility:
      - ALL:          所有端可见 / Visible to all (admin + tenant + user)
      - ADMIN_ONLY:   仅管理端可见 / Admin panel only
      - ADMIN_TENANT: 管理端 + 企业端可见（默认） / Admin + tenant (default)
    """

    ALL = ("all", "enum.audience.all")
    ADMIN_ONLY = ("admin_only", "enum.audience.admin_only")
    ADMIN_TENANT = ("admin_tenant", "enum.audience.admin_tenant")


__all__ = [
    "StatusEnum",
    "BoolEnum",
    "GenderEnum",
    "AuditStatusEnum",
    "SortOrderEnum",
    "OperationTypeEnum",
    "PriorityEnum",
    "ResourceScopeEnum",
    "SkillBindModeEnum",
    "ApprovalStatusEnum",
    "DeleteLevelEnum",
    "UserRoleEnum",
    "AudienceEnum",
]
