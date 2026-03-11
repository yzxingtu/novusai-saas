"""
邮件通知渠道 / Email Notification Channel

通过 Celery 异步任务发送邮件通知。使用专门的 notification 队列。
Sends email notifications via Celery async tasks. Uses dedicated notification queue.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.services.common.channels.base import NotificationChannel

logger = LogManager.get_logger("app")


class EmailChannel(NotificationChannel):
    """邮件渠道 — 通过 Celery notification 队列异步发送"""

    @property
    def channel_code(self) -> str:
        return "email"

    @property
    def channel_name(self) -> str:
        return "Email"

    async def is_enabled(self) -> bool:
        """检查 SMTP 邮件发送是否启用"""
        try:
            from app.core.database import sync_session_factory
            from app.models.system.config import SystemConfig, SystemConfigValue

            session = sync_session_factory()
            try:
                row = (
                    session.query(SystemConfigValue.value)
                    .join(SystemConfig, SystemConfigValue.config_id == SystemConfig.id)
                    .filter(SystemConfig.key == "email_enabled", SystemConfigValue.tenant_id == 0)
                    .first()
                )
                if not row:
                    return False
                val = row[0]
                # 处理 JSON 编码的值（如 '"true"'）
                if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                    val = val.strip('"')
                return val == "true" or val is True
            finally:
                session.close()
        except Exception:
            return False

    async def deliver(
        self,
        db: AsyncSession,
        user_type: str,
        user_id: int,
        title: str,
        body: str | None,
        data: dict[str, Any] | None,
        link: str | None,
        priority: str,
        template_code: str,
        tenant_id: int | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        通过邮件发送通知

        支持 kwargs:
            email_html: 自定义 HTML 邮件正文（富文本邮件场景）
            email_subject: 自定义邮件主题（默认用 title）
            email_text: 自定义纯文本正文
        """
        _ = data
        try:
            # 租户级邮件通知开关检查
            if tenant_id:
                try:
                    from app.configs.service import ConfigService
                    config_service = ConfigService(db)
                    email_enabled = await config_service.get_tenant_config(
                        tenant_id=tenant_id,
                        key="tenant_email_notification",
                    )
                    if email_enabled is False:
                        logger.debug(
                            "EmailChannel: tenant %d email notification disabled, skip",
                            tenant_id,
                        )
                        return False
                except Exception as cfg_err:
                    logger.warning("EmailChannel: tenant config check failed: %s", cfg_err)

            email = await self._get_user_email(db, user_type, user_id)
            if not email:
                logger.debug("EmailChannel: no email for %s:%d, skip", user_type, user_id)
                return False

            from app.tasks.notification import send_notification_email

            email_subject = kwargs.get("email_subject") or title
            email_html = kwargs.get("email_html")
            email_text = kwargs.get("email_text")

            # 没有自定义 HTML 时，自动使用通知 HTML 模板包装
            if not email_html:
                try:
                    from app.services.common.email_templates import (
                        render_notification_html,
                    )
                    email_html, email_text = render_notification_html(
                        title=title,
                        body=body,
                        priority=priority,
                        link=link,
                    )
                    logger.debug("EmailChannel: rendered HTML template OK, len=%d", len(email_html))
                except Exception as tpl_err:
                    logger.error("EmailChannel: render_notification_html failed: %s", tpl_err, exc_info=True)
                    # 降级为纯文本
                    email_html = body or title

            send_notification_email.delay(
                to=[email],
                subject=email_subject,
                html_body=email_html,
                text_body=email_text,
                triggered_by=template_code,
                tenant_id=tenant_id,
            )
            return True
        except Exception as e:
            logger.warning("EmailChannel deliver failed: %s", str(e))
            return False

    @staticmethod
    async def _get_user_email(db: AsyncSession, user_type: str, user_id: int) -> str | None:
        """获取用户邮箱"""
        from sqlalchemy import select

        if user_type == "admin":
            from app.models import Admin
            result = await db.execute(select(Admin.email).where(Admin.id == user_id))
        elif user_type == "tenant_admin":
            from app.models import TenantAdmin
            result = await db.execute(select(TenantAdmin.email).where(TenantAdmin.id == user_id))
        elif user_type == "tenant_user":
            from app.models import TenantUser
            result = await db.execute(select(TenantUser.email).where(TenantUser.id == user_id))
        else:
            return None
        return result.scalar_one_or_none()


__all__ = ["EmailChannel"]
