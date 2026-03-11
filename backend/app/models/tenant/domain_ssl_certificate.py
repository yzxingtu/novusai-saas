"""
域名 SSL 证书模型 / Domain SSL Certificate Model

存储域名的 SSL 证书信息，支持平台自动签发(Let's Encrypt)和用户自定义上传两种类型
Stores domain SSL certificate info, supports auto-issuance (Let's Encrypt) and custom upload.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.enums.domain import SslCertStatus, SslCertType


class DomainSslCertificate(BaseModel):
    """
    域名 SSL 证书模型

    - 每个域名最多一个有效证书（active 状态）
    - 支持 platform（ACME 自动签发）和 custom（用户上传）两种类型
    - platform 类型支持自动续期，custom 类型需手动重新上传
    - 私钥使用 Fernet 加密存储
    """

    __tablename__ = "domain_ssl_certificates"

    __filterable__ = {
        "id": "id",
        "domain_id": "domain_id",
        "tenant_id": "tenant_id",
        "cert_type": "cert_type",
        "status": "status",
        "auto_renew": "auto_renew",
        "expires_at": "expires_at",
        "created_at": "created_at",
    }

    __sortable__ = [
        "id", "expires_at", "issued_at", "created_at", "updated_at",
    ]

    # ==================== 关联字段 ====================

    domain_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenant_domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="域名 ID",
    )

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="租户 ID",
    )

    # ==================== 证书类型与状态 ====================

    cert_type: Mapped[str] = mapped_column(
        String(20),
        default=SslCertType.PLATFORM,
        nullable=False,
        comment="证书类型: platform(ACME自动签发) / custom(用户上传)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=SslCertStatus.PENDING,
        nullable=False,
        comment="证书状态: pending/active/expired/revoked/failed",
    )

    # ==================== 证书内容 ====================

    certificate: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="PEM 格式证书内容",
    )

    private_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Fernet 加密的私钥",
    )

    certificate_chain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="PEM 格式证书链（中间证书）",
    )

    # ==================== 证书元信息 ====================

    issuer: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="签发机构（如 Let's Encrypt）",
    )

    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="证书序列号",
    )

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="签发时间",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="到期时间",
    )

    # ==================== 续期配置 ====================

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否自动续期（仅 platform 类型有效）",
    )

    last_renewal_attempt: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="最近一次续期尝试时间",
    )

    renewal_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最近一次续期失败原因",
    )

    # ==================== ACME 相关 ====================

    acme_order_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="ACME 订单 URL（用于异步轮询签发状态）",
    )

    # ==================== 关系 ====================

    domain = relationship(
        "TenantDomain",
        back_populates="ssl_certificates",
        lazy="select",
    )

    tenant = relationship(
        "Tenant",
        lazy="noload",
    )

    # ==================== 索引 ====================

    __table_args__ = (
        Index("ix_domain_ssl_certs_domain_status", "domain_id", "status"),
        Index("ix_domain_ssl_certs_expires", "expires_at"),
        Index("ix_domain_ssl_certs_tenant", "tenant_id"),
    )

    # ==================== 辅助方法 ====================

    @property
    def is_platform(self) -> bool:
        return self.cert_type == SslCertType.PLATFORM

    @property
    def is_custom(self) -> bool:
        return self.cert_type == SslCertType.CUSTOM

    @property
    def is_expiring_soon(self) -> bool:
        """30 天内即将过期"""
        if not self.expires_at:
            return False
        from datetime import timedelta

        from app.core.base_model import utc_now
        return self.expires_at < utc_now() + timedelta(days=30)

    def __repr__(self) -> str:
        return (
            f"<DomainSslCertificate(id={self.id}, domain_id={self.domain_id}, "
            f"type={self.cert_type}, status={self.status})>"
        )


__all__ = ["DomainSslCertificate"]
