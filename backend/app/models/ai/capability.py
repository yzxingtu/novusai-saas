"""
Capability model.
"""

from sqlalchemy import JSON, Boolean, Column, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.enums.agent import ToolConsentModeEnum
from app.enums.skill import CapabilityExecutorTypeEnum, CapabilityStatusEnum


class Capability(BaseModel):
    """Capability contract exposed by a Skill once activated."""

    __tablename__ = "capabilities"

    owner_tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="Owner tenant ID / 归属企业 ID",
    )

    __filterable__ = {
        "id": "id",
        "key": "key",
        "executor_type": "executor_type",
        "status": "status",
        "owner_tenant_id": "owner_tenant_id",
        "is_builtin": "is_builtin",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "key": "key",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Stable capability key / 稳定能力 Key",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name / 展示名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Capability description / 能力描述",
    )
    executor_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=CapabilityExecutorTypeEnum.BUILTIN.value,
        index=True,
        comment="Executor type / 执行器类型",
    )
    executor_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Executor reference / 执行器引用",
    )
    input_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Input schema / 输入 Schema",
    )
    output_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Output schema / 输出 Schema",
    )
    default_consent_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ToolConsentModeEnum.AUTO.value,
        comment="Default consent mode / 默认授权模式",
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Timeout seconds / 超时秒数",
    )
    security_policy: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Security policy / 安全策略",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CapabilityStatusEnum.ACTIVE.value,
        index=True,
        comment="Capability status / 能力状态",
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Builtin capability / 是否平台内置",
    )

    skill_bindings = relationship(
        "SkillCapabilityBinding",
        back_populates="capability",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_capabilities_owner_status", "owner_tenant_id", "status"),
    )


__all__ = ["Capability"]
