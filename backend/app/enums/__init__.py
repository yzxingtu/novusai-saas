"""
枚举模块 / Enum Module

提供应用的枚举类定义
Provides application enum class definitions.
"""

from app.enums.agent import (
    AccessTypeEnum,
    AgentExecutionModeEnum,
    AgentStatusEnum,
    AgentVisibilityEnum,
    BatchRunStatusEnum,
    ConversationStatusEnum,
    MessageRoleEnum,
    SkillTypeEnum,
    ToolTypeEnum,
)
from app.enums.ai import ToolParameterTypeEnum
from app.enums.attachment import (
    AttachmentSource,
    AttachmentStatus,
    AttachmentVisibility,
)
from app.enums.base import BaseEnum, IntEnum, StrEnum
from app.enums.billing import BillingCycle
from app.enums.codegen import CodegenConfigStatusEnum
from app.enums.cache import CacheCategoryEnum
from app.enums.common import (
    ApprovalStatusEnum,
    AudienceEnum,
    AuditStatusEnum,
    BoolEnum,
    DeleteLevelEnum,
    GenderEnum,
    OperationTypeEnum,
    PriorityEnum,
    ResourceScopeEnum,
    SkillBindModeEnum,
    SortOrderEnum,
    StatusEnum,
    UserRoleEnum,
)
from app.enums.config import ConfigScope, ConfigValueType
from app.enums.domain import DomainSslStatus, DomainType, SslCertStatus, SslCertType
from app.enums.error_code import ErrorCode
from app.enums.knowledge_base import (
    ChunkStrategyEnum,
    DocumentStatusEnum,
    DocumentTypeEnum,
    KBStatusEnum,
    RewriteStrategyEnum,
    SearchModeEnum,
)
from app.enums.log import LogCategoryEnum, LogModuleEnum, UserTypeEnum
from app.enums.plugin import (
    PluginInstallSourceEnum,
    PluginLicenseTypeEnum,
    PluginPricingTypeEnum,
    PluginStatusEnum,
    PluginTierEnum,
    PluginVersionStatusEnum,
)
from app.enums.rbac import (
    PermissionScope,
    PermissionType,
)
from app.enums.role import RoleType
from app.enums.task import ScheduleTypeEnum, TaskStatusEnum

__all__ = [
    # 基类 / Base Classes
    "BaseEnum",
    "IntEnum",
    "StrEnum",
    # 通用枚举 / Common Enums
    "StatusEnum",
    "BoolEnum",
    "GenderEnum",
    "AuditStatusEnum",
    "ApprovalStatusEnum",
    "SortOrderEnum",
    "OperationTypeEnum",
    "PriorityEnum",
    "ResourceScopeEnum",
    "SkillBindModeEnum",
    "DeleteLevelEnum",
    "UserRoleEnum",
    "AudienceEnum",
    # RBAC 权限 / RBAC Permissions
    "PermissionType",
    "PermissionScope",
    # 角色/组织架构 / Role/Organization
    "RoleType",
    # 配置 / Configuration
    "ConfigScope",
    "ConfigValueType",
    # 计费 / Billing
    "BillingCycle",
    # 代码生成器 / Codegen
    "CodegenConfigStatusEnum",
    # 日志 / Logging
    "UserTypeEnum",
    "LogModuleEnum",
    "LogCategoryEnum",
    # 附件 / Attachment
    "AttachmentVisibility",
    "AttachmentStatus",
    "AttachmentSource",
    # 错误码 / Error Codes
    "ErrorCode",
    # 任务 / Tasks
    "TaskStatusEnum",
    "ScheduleTypeEnum",
    # 智能体 / Agent
    "AgentStatusEnum",
    "AgentExecutionModeEnum",
    "ToolTypeEnum",
    "SkillTypeEnum",
    "ConversationStatusEnum",
    "MessageRoleEnum",
    "AgentVisibilityEnum",
    "AccessTypeEnum",
    "BatchRunStatusEnum",
    # AI / AI 相关
    "ToolParameterTypeEnum",
    # 域名 / Domain
    "DomainSslStatus",
    "DomainType",
    "SslCertType",
    "SslCertStatus",
    # 知识库 / Knowledge Base
    "KBStatusEnum",
    "DocumentStatusEnum",
    "DocumentTypeEnum",
    "ChunkStrategyEnum",
    "SearchModeEnum",
    "RewriteStrategyEnum",
    # 缓存 / Cache
    "CacheCategoryEnum",
    # 插件 / Plugin
    "PluginStatusEnum",
    "PluginTierEnum",
    "PluginInstallSourceEnum",
    "PluginPricingTypeEnum",
    "PluginLicenseTypeEnum",
    "PluginVersionStatusEnum",
]
