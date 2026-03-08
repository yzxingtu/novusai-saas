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
    """统一资源作用域枚举（全平台共用：智能体、技能包、知识库、权限、配置、插件、定时任务等）

    6 种作用域覆盖所有业务场景：
      - ADMIN_ONLY:         仅管理端可见
      - ALL_TENANTS:        仅租户端可见（全部租户）
      - ADMIN_AND_ALL:      管理端 + 全部租户（全局共享）
      - ADMIN_AND_ASSIGNED: 管理端 + 部分租户（需 ResourceTenantAssignment 分配）
      - ASSIGNED_TENANTS:   部分租户（需 ResourceTenantAssignment 分配）
      - TENANT_USER:        仅用户端可见（租户业务用户）

    注意区分：本枚举是「资源作用域」，与以下概念无关：
      - JWT Token Scope (TOKEN_SCOPE_ADMIN 等) — 认证身份标识
      - ASGI Scope (Starlette.types.Scope) — HTTP 请求元数据
      - BaseRepository._scope_fields — API 端字段过滤标识
    """

    ADMIN_ONLY = ("admin_only", "enum.scope.admin_only")
    ALL_TENANTS = ("all_tenants", "enum.scope.all_tenants")
    ADMIN_AND_ALL = ("admin_and_all", "enum.scope.admin_and_all")
    ADMIN_AND_ASSIGNED = ("admin_and_assigned", "enum.scope.admin_and_assigned")
    ASSIGNED_TENANTS = ("assigned_tenants", "enum.scope.assigned_tenants")
    TENANT_USER = ("tenant_user", "enum.scope.tenant_user")


class SkillBindModeEnum(LabeledStrEnum):
    """技能包绑定模式枚举

    控制技能包如何绑定到智能体：
      - AUTO:   自动绑定 — 按 scope 匹配规则自动对所有匹配的 Agent 生效，无需 AgentSkillBinding 记录
      - MANUAL: 手动绑定 — 需通过 AgentSkillBinding 显式绑定（默认）
    """

    AUTO = ("auto", "enum.skill_bind_mode.auto")
    MANUAL = ("manual", "enum.skill_bind_mode.manual")


class ApprovalStatusEnum(LabeledStrEnum):
    """用户审批状态枚举"""

    PENDING = ("pending", "enum.approval_status.pending")
    APPROVED = ("approved", "enum.approval_status.approved")
    REJECTED = ("rejected", "enum.approval_status.rejected")


class DeleteLevelEnum(LabeledStrEnum):
    """删除层级枚举（两级回收站）"""

    TENANT = ("tenant", "enum.delete_level.tenant")
    ADMIN = ("admin", "enum.delete_level.admin")


class UserRoleEnum(LabeledStrEnum):
    """用户角色枚举"""

    PLATFORM_ADMIN = ("platform_admin", "enum.user_role.platform_admin")
    TENANT_ADMIN = ("tenant_admin", "enum.user_role.tenant_admin")
    TENANT_USER = ("tenant_user", "enum.user_role.tenant_user")


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
]
