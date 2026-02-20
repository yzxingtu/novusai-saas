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
    ResourceScopeEnum,
    DeleteLevelEnum,
    UserRoleEnum,
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
from app.enums.task import TaskStatusEnum, ScheduleTypeEnum, TaskScopeEnum
from app.enums.agent import (
    AgentStatusEnum,
    AgentExecutionModeEnum,
    ToolTypeEnum,
    SkillTypeEnum,
    ConversationStatusEnum,
    MessageRoleEnum,
    AgentVisibilityEnum,
    AccessTypeEnum,
    BatchRunStatusEnum,
)
from app.enums.ai import ToolParameterTypeEnum
from app.enums.plugin import PluginTypeEnum, PluginStatusEnum
from app.enums.domain import DomainSslStatus, DomainType, SslCertType, SslCertStatus
from app.enums.knowledge_base import (
    KBStatusEnum,
    DocumentStatusEnum,
    DocumentTypeEnum,
    ChunkStrategyEnum,
    SearchModeEnum,
    RewriteStrategyEnum,
)

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
    # 插件
    "PluginTypeEnum",
    "PluginStatusEnum",
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
]
