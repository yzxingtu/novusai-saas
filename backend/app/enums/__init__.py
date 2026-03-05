"""
枚举模块

提供应用的枚举类定义
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
from app.enums.cache import CacheCategoryEnum
from app.enums.common import (
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
    PluginScopeEnum,
    PluginStatusEnum,
    PluginTierEnum,
    PluginVersionStatusEnum,
)
from app.enums.rbac import (
    PermissionScope,
    PermissionType,
)
from app.enums.role import RoleType
from app.enums.task import ScheduleTypeEnum, TaskScopeEnum, TaskStatusEnum

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
    "ResourceScopeEnum",
    "SkillBindModeEnum",
    "DeleteLevelEnum",
    "UserRoleEnum",
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
    # 任务
    "TaskStatusEnum",
    "ScheduleTypeEnum",
    "TaskScopeEnum",
    # 智能体
    "AgentStatusEnum",
    "AgentExecutionModeEnum",
    "ToolTypeEnum",
    "SkillTypeEnum",
    "ConversationStatusEnum",
    "MessageRoleEnum",
    "AgentVisibilityEnum",
    "AccessTypeEnum",
    "BatchRunStatusEnum",
    # AI
    "ToolParameterTypeEnum",
    # 域名
    "DomainSslStatus",
    "DomainType",
    "SslCertType",
    "SslCertStatus",
    # 知识库
    "KBStatusEnum",
    "DocumentStatusEnum",
    "DocumentTypeEnum",
    "ChunkStrategyEnum",
    "SearchModeEnum",
    "RewriteStrategyEnum",
    # 缓存
    "CacheCategoryEnum",
    # 插件
    "PluginStatusEnum",
    "PluginScopeEnum",
    "PluginTierEnum",
    "PluginInstallSourceEnum",
    "PluginPricingTypeEnum",
    "PluginLicenseTypeEnum",
    "PluginVersionStatusEnum",
]
