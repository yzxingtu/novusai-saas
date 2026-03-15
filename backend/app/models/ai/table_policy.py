"""
AI 表策略模型 / AI Table Policy Model

管理 AI 智能体对数据库表的访问策略：
Manages AI agent access policies for database tables:
- 表级 CRUD 权限开关
- 单次查询行数限制
- 列级可见性控制（屏蔽列 / 只读列）
- 关键词映射（辅助 LLM 精准匹配表）
- 列描述（含枚举合法值，帮助 LLM 生成正确 SQL）
"""

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel, TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _


class AITablePolicy(BaseModel):
    """
    AI 表访问策略（平台级）/ AI table access policy (platform-level).

    每张数据库表对应一条策略记录，由系统自动发现并创建，
    管理员通过管理页面调整 CRUD 开关、行数限制、列级控制。
    """

    __tablename__ = "ai_table_policies"

    __delete_deps__ = [
        DeletionDep("AITablePolicyOverride", "policy_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="table_policy_override"),
    ]

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "table_name": "table_name",
        "label": "label",
        "is_active": "is_active",
        "allow_read": "allow_read",
        "allow_create": "allow_create",
        "allow_update": "allow_update",
        "allow_delete": "allow_delete",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "table_name": "table_name",
        "label": "label",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选择配置
    __selectable__ = {
        "label": "label",
        "value": "id",
        "search": ["table_name", "label"],
    }

    # ==================== 基本信息 ====================

    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment=_("ai_table_policy.field.table_name"),
    )
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        comment=_("ai_table_policy.field.label"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("ai_table_policy.field.description"),
    )
    keywords: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("ai_table_policy.field.keywords"),
    )

    # ==================== 列级描述 ====================

    column_descriptions: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("ai_table_policy.field.column_descriptions"),
    )

    # ==================== CRUD 权限开关 ====================

    allow_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("ai_table_policy.field.allow_read"),
    )
    allow_create: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=_("ai_table_policy.field.allow_create"),
    )
    allow_update: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=_("ai_table_policy.field.allow_update"),
    )
    allow_delete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=_("ai_table_policy.field.allow_delete"),
    )

    # ==================== 查询限制 ====================

    max_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=200,
        comment=_("ai_table_policy.field.max_rows"),
    )

    # ==================== 列级控制 ====================

    blocked_columns: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("ai_table_policy.field.blocked_columns"),
    )
    readonly_columns: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("ai_table_policy.field.readonly_columns"),
    )

    # ==================== 权限 ====================

    permission_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="*",
        comment=_("ai_table_policy.field.permission_code"),
    )

    # ==================== 排序与状态 ====================

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("ai_table_policy.field.sort_order"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment=_("ai_table_policy.field.is_active"),
    )

    # ==================== 索引 ====================

    __table_args__ = (
        Index("idx_ai_table_policies_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<AITablePolicy(id={self.id}, table={self.table_name}, "
            f"active={self.is_active})>"
        )


class AITablePolicyOverride(TenantModel):
    """
    AI 表策略企业级覆盖 / AI table policy tenant override.

    允许企业管理员针对自己的企业自定义策略，覆盖全局设置。
    规则：企业只能收紧（限制更多），不能放开（超出全局策略）。
    字段为 NULL 表示使用全局策略值。
    """

    __tablename__ = "ai_table_policy_overrides"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "policy_id": "policy_id",
        "tenant_id": "tenant_id",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # ==================== 关联 ====================

    policy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_table_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("ai_table_policy_override.field.policy_id"),
    )

    # ==================== 可覆盖字段（NULL = 使用全局值） ====================

    allow_read: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=_("ai_table_policy_override.field.allow_read"),
    )
    allow_create: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=_("ai_table_policy_override.field.allow_create"),
    )
    allow_update: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=_("ai_table_policy_override.field.allow_update"),
    )
    allow_delete: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=_("ai_table_policy_override.field.allow_delete"),
    )
    max_rows: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("ai_table_policy_override.field.max_rows"),
    )
    blocked_columns: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("ai_table_policy_override.field.blocked_columns"),
    )
    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=_("ai_table_policy_override.field.is_active"),
    )

    # ==================== 约束 ====================

    __table_args__ = (
        Index(
            "uq_policy_override_tenant_policy",
            "tenant_id", "policy_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AITablePolicyOverride(id={self.id}, tenant_id={self.tenant_id}, "
            f"policy_id={self.policy_id})>"
        )


__all__ = ["AITablePolicy", "AITablePolicyOverride"]
