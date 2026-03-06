"""
SSL 证书服务

提供 SSL 证书的业务逻辑（平台级）
包括证书查询、上传、删除、自动续期开关、证书解析与验证
"""

from datetime import datetime

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from app.core.base_model import utc_now
from app.core.base_service import GlobalService
from app.core.config import settings
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.domain import DomainSslStatus, SslCertStatus, SslCertType
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.domain_ssl_certificate import DomainSslCertificate
from app.models.tenant.tenant_domain import TenantDomain
from app.repositories.system.ssl_certificate_repository import SslCertificateRepository


class SslCertificateService(GlobalService[DomainSslCertificate, SslCertificateRepository]):
    """
    SSL 证书服务

    提供证书管理的核心业务方法
    """

    model = DomainSslCertificate
    repository_class = SslCertificateRepository

    # ==================== 查询 ====================

    async def get_cert_detail(self, domain_id: int) -> DomainSslCertificate | None:
        """获取域名当前证书（优先 active，否则最新）"""
        cert = await self.repo.get_active_cert(domain_id)
        if not cert:
            cert = await self.repo.get_cert_by_domain(domain_id)
        return cert

    # ==================== 上传自定义证书 ====================

    async def _check_custom_ssl_quota(self, tenant_id: int) -> None:
        """
        检查租户是否允许上传自定义 SSL 证书

        通过租户套餐的 allow_custom_ssl 配额判断。
        不允许时抛出 BusinessException。
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.tenant.tenant import Tenant

        result = await self.db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id, Tenant.is_deleted.is_(False))
            .options(selectinload(Tenant.tenant_plan))
        )
        tenant = result.scalar_one_or_none()
        if tenant and not tenant.get_quota_value("allow_custom_ssl", False):
            raise BusinessException(
                message=_("ssl_certificate.custom_ssl_not_allowed"),
                code=ErrorCode.FORBIDDEN,
            )

    async def upload_custom_cert(
        self,
        domain_id: int,
        tenant_id: int,
        cert_pem: str,
        key_pem: str,
        chain_pem: str | None = None,
        *,
        check_quota: bool = False,
    ) -> DomainSslCertificate:
        """
        上传自定义证书

        验证证书格式、私钥匹配、域名匹配后存储
        自动设置 cert_type=custom, auto_renew=False

        Args:
            check_quota: 是否检查套餐 allow_custom_ssl 配额（租户端传 True，管理端传 False）
        """
        # 套餐配额检查（仅租户端需要）
        if check_quota:
            await self._check_custom_ssl_quota(tenant_id)

        # 获取域名信息
        domain = await self._get_domain(domain_id)

        # 验证证书与私钥
        cert_info = self._parse_cert_info(cert_pem)
        self._validate_certificate(cert_pem, key_pem)
        self._validate_domain_in_cert(cert_pem, domain.domain)

        # 检查证书是否过期
        if cert_info["expires_at"] and cert_info["expires_at"] < utc_now():
            raise BusinessException(
                message=_("ssl_certificate.cert_expired"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        # 停用域名现有证书
        await self.repo.deactivate_domain_certs(domain_id)

        # 加密私钥
        encryption_key = await self._get_encryption_key()
        encrypted_key = self._encrypt_private_key(key_pem, encryption_key)

        # 创建新证书记录
        cert = await self.create({
            "domain_id": domain_id,
            "tenant_id": tenant_id,
            "cert_type": SslCertType.CUSTOM.value,
            "status": SslCertStatus.ACTIVE.value,
            "certificate": cert_pem,
            "private_key_encrypted": encrypted_key,
            "certificate_chain": chain_pem,
            "issuer": cert_info["issuer"],
            "serial_number": cert_info["serial_number"],
            "issued_at": cert_info["issued_at"],
            "expires_at": cert_info["expires_at"],
            "auto_renew": False,
        })

        # 更新域名 SSL 状态
        await self._update_domain_ssl_status(
            domain_id, DomainSslStatus.ACTIVE.value, cert_info["expires_at"],
        )

        return cert

    # ==================== 删除证书 ====================

    async def delete_cert(self, domain_id: int) -> bool:
        """删除域名证书并重置 SSL 状态"""
        cert = await self.repo.get_active_cert(domain_id)
        if not cert:
            cert = await self.repo.get_cert_by_domain(domain_id)
        if not cert:
            raise NotFoundException(message=_("ssl_certificate.not_found"))

        await self.delete(cert.id)
        await self._update_domain_ssl_status(domain_id, DomainSslStatus.NONE.value, None)
        return True

    # ==================== 自动续期开关 ====================

    async def toggle_auto_renew(self, domain_id: int, enabled: bool) -> DomainSslCertificate:
        """开关自动续期（仅 platform 类型可开启）"""
        cert = await self.repo.get_active_cert(domain_id)
        if not cert:
            raise NotFoundException(message=_("ssl_certificate.not_found"))

        if enabled and cert.cert_type == SslCertType.CUSTOM.value:
            raise BusinessException(
                message=_("ssl_certificate.custom_cert_no_auto_renew"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.update(cert.id, {"auto_renew": enabled})
        if not result:
            raise NotFoundException(message=_("ssl_certificate.not_found"))
        return result

    # ==================== 存储平台证书（ACME 签发后调用） ====================

    async def store_platform_cert(
        self,
        domain_id: int,
        tenant_id: int,
        cert_pem: str,
        key_pem: str,
        chain_pem: str | None = None,
        acme_order_url: str | None = None,
    ) -> DomainSslCertificate:
        """存储 ACME 签发的平台证书（由 Celery 任务调用）"""
        cert_info = self._parse_cert_info(cert_pem)
        encryption_key = await self._get_encryption_key()
        encrypted_key = self._encrypt_private_key(key_pem, encryption_key)

        # 停用已有证书
        await self.repo.deactivate_domain_certs(domain_id)

        cert = await self.create({
            "domain_id": domain_id,
            "tenant_id": tenant_id,
            "cert_type": SslCertType.PLATFORM.value,
            "status": SslCertStatus.ACTIVE.value,
            "certificate": cert_pem,
            "private_key_encrypted": encrypted_key,
            "certificate_chain": chain_pem,
            "issuer": cert_info["issuer"],
            "serial_number": cert_info["serial_number"],
            "issued_at": cert_info["issued_at"],
            "expires_at": cert_info["expires_at"],
            "auto_renew": True,
            "acme_order_url": acme_order_url,
        })

        await self._update_domain_ssl_status(
            domain_id, DomainSslStatus.ACTIVE.value, cert_info["expires_at"],
        )

        return cert

    # ==================== 记录签发失败 ====================

    async def mark_provision_failed(
        self, domain_id: int, error: str,
    ) -> None:
        """标记签发失败"""
        cert = await self.repo.get_cert_by_domain(domain_id)
        if cert:
            await self.update(cert.id, {
                "status": SslCertStatus.FAILED.value,
                "renewal_error": error,
                "last_renewal_attempt": utc_now(),
            })

        await self._update_domain_ssl_status(domain_id, DomainSslStatus.FAILED.value, None)

    # ==================== 记录续期失败 ====================

    async def mark_renewal_failed(
        self, cert_id: int, error: str,
    ) -> None:
        """标记续期失败（不改变 ssl_status，证书仍然有效直到过期）"""
        await self.update(cert_id, {
            "renewal_error": error,
            "last_renewal_attempt": utc_now(),
        })

    # ==================== 记录到期预警 ====================

    async def mark_expiry_warning(
        self, cert_id: int, warning: str,
    ) -> None:
        """记录证书到期预警（用于自定义证书即将过期的提醒，不改变状态）"""
        await self.update(cert_id, {
            "renewal_error": warning,
            "last_renewal_attempt": utc_now(),
        })

    # ==================== 标记过期 ====================

    async def mark_expired(self, cert_id: int, domain_id: int) -> None:
        """标记证书过期"""
        await self.update(cert_id, {"status": SslCertStatus.EXPIRED.value})
        await self._update_domain_ssl_status(domain_id, DomainSslStatus.EXPIRED.value, None)

    # ==================== 内部方法 ====================

    async def _get_domain(self, domain_id: int) -> TenantDomain:
        """获取域名实例"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(TenantDomain).where(
                TenantDomain.id == domain_id,
                TenantDomain.is_deleted.is_(False),
            )
        )
        domain = result.scalar_one_or_none()
        if not domain:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return domain

    async def _update_domain_ssl_status(
        self, domain_id: int, status: str, expires_at: datetime | None,
    ) -> None:
        """更新域名 SSL 状态字段"""
        from sqlalchemy import update
        stmt = (
            update(TenantDomain)
            .where(TenantDomain.id == domain_id)
            .values(ssl_status=status, ssl_expires_at=expires_at)
        )
        await self.db.execute(stmt)

    # ==================== 证书工具方法 ====================

    async def _get_encryption_key(self) -> str:
        """从平台配置或环境变量获取 Fernet 加密密钥"""
        from app.configs.service import ConfigService
        config_svc = ConfigService(self.db)
        key = await config_svc.get_platform_config(
            "ssl_private_key_encryption_key", default=None,
        )
        if key:
            return key
        if settings.SSL_PRIVATE_KEY_ENCRYPTION_KEY:
            return settings.SSL_PRIVATE_KEY_ENCRYPTION_KEY
        raise BusinessException(
            message=_("ssl_certificate.encryption_key_not_configured"),
            code=ErrorCode.VALIDATION_ERROR,
        )

    @staticmethod
    def _encrypt_private_key(key_pem: str, encryption_key: str) -> str:
        """Fernet 加密私钥"""
        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(key_pem.encode()).decode()

    @staticmethod
    def _decrypt_private_key(encrypted: str, encryption_key: str) -> str:
        """Fernet 解密私钥"""
        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(encrypted.encode()).decode()

    @staticmethod
    def _parse_cert_info(cert_pem: str) -> dict:
        """解析 PEM 证书信息"""
        cert = x509.load_pem_x509_certificate(cert_pem.encode())

        # 签发机构
        issuer_parts = []
        for attr in cert.issuer:
            if attr.oid == NameOID.ORGANIZATION_NAME or attr.oid == NameOID.COMMON_NAME:
                issuer_parts.append(attr.value)
        issuer = ", ".join(issuer_parts) if issuer_parts else str(cert.issuer)

        # Return naive UTC datetimes (TIMESTAMP WITHOUT TIME ZONE)
        issued_at = (
            cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc")
            else cert.not_valid_before
        )
        expires_at = (
            cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc")
            else cert.not_valid_after
        )

        return {
            "issuer": issuer,
            "serial_number": format(cert.serial_number, "x"),
            "issued_at": issued_at.replace(tzinfo=None),
            "expires_at": expires_at.replace(tzinfo=None),
        }

    @staticmethod
    def _validate_certificate(cert_pem: str, key_pem: str) -> None:
        """验证证书与私钥是否匹配"""
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode())
            key = serialization.load_pem_private_key(key_pem.encode(), password=None)
        except Exception as e:
            raise BusinessException(
                message=_("ssl_certificate.cert_key_mismatch"),
                code=ErrorCode.VALIDATION_ERROR,
            ) from e

        # 比较公钥
        cert_pub = cert.public_key()
        key_pub = key.public_key()

        cert_pub_bytes = cert_pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        key_pub_bytes = key_pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        if cert_pub_bytes != key_pub_bytes:
            raise BusinessException(
                message=_("ssl_certificate.cert_key_mismatch"),
                code=ErrorCode.VALIDATION_ERROR,
            )

    @staticmethod
    def _validate_domain_in_cert(cert_pem: str, domain: str) -> None:
        """验证证书是否包含指定域名（检查 SAN 和 CN）"""
        cert = x509.load_pem_x509_certificate(cert_pem.encode())

        # 检查 SAN (Subject Alternative Names)
        try:
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            dns_names = san.value.get_values_for_type(x509.DNSName)
            for name in dns_names:
                if name == domain or (name.startswith("*.") and domain.endswith(name[1:])):
                    return
        except x509.ExtensionNotFound:
            pass

        # 回退检查 CN
        for attr in cert.subject:
            if attr.oid == NameOID.COMMON_NAME:
                cn = attr.value
                if cn == domain or (cn.startswith("*.") and domain.endswith(cn[1:])):
                    return

        raise BusinessException(
            message=_("ssl_certificate.domain_not_in_cert"),
            code=ErrorCode.VALIDATION_ERROR,
        )


__all__ = ["SslCertificateService"]
