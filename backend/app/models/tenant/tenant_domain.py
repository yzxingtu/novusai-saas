"""
企业域名模型 / Tenant Domain Model

管理企业的自定义域名绑定
Manages tenant custom domain bindings.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.enums.domain import DomainSslStatus, DomainType


class TenantDomain(BaseModel):
    """
    企业域名模型 / Tenant domain model.

    - 每个企业可以绑定多个自定义域名
    - 用户通过 CNAME 将自定义域名解析到企业子域名
    - 域名需要验证所有权后才能使用
    """

    __tablename__ = "tenant_domains"

    __delete_deps__ = [
        DeletionDep("DomainSslCertificate", "domain_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="domain_ssl_certificate"),
    ]

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "domain": "domain",
        "is_verified": "is_verified",
        "is_primary": "is_primary",
        "ssl_status": "ssl_status",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 允许前端排序的字段
    __sortable__ = [
        "id", "domain", "is_verified", "is_primary",
        "ssl_status", "created_at", "updated_at",
    ]

    # 下拉选项配置
    __selectable__ = {
        "label": "domain",
        "value": "id",
        "search": ["domain"],
        "extra": ["is_primary", "is_verified", "ssl_status"],
    }

    # 关联企业
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="企业 ID",
    )

    # 域名（全局唯一）
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="域名",
    )

    # 验证状态
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否已验证",
    )

    # 验证时间
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="验证时间",
    )

    # 是否主域名（每个企业只能有一个主域名）
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否主域名",
    )

    # SSL 证书状态
    ssl_status: Mapped[str] = mapped_column(
        String(20),
        default=DomainSslStatus.PENDING,
        comment="SSL 状态: none/pending/provisioning/active/failed/expired",
    )

    # SSL 证书到期时间
    ssl_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="SSL 证书到期时间",
    )

    # 验证记录值（用于 DNS TXT 验证）
    verification_token: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="域名验证 Token",
    )

    # 备注
    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )

    # ==================== 关系 ====================

    # 关联的企业
    tenant = relationship(
        "Tenant",
        back_populates="domains",
        lazy="noload",
    )

    # 关联的 SSL 证书
    ssl_certificates = relationship(
        "DomainSslCertificate",
        back_populates="domain",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    # ==================== 索引 ====================

    __table_args__ = (
        # 复合索引：企业ID + 是否主域名
        Index("ix_tenant_domains_tenant_primary", "tenant_id", "is_primary"),
    )

    # ==================== 辅助方法 ====================

    @property
    def domain_type(self) -> str:
        """域名类型：default（平台默认）或 custom（自定义） / Domain type: default or custom."""
        from app.core.config import settings
        suffix = settings.TENANT_DOMAIN_SUFFIX.lstrip(".")
        if self.domain and self.domain.endswith(suffix):
            return DomainType.DEFAULT
        return DomainType.CUSTOM

    @property
    def is_active(self) -> bool:
        """域名是否处于可用状态 / Whether domain is in active/usable state."""
        return self.is_verified and self.ssl_status == DomainSslStatus.ACTIVE

    @property
    def cname_target(self) -> str | None:
        """
        获取 CNAME 解析目标 / Get CNAME target.

        需要从关联的企业获取子域名。
        """
        if self.tenant:
            from app.core.config import settings
            return f"{self.tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"
        return None

    def __repr__(self) -> str:
        return f"<TenantDomain(id={self.id}, domain={self.domain}, tenant_id={self.tenant_id})>"


__all__ = ["TenantDomain"]
