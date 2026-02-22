"""
SSL 证书 Celery 任务

包含 3 个任务：
1. task_provision_ssl - 域名验证后自动触发 ACME 签发（default 队列，一次性）
2. task_check_ssl_renewals - 每日巡检即将过期证书（scheduled 队列，Beat cron）
3. task_renew_ssl - 单个证书续期（default 队列，由巡检触发）

注意：Celery Worker (Windows --pool=solo) 中，asyncio.new_event_loop() 在 retries 之间
会导致模块级 async_session_factory 绑定的 event loop 失效。
因此必须在每次任务调用时创建独立的 async engine + session。
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.core.base_model import utc_now
from app.tasks.base import register_task, BaseTask
from app.tasks.async_db import task_async_session as _task_async_session

logger = LogManager.get_logger("ssl")


@register_task(
    queue="default",
    description="ACME SSL 证书签发（域名验证后自动触发）",
    max_retries=5,
    default_retry_delay=120,
)
def task_provision_ssl(self: BaseTask, domain_id: int) -> dict:
    """
    异步签发 SSL 证书

    由域名验证成功后 celery_app.send_task() 触发
    走 default 队列，一次性即时任务
    """

    async def _provision() -> dict:
        from app.services.system.ssl_certificate_service import SslCertificateService
        from app.services.system.acme_client import AcmeClient
        from app.models.tenant.tenant_domain import TenantDomain
        from sqlalchemy import select

        async with _task_async_session() as db:
            try:
                # 1. 获取域名信息
                result = await db.execute(
                    select(TenantDomain).where(
                        TenantDomain.id == domain_id,
                        TenantDomain.is_deleted.is_(False),
                    )
                )
                domain = result.scalar_one_or_none()

                if not domain:
                    logger.error("Domain %d not found for SSL provisioning", domain_id)
                    return {"error": "domain_not_found", "domain_id": domain_id}

                if not domain.is_verified:
                    logger.warning("Domain %d not verified, skipping SSL", domain_id)
                    return {"error": "domain_not_verified", "domain_id": domain_id}

                logger.info(
                    "Starting SSL provisioning for domain %s (id=%d)",
                    domain.domain, domain_id,
                )

                # 2. 从平台配置读取 ACME 参数
                from app.configs.service import ConfigService
                config_svc = ConfigService(db)
                acme_email = await config_svc.get_platform_config("acme_account_email", default="")
                acme_use_staging = await config_svc.get_platform_config("acme_use_staging", default=True)
                acme_dir_url = await config_svc.get_platform_config("acme_directory_url", default=None)
                acme_stg_url = await config_svc.get_platform_config("acme_staging_url", default=None)
                dir_url = acme_stg_url if acme_use_staging else acme_dir_url

                # 3. 构建 DNS 提供商 + ACME 客户端签发
                from app.services.system.dns_provider import get_dns_provider
                dns_provider = await get_dns_provider(db)

                acme = AcmeClient(
                    directory_url=dir_url or None,
                    account_email=acme_email or None,
                    use_staging=acme_use_staging,
                )
                cert_pem, key_pem, chain_pem = await acme.provision_certificate(
                    domain.domain,
                    dns_setter=dns_provider.set_txt_record,
                )

                # 4. 存储证书
                ssl_service = SslCertificateService(db)
                cert = await ssl_service.store_platform_cert(
                    domain_id=domain_id,
                    tenant_id=domain.tenant_id,
                    cert_pem=cert_pem,
                    key_pem=key_pem,
                    chain_pem=chain_pem,
                )

                await db.commit()

                logger.info(
                    "SSL certificate issued for %s, expires %s",
                    domain.domain, cert.expires_at,
                )
                return {
                    "domain_id": domain_id,
                    "domain": domain.domain,
                    "cert_id": cert.id,
                    "expires_at": str(cert.expires_at),
                    "status": "active",
                }

            except Exception as exc:
                await db.rollback()

                # dns_setter 缺失：配置问题，不重试，仅 WARNING
                from app.services.system.acme_client import AcmeDnsSetterMissingError
                if isinstance(exc, AcmeDnsSetterMissingError):
                    logger.warning(
                        "SSL provisioning skipped for domain %d: %s",
                        domain_id, str(exc),
                    )
                    return {
                        "error": "dns_setter_missing",
                        "domain_id": domain_id,
                        "message": str(exc),
                    }

                # 其他错误：记录 ERROR + 标记失败 + 重试
                logger.error(
                    "SSL provisioning failed for domain %d: %s",
                    domain_id, str(exc), exc_info=True,
                )
                try:
                    async with _task_async_session() as db2:
                        ssl_service = SslCertificateService(db2)
                        await ssl_service.mark_provision_failed(
                            domain_id, str(exc),
                        )
                        await db2.commit()
                except Exception:
                    pass

                raise self.retry(
                    exc=exc,
                    countdown=self.get_retry_countdown() * (self.request.retries + 1),
                )

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_provision())
    finally:
        loop.close()


@register_task(
    queue="scheduled",
    description="SSL 证书续期检查（每日凌晨 3:00 执行）",
    max_retries=1,
)
def task_check_ssl_renewals(self: BaseTask) -> dict:
    """
    定期巡检即将过期的证书

    走 scheduled 队列，由 Beat cron 触发
    - platform 证书：auto_renew=True → 触发 task_renew_ssl
    - custom 证书：仅记录提醒（不自动续期）
    - 已过期证书：标记 ssl_status=expired
    """

    async def _check() -> dict:
        from app.services.system.ssl_certificate_service import SslCertificateService
        from app.repositories.system.ssl_certificate_repository import SslCertificateRepository

        stats = {
            "platform_renewals_triggered": 0,
            "custom_expiring_notified": 0,
            "expired_marked": 0,
            "errors": 0,
        }

        async with _task_async_session() as db:
            try:
                repo = SslCertificateRepository(db)
                ssl_service = SslCertificateService(db)

                # 1. 查询即将过期的平台证书 → 触发续期
                platform_certs = await repo.get_expiring_platform_certs(
                    days=30,
                )
                for cert in platform_certs:
                    try:
                        task_renew_ssl.delay(cert_id=cert.id)
                        stats["platform_renewals_triggered"] += 1
                        logger.info(
                            "Renewal triggered for cert %d (domain_id=%d, expires=%s)",
                            cert.id, cert.domain_id, cert.expires_at,
                        )
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(
                            "Failed to trigger renewal for cert %d: %s",
                            cert.id, str(e),
                        )

                # 2. 查询即将过期的自定义证书 → 记录提醒 + 邮件通知
                custom_certs = await repo.get_expiring_custom_certs(days=30)
                for cert in custom_certs:
                    await ssl_service.mark_renewal_failed(
                        cert.id,
                        "Custom certificate expiring soon, manual upload required",
                    )
                    stats["custom_expiring_notified"] += 1
                    logger.info(
                        "Custom cert %d expiring soon (domain_id=%d, expires=%s)",
                        cert.id, cert.domain_id, cert.expires_at,
                    )
                    # 发送 SSL 到期提醒邮件（在 async 上下文中提取关联数据）
                    notify_email = await _get_cert_notify_email(db, cert.domain_id)
                    if notify_email:
                        _send_ssl_expiry_email(
                            domain_name=notify_email["domain"],
                            expires_at=cert.expires_at,
                            contact_email=notify_email["email"],
                            tenant_id=notify_email["tenant_id"],
                        )

                # 3. 查询已过期证书 → 标记 expired
                expired_certs = await repo.get_expired_certs()
                for cert in expired_certs:
                    try:
                        await ssl_service.mark_expired(cert.id, cert.domain_id)
                        stats["expired_marked"] += 1
                        logger.info(
                            "Cert %d marked expired (domain_id=%d)",
                            cert.id, cert.domain_id,
                        )
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(
                            "Failed to mark cert %d expired: %s",
                            cert.id, str(e),
                        )

                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error("SSL renewal check failed: %s", str(e), exc_info=True)
                stats["errors"] += 1

        logger.info(
            "SSL renewal check completed: %d renewals, %d custom warnings, "
            "%d expired, %d errors",
            stats["platform_renewals_triggered"],
            stats["custom_expiring_notified"],
            stats["expired_marked"],
            stats["errors"],
        )
        return stats

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()


@register_task(
    queue="default",
    description="单个 SSL 证书续期（由巡检任务或手动触发）",
    max_retries=3,
    default_retry_delay=120,
)
def task_renew_ssl(self: BaseTask, cert_id: int) -> dict:
    """
    单个平台证书续期

    走 default 队列，由 task_check_ssl_renewals 或管理端/租户端手动触发
    仅 platform 类型可续期
    """

    async def _renew() -> dict:
        from app.services.system.ssl_certificate_service import SslCertificateService
        from app.services.system.acme_client import AcmeClient
        from app.enums.domain import SslCertType

        async with _task_async_session() as db:
            try:
                ssl_service = SslCertificateService(db)

                # 1. 获取证书信息
                cert = await ssl_service.get_by_id(cert_id)
                if not cert:
                    logger.error("Cert %d not found for renewal", cert_id)
                    return {"error": "cert_not_found", "cert_id": cert_id}

                if cert.cert_type != SslCertType.PLATFORM.value:
                    logger.warning(
                        "Cert %d is custom type, cannot auto-renew", cert_id,
                    )
                    return {"error": "custom_cert_no_renew", "cert_id": cert_id}

                # 2. 获取域名信息
                domain = await ssl_service._get_domain(cert.domain_id)

                logger.info(
                    "Starting SSL renewal for cert %d (domain=%s)",
                    cert_id, domain.domain,
                )

                # 3. 从平台配置读取 ACME 参数
                from app.configs.service import ConfigService
                config_svc = ConfigService(db)
                acme_email = await config_svc.get_platform_config("acme_account_email", default="")
                acme_use_staging = await config_svc.get_platform_config("acme_use_staging", default=True)
                acme_dir_url = await config_svc.get_platform_config("acme_directory_url", default=None)
                acme_stg_url = await config_svc.get_platform_config("acme_staging_url", default=None)
                dir_url = acme_stg_url if acme_use_staging else acme_dir_url

                # 4. 构建 DNS 提供商 + ACME 重新签发
                from app.services.system.dns_provider import get_dns_provider
                dns_provider = await get_dns_provider(db)

                acme = AcmeClient(
                    directory_url=dir_url or None,
                    account_email=acme_email or None,
                    use_staging=acme_use_staging,
                )
                cert_pem, key_pem, chain_pem = await acme.provision_certificate(
                    domain.domain,
                    dns_setter=dns_provider.set_txt_record,
                )

                # 5. 存储新证书（会自动停用旧证书）
                new_cert = await ssl_service.store_platform_cert(
                    domain_id=cert.domain_id,
                    tenant_id=cert.tenant_id,
                    cert_pem=cert_pem,
                    key_pem=key_pem,
                    chain_pem=chain_pem,
                )

                await db.commit()

                logger.info(
                    "SSL certificate renewed for %s, new cert %d expires %s",
                    domain.domain, new_cert.id, new_cert.expires_at,
                )
                return {
                    "cert_id": cert_id,
                    "new_cert_id": new_cert.id,
                    "domain": domain.domain,
                    "expires_at": str(new_cert.expires_at),
                    "status": "renewed",
                }

            except Exception as exc:
                await db.rollback()
                logger.error(
                    "SSL renewal failed for cert %d: %s",
                    cert_id, str(exc), exc_info=True,
                )

                # 记录续期失败（不改变证书状态，仍有效直到过期）
                try:
                    async with _task_async_session() as db2:
                        ssl_service2 = SslCertificateService(db2)
                        await ssl_service2.mark_renewal_failed(cert_id, str(exc))
                        await db2.commit()
                except Exception:
                    pass

                raise self.retry(
                    exc=exc,
                    countdown=self.get_retry_countdown() * (self.request.retries + 1),
                )

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_renew())
    finally:
        loop.close()


async def _get_cert_notify_email(db: AsyncSession, domain_id: int) -> dict | None:
    """
    从 domain_id 查询域名 + 租户联系邮箱（显式查询，避免 ORM 懒加载）

    Returns:
        {"domain": str, "email": str, "tenant_id": int} 或 None
    """
    from sqlalchemy import select
    from app.models.tenant.tenant_domain import TenantDomain
    from app.models import Tenant

    try:
        result = await db.execute(
            select(
                TenantDomain.domain,
                Tenant.id.label("tenant_id"),
                Tenant.contact_email,
            )
            .join(Tenant, Tenant.id == TenantDomain.tenant_id)
            .where(TenantDomain.id == domain_id)
        )
        row = result.first()
        if row and row.contact_email:
            return {
                "domain": row.domain,
                "email": row.contact_email,
                "tenant_id": row.tenant_id,
            }
    except Exception as e:
        logger.warning("Failed to query cert notify email: %s", str(e))
    return None


def _send_ssl_expiry_email(
    domain_name: str,
    expires_at,
    contact_email: str,
    tenant_id: int,
) -> None:
    """
    发送 SSL 证书到期提醒（通过统一通知系统）

    走 notification 队列异步发送，静默失败不影响巡检主流程。
    """
    try:
        from app.services.common.email_templates import render_ssl_expiry_email
        from app.services.common.notification_service import notify_sync

        days_remaining = (expires_at - utc_now()).days if expires_at else 0
        subject, html_body, text_body = render_ssl_expiry_email(
            domain=domain_name,
            expires_at=str(expires_at.date()) if expires_at else "-",
            days_remaining=max(days_remaining, 0),
        )
        notify_sync(
            template_code="system.ssl_expiry",
            recipients=[("admin", 1)],
            data={"domain": domain_name, "days_remaining": max(days_remaining, 0)},
            tenant_id=tenant_id,
            email_html=html_body,
            email_subject=subject,
            email_text=text_body,
        )
    except Exception as e:
        logger.warning("Failed to send SSL expiry notification: %s", str(e))


__all__ = ["task_provision_ssl", "task_check_ssl_renewals", "task_renew_ssl"]
