"""
邮件发送服务 / Email Service

提供 SMTP 邮件发送核心逻辑，从平台配置动态读取 SMTP 参数。
Provides SMTP email sending core logic, dynamically reads SMTP params from platform config.
支持 HTML/纯文本/附件/CC/BCC，发送前检查 email_enabled 开关。

注意：此服务需要 async DB session（用于读取配置），
在 Celery 任务中使用时需通过 sync 包装器调用。
"""

import contextlib
import re
import smtplib
import ssl as ssl_module
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("app")


@dataclass
class EmailAttachment:
    """邮件附件 / Email attachment."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass
class EmailMessage:
    """邮件消息 / Email message."""

    to: list[str]
    subject: str
    html_body: str | None = None
    text_body: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)
    reply_to: str | None = None


@dataclass
class EmailResult:
    """邮件发送结果 / Email send result."""

    success: bool
    message: str
    recipients: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class SmtpConfig:
    """SMTP 配置 / SMTP configuration."""

    host: str
    port: int
    encryption: str  # 传输加密 none / ssl / tls / transport encryption
    username: str
    password: str
    from_address: str
    from_name: str
    enabled: bool


# 安全限制常量 / Safety limit constants
MAX_RECIPIENTS = 50
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 上限约 10MB / ~10MB cap
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _is_valid_email(address: str) -> bool:
    """校验邮箱格式 / Validate email format."""
    return bool(_EMAIL_REGEX.match(address.strip()))


class EmailService:
    """
    邮件发送服务；从平台配置动态读取 SMTP，支持 HTML/纯文本/附件 / Email send service; SMTP from platform config, HTML/text/attachments.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._config_service = ConfigService(db)

    async def _load_smtp_config(self) -> SmtpConfig:
        """从平台配置加载 SMTP 参数 / Load SMTP config from platform settings."""
        get = self._config_service.get_platform_config
        return SmtpConfig(
            host=await get("email_smtp_host", default=""),
            port=await get("email_smtp_port", default=587),
            encryption=await get("email_smtp_encryption", default="tls"),
            username=await get("email_smtp_username", default=""),
            password=await get("email_smtp_password", default=""),
            from_address=await get("email_from_address", default=""),
            from_name=await get("email_from_name", default="NovusAI SaaS"),
            enabled=await get("email_enabled", default=False),
        )

    async def send(self, message: EmailMessage) -> EmailResult:
        """
        发送邮件 / Send email.

        Args:
            message: 邮件消息对象 / Email message.

        Returns:
            EmailResult 发送结果 / Send result.
        """
        config = await self._load_smtp_config()

        # 检查邮件功能开关 / Check mail feature enabled
        if not config.enabled:
            logger.info("Email sending disabled, skipping")
            return EmailResult(
                success=False,
                message="email_disabled",
                recipients=message.to,
            )

        # 校验必要配置 / Validate required config
        missing = []
        if not config.host:
            missing.append("smtp_host")
        if not config.from_address:
            missing.append("from_address")
        if missing:
            error_msg = _("email.error.config_missing", fields=", ".join(missing))
            logger.warning("Email config incomplete: {}", ", ".join(missing))
            return EmailResult(
                success=False,
                message="config_incomplete",
                recipients=message.to,
                error=error_msg,
            )

        # 校验收件人 / Validate recipients
        if not message.to:
            return EmailResult(
                success=False,
                message="no_recipients",
                recipients=[],
                error=_("email.error.no_recipients"),
            )

        # 安全校验：收件人数量 / Safety check: recipient count
        all_recipients = message.to + message.cc + message.bcc
        if len(all_recipients) > MAX_RECIPIENTS:
            return EmailResult(
                success=False,
                message="too_many_recipients",
                recipients=message.to,
                error=_(
                    "email.error.too_many_recipients",
                    max=MAX_RECIPIENTS,
                    got=len(all_recipients),
                ),
            )

        # 安全校验：邮箱格式 / Safety check: email format
        invalid = [addr for addr in all_recipients if not _is_valid_email(addr)]
        if invalid:
            return EmailResult(
                success=False,
                message="invalid_email",
                recipients=message.to,
                error=_("email.error.invalid_email", addresses=", ".join(invalid)),
            )

        # 安全校验：附件大小 / Safety check: attachment size
        if message.attachments:
            total_size = sum(len(a.content) for a in message.attachments)
            if total_size > MAX_ATTACHMENT_SIZE:
                max_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
                return EmailResult(
                    success=False,
                    message="attachment_too_large",
                    recipients=message.to,
                    error=_("email.error.attachment_too_large", max_mb=f"{max_mb:.0f}"),
                )

        # 构建 MIME 邮件
        mime_msg = self._build_mime_message(message, config)

        # 发送 / Send
        try:
            self._smtp_send(config, mime_msg, all_recipients)
            logger.info(
                "Email sent: to={} subject={}",
                ", ".join(message.to),
                message.subject,
            )
            return EmailResult(
                success=True,
                message="sent",
                recipients=all_recipients,
            )
        except smtplib.SMTPAuthenticationError as e:
            logger.error("SMTP auth failed: {}", str(e))
            return EmailResult(
                success=False,
                message="auth_failed",
                recipients=all_recipients,
                error=str(e),
            )
        except smtplib.SMTPException as e:
            logger.error("SMTP error: {}", str(e))
            return EmailResult(
                success=False,
                message="smtp_error",
                recipients=all_recipients,
                error=str(e),
            )
        except Exception as e:
            logger.error("Email send failed: {}", str(e))
            return EmailResult(
                success=False,
                message="send_failed",
                recipients=all_recipients,
                error=str(e),
            )

    @staticmethod
    def _build_mime_message(message: EmailMessage, config: SmtpConfig) -> MIMEMultipart:
        """构建 MIME 邮件 / Build MIME message."""
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{config.from_name} <{config.from_address}>"
        msg["To"] = ", ".join(message.to)
        msg["Subject"] = message.subject

        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        # 邮件正文（优先 HTML，附带纯文本回退）
        if message.html_body and message.text_body:
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(message.text_body, "plain", "utf-8"))
            body_part.attach(MIMEText(message.html_body, "html", "utf-8"))
            msg.attach(body_part)
        elif message.html_body:
            msg.attach(MIMEText(message.html_body, "html", "utf-8"))
        elif message.text_body:
            msg.attach(MIMEText(message.text_body, "plain", "utf-8"))

        # 附件 / Attachments
        for attachment in message.attachments:
            part = MIMEApplication(attachment.content)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment.filename,
            )
            part["Content-Type"] = attachment.content_type
            msg.attach(part)

        return msg

    @staticmethod
    def _smtp_send(
        config: SmtpConfig,
        mime_msg: MIMEMultipart,
        recipients: list[str],
    ) -> None:
        """通过 SMTP 发送邮件（同步阻塞） / Send email via SMTP (sync blocking)."""
        timeout = 30

        if config.encryption == "ssl":
            context = ssl_module.create_default_context()
            server = smtplib.SMTP_SSL(
                config.host, config.port, timeout=timeout, context=context
            )
        else:
            server = smtplib.SMTP(config.host, config.port, timeout=timeout)

        try:
            if config.encryption == "tls":
                context = ssl_module.create_default_context()
                server.starttls(context=context)

            if config.username and config.password:
                server.login(config.username, config.password)

            server.sendmail(
                config.from_address,
                recipients,
                mime_msg.as_string(),
            )
        finally:
            server.quit()


# ============================================
# 同步版本（Celery 任务专用）
# ============================================


def send_email_sync(
    to: list[str],
    subject: str,
    html_body: str | None = None,
    text_body: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> EmailResult:
    """
    同步发送邮件（Celery Worker 专用）/ Send email synchronously (for Celery worker).

    直接从 DB 读取 SMTP 配置，不依赖 async session。
    """
    from app.core.database import sync_session_factory

    session = sync_session_factory()
    try:
        config = _load_smtp_config_sync(session)

        if not config.enabled:
            return EmailResult(success=False, message="email_disabled", recipients=to)

        if not config.host or not config.from_address:
            return EmailResult(
                success=False,
                message="config_incomplete",
                recipients=to,
                error=_("email.error.config_missing", fields="smtp_host, from_address"),
            )

        all_recipients = to + (cc or []) + (bcc or [])

        # 安全校验：收件人数量 / Safety check: recipient count
        if len(all_recipients) > MAX_RECIPIENTS:
            return EmailResult(
                success=False,
                message="too_many_recipients",
                recipients=to,
                error=f"Too many recipients: {len(all_recipients)} > {MAX_RECIPIENTS}",
            )

        # 安全校验：邮箱格式 / Safety check: email format
        invalid = [addr for addr in all_recipients if not _is_valid_email(addr)]
        if invalid:
            return EmailResult(
                success=False,
                message="invalid_email",
                recipients=to,
                error=f"Invalid email: {', '.join(invalid)}",
            )

        message = EmailMessage(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc=cc or [],
            bcc=bcc or [],
        )

        mime_msg = EmailService._build_mime_message(message, config)

        EmailService._smtp_send(config, mime_msg, all_recipients)

        logger.info("Email sent (sync): to={} subject={}", ", ".join(to), subject)
        return EmailResult(success=True, message="sent", recipients=all_recipients)

    except Exception as e:
        logger.error("Email send failed (sync): {}", str(e))
        return EmailResult(
            success=False, message="send_failed", recipients=to, error=str(e)
        )
    finally:
        session.close()


def _load_smtp_config_sync(session: Any) -> SmtpConfig:
    """同步加载 SMTP 配置 / Load SMTP config synchronously."""
    from app.configs.service import PLATFORM_TENANT_ID
    from app.models.system.config import SystemConfig, SystemConfigValue

    def _get(key: str, default: Any = None) -> Any:
        row = (
            session.query(SystemConfigValue)
            .join(SystemConfig, SystemConfigValue.config_id == SystemConfig.id)
            .filter(
                SystemConfig.key == key,
                SystemConfigValue.tenant_id == PLATFORM_TENANT_ID,
            )
            .first()
        )
        if row is None:
            return default
        val = row.value
        if isinstance(val, str):
            # 配置值以 JSON 格式存储，字符串会带引号如 '"smtp.example.com"'
            # 先尝试 JSON 反序列化
            import json

            with contextlib.suppress(json.JSONDecodeError, TypeError):
                val = json.loads(val)
            # 布尔值处理 / Boolean coercion
            if isinstance(val, bool):
                return val
            if isinstance(val, str) and val.lower() in ("true", "false"):
                return val.lower() == "true"
            # 数字处理 / Numeric coercion
            if isinstance(val, (int, float)):
                return val
            if isinstance(val, str):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
        return val

    return SmtpConfig(
        host=_get("email_smtp_host", ""),
        port=_get("email_smtp_port", 465),
        encryption=_get("email_smtp_encryption", "ssl"),
        username=_get("email_smtp_username", ""),
        password=_get("email_smtp_password", ""),
        from_address=_get("email_from_address", ""),
        from_name=_get("email_from_name", "NovusAI SaaS"),
        enabled=_get("email_enabled", False),
    )


__all__ = [
    "EmailService",
    "EmailMessage",
    "EmailAttachment",
    "EmailResult",
    "SmtpConfig",
    "send_email_sync",
]
