"""
SSL 证书仓储

提供 SSL 证书的数据访问操作（平台级，非租户隔离）
"""

from datetime import timedelta

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository
from app.enums.domain import SslCertStatus, SslCertType
from app.models.tenant.domain_ssl_certificate import DomainSslCertificate


class SslCertificateRepository(BaseRepository[DomainSslCertificate]):
    """
    SSL 证书仓储

    提供证书特有的数据访问方法
    """

    model = DomainSslCertificate

    async def get_active_cert(self, domain_id: int) -> DomainSslCertificate | None:
        """获取域名当前有效证书"""
        query = select(self.model).where(
            self.model.domain_id == domain_id,
            self.model.status == SslCertStatus.ACTIVE.value,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_cert_by_domain(self, domain_id: int) -> DomainSslCertificate | None:
        """获取域名最新证书（不论状态）"""
        query = (
            select(self.model)
            .where(
                self.model.domain_id == domain_id,
                self.model.is_deleted.is_(False),
            )
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_expiring_platform_certs(self, days: int = 30) -> list[DomainSslCertificate]:
        """查询即将过期的平台证书（auto_renew=True）"""
        cutoff = utc_now() + timedelta(days=days)
        query = select(self.model).where(
            self.model.cert_type == SslCertType.PLATFORM.value,
            self.model.status == SslCertStatus.ACTIVE.value,
            self.model.auto_renew.is_(True),
            self.model.expires_at.is_not(None),
            self.model.expires_at < cutoff,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_expiring_custom_certs(self, days: int = 30) -> list[DomainSslCertificate]:
        """查询即将过期的自定义证书（需通知，不自动续期）"""
        cutoff = utc_now() + timedelta(days=days)
        query = select(self.model).where(
            self.model.cert_type == SslCertType.CUSTOM.value,
            self.model.status == SslCertStatus.ACTIVE.value,
            self.model.expires_at.is_not(None),
            self.model.expires_at < cutoff,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_expired_certs(self) -> list[DomainSslCertificate]:
        """查询已过期但 status 未更新的证书"""
        now = utc_now()
        query = select(self.model).where(
            self.model.status == SslCertStatus.ACTIVE.value,
            self.model.expires_at.is_not(None),
            self.model.expires_at < now,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def deactivate_domain_certs(self, domain_id: int) -> None:
        """将域名所有有效证书标记为已吊销（上传新证书前调用）"""
        from sqlalchemy import update
        stmt = (
            update(self.model)
            .where(
                self.model.domain_id == domain_id,
                self.model.status == SslCertStatus.ACTIVE.value,
                self.model.is_deleted.is_(False),
            )
            .values(status=SslCertStatus.REVOKED.value)
        )
        await self.db.execute(stmt)


__all__ = ["SslCertificateRepository"]
