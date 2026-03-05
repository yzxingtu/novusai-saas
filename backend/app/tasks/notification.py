"""
通知系统 Celery 任务

专用 notification 队列，处理通知相关的异步任务（邮件发送等）。
与 email.py 的区别：email.py 处理通用邮件发送（手动/测试），
本模块专门处理通知系统触发的邮件。
"""

from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


@register_task(
    queue="notification",
    description="通知系统邮件发送",
    max_retries=3,
    default_retry_delay=30,
)
def send_notification_email(
    self: BaseTask,
    to: list[str],
    subject: str,
    html_body: str | None = None,
    text_body: str | None = None,
    triggered_by: str = "notification",
    tenant_id: int | None = None,
) -> dict:
    """
    通知系统触发的邮件发送（走 notification 队列）

    Args:
        to: 收件人列表
        subject: 邮件主题
        html_body: HTML 正文
        text_body: 纯文本正文
        triggered_by: 触发来源（通知模板编码，如 system.password_reset）
        tenant_id: 关联租户 ID

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
        )

        # 记录邮件日志
        _record_notification_email_log(
            to=to,
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
                "Notification email sent: to=%s subject=%s triggered_by=%s",
                ", ".join(to), subject, triggered_by,
            )
            return {
                "status": "sent",
                "recipients": result.recipients,
                "triggered_by": triggered_by,
            }

        # 配置问题不重试
        if result.message in (
            "email_disabled", "config_incomplete", "no_recipients",
        ):
            logger.warning(
                "Notification email skipped: reason=%s to=%s",
                result.message, ", ".join(to),
            )
            return {
                "status": result.message,
                "error": result.error,
                "triggered_by": triggered_by,
            }

        # SMTP 错误重试
        raise RuntimeError(result.error or result.message)

    except RuntimeError:
        raise
    except Exception as e:
        logger.error("Notification email task failed: %s", str(e))
        _record_notification_email_log(
            to=to,
            subject=subject,
            triggered_by=triggered_by,
            tenant_id=tenant_id,
            success=False,
            error=str(e),
            html_body=html_body,
            text_body=text_body,
        )
        raise self.retry(
            exc=e,
            countdown=self.get_retry_countdown() * (self.request.retries + 1),
        )


def _record_notification_email_log(
    to: list[str],
    subject: str,
    triggered_by: str,
    tenant_id: int | None,
    success: bool,
    error: str | None,
    html_body: str | None = None,
    text_body: str | None = None,
) -> None:
    """记录通知邮件日志"""
    from app.core.base_model import utc_now
    from app.core.database import sync_session_factory

    session = None
    try:
        from app.models.system.email_log import EmailLog

        session = sync_session_factory()
        log = EmailLog(
            to_address=", ".join(to),
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
        logger.warning("Failed to record notification email log: %s", str(e))
        if session:
            session.rollback()
    finally:
        if session:
            session.close()


__all__ = ["send_notification_email"]
