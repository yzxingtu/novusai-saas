"""
邮件发送 Celery 任务

异步发送邮件，支持重试。
遵循项目定时任务开发规范：sync DB、返回 dict、logger 格式化。
"""

from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import register_task, BaseTask

logger = LogManager.get_logger("task")


@register_task(
    queue="default",
    description="异步发送邮件",
    max_retries=3,
    default_retry_delay=60,
)
def send_email_task(
    self: BaseTask,
    to: list[str],
    subject: str,
    html_body: str | None = None,
    text_body: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    triggered_by: str = "manual",
    tenant_id: int | None = None,
) -> dict:
    """
    异步发送邮件

    Args:
        to: 收件人列表
        subject: 邮件主题
        html_body: HTML 正文
        text_body: 纯文本正文
        cc: 抄送列表
        bcc: 密送列表
        triggered_by: 触发来源 (manual/task_failure/password_reset/test/welcome/ssl_expiry)
        tenant_id: 关联租户 ID（可选）

    Returns:
        发送结果 dict
    """
    from app.services.common.email_service import send_email_sync

    try:
        result = send_email_sync(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc=cc,
            bcc=bcc,
        )

        # 记录邮件日志
        _record_email_log(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            triggered_by=triggered_by,
            tenant_id=tenant_id,
            success=result.success,
            error=result.error,
            html_body=html_body,
            text_body=text_body,
        )

        if result.success:
            logger.info(
                "Email sent: to=%s subject=%s triggered_by=%s",
                ", ".join(to), subject, triggered_by,
            )
            return {
                "status": "sent",
                "recipients": result.recipients,
                "triggered_by": triggered_by,
            }

        # 发送失败但非异常（配置缺失/校验失败）—— 不重试
        if result.message in (
            "email_disabled", "config_incomplete", "no_recipients",
            "too_many_recipients", "invalid_email", "attachment_too_large",
        ):
            logger.warning(
                "Email skipped: reason=%s to=%s",
                result.message, ", ".join(to),
            )
            return {
                "status": result.message,
                "error": result.error,
                "triggered_by": triggered_by,
            }

        # SMTP 错误 —— 重试
        raise RuntimeError(result.error or result.message)

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("Email task failed: %s", str(e))
        _record_email_log(
            to=to, cc=cc, bcc=bcc, subject=subject,
            triggered_by=triggered_by, tenant_id=tenant_id,
            success=False, error=str(e),
            html_body=html_body, text_body=text_body,
        )
        raise self.retry(
            exc=e,
            countdown=self.get_retry_countdown() * (self.request.retries + 1),
        )


def _record_email_log(
    to: list[str],
    cc: list[str] | None,
    bcc: list[str] | None,
    subject: str,
    triggered_by: str,
    tenant_id: int | None,
    success: bool,
    error: str | None,
    html_body: str | None = None,
    text_body: str | None = None,
) -> None:
    """记录邮件发送日志到 email_logs 表"""
    from app.core.database import sync_session_factory
    from app.core.base_model import utc_now

    session = None
    try:
        from app.models.system.email_log import EmailLog

        session = sync_session_factory()
        log = EmailLog(
            to_address=", ".join(to),
            cc=", ".join(cc) if cc else None,
            bcc=", ".join(bcc) if bcc else None,
            subject=subject,
            triggered_by=triggered_by,
            tenant_id=tenant_id,
            status="sent" if success else "failed",
            html_body=html_body[:50000] if html_body else None,
            text_body=text_body[:50000] if text_body else None,
            error_message=error[:2000] if error else None,
            sent_at=utc_now() if success else None,
        )
        session.add(log)
        session.commit()
    except Exception as e:
        logger.warning("Failed to record email log: %s", str(e))
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


__all__ = ["send_email_task"]
