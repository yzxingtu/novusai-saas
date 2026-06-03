"""
用户偏好设置模型 / User Preference Model

分层偏好体系：全局偏好 → 个人覆盖，支持管理端和企业端双轨道。
Layered preference system: global preferences -> individual overrides,
supporting both admin and tenant sides.
"""

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class UserPreference(BaseModel):
    """
    用户偏好设置 / User Preference

    四种作用域 / Four scopes:
    - platform_global: 管理端全局基线 / Admin-side global baseline (tenant_id=0, user_id=NULL)
    - tenant_global:   企业端全局基线 / Tenant-side global baseline (tenant_id=N, user_id=NULL)
    - admin:           管理端管理员个人覆盖 / Admin individual override (tenant_id=0, user_id=N)
    - tenant_admin:    企业端管理员个人覆盖 / Tenant admin individual override (tenant_id=N, user_id=N)
    """

    __tablename__ = "user_preferences"

    __table_args__ = (
        UniqueConstraint(
            "scope",
            "tenant_id",
            "user_id",
            name="uq_user_pref_scope_tenant_user",
        ),
    )

    scope: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="作用域 / Scope: platform_global, tenant_global, admin, tenant_admin",
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="企业 ID（0 = 平台级） / Tenant ID (0 = platform level)",
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        index=True,
        comment="用户 ID（NULL = 全局记录） / User ID (NULL = global record)",
    )
    preferences: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="偏好 JSON / Preferences JSON: {key: value, ...}",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="全局记录变更版本号 / Global record change version",
    )

    def __repr__(self) -> str:
        return (
            f"<UserPreference(id={self.id}, scope={self.scope}, "
            f"tenant_id={self.tenant_id}, user_id={self.user_id})>"
        )


__all__ = ["UserPreference"]
