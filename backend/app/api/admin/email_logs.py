"""
邮件日志管理 API

提供邮件发送日志查看 + 手动发送邮件接口（平台管理员专用）
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success, paginated
from app.exceptions import NotFoundException
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
)
from app.schemas.system.email_log import (
    EmailLogResponse,
    EmailSendRequest,
    EmailTestRequest,
)
from app.services.common.email_service import EmailService, EmailMessage
from app.repositories.system.email_log_repository import EmailLogRepository


@permission_resource(
    resource="email_log",
    name="menu.admin.email_log",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:mail",
        path="/system/email-logs",
        component="admin/system/email-logs/index",
        parent="system_maintenance",
        sort_order=70,
    ),
)
class AdminEmailLogController(GlobalController):
    """
    邮件日志控制器

    提供邮件日志查询 + 手动发送 + 测试邮件接口
    """

    prefix = "/email-logs"
    tags = ["Email Logs"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取邮件发送日志列表")
        @action_read("action.email_log.list")
        async def list_email_logs(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            query: QueryParams,
        ):
            repo = EmailLogRepository(db)
            items, total = await repo.query_list(query)
            return paginated(
                items=[EmailLogResponse.model_validate(item, from_attributes=True) for item in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{log_id}", summary="获取邮件日志详情")
        @action_read("action.email_log.list")
        async def get_email_log_detail(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            log_id: int,
        ):
            repo = EmailLogRepository(db)
            log = await repo.get_by_id(log_id)
            if not log:
                raise NotFoundException(message=_("email_log.not_found"))
            return success(data={
                "id": log.id,
                "to_address": log.to_address,
                "cc": log.cc,
                "bcc": log.bcc,
                "subject": log.subject,
                "status": log.status,
                "triggered_by": log.triggered_by,
                "html_body": log.html_body,
                "text_body": log.text_body,
                "error_message": log.error_message,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "tenant_id": log.tenant_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        @router.post("/send", summary="手动发送邮件")
        @action_create("action.email_log.send")
        async def send_email(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: EmailSendRequest,
        ):
            service = EmailService(db)
            message = EmailMessage(
                to=body.to,
                subject=body.subject,
                html_body=body.html_body,
                text_body=body.text_body,
                cc=body.cc or [],
                bcc=body.bcc or [],
            )
            result = await service.send(message)

            # 记录日志
            from app.models.system.email_log import EmailLog
            from app.core.base_model import utc_now
            log = EmailLog(
                to_address=", ".join(body.to),
                cc=", ".join(body.cc) if body.cc else None,
                bcc=", ".join(body.bcc) if body.bcc else None,
                subject=body.subject,
                triggered_by="manual",
                status="sent" if result.success else "failed",
                html_body=body.html_body[:50000] if body.html_body else None,
                text_body=body.text_body[:50000] if body.text_body else None,
                error_message=result.error,
                sent_at=utc_now() if result.success else None,
            )
            db.add(log)
            await db.commit()

            return success(data={
                "success": result.success,
                "message": result.message,
                "error": result.error,
            })

        @router.post("/test", summary="发送测试邮件")
        @action_create("action.email_log.test")
        async def send_test_email(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: EmailTestRequest,
        ):
            service = EmailService(db)
            message = EmailMessage(
                to=[body.to],
                subject=_("email.test.subject"),
                html_body=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1890ff;">NovusAI SaaS</h2>
                    <p>{_("email.test.body")}</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
                    <p style="color: #999; font-size: 12px;">{_("email.test.footer")}</p>
                </div>
                """,
                text_body=_("email.test.body"),
            )
            result = await service.send(message)

            # 记录日志
            from app.models.system.email_log import EmailLog
            from app.core.base_model import utc_now
            log = EmailLog(
                to_address=body.to,
                subject=_("email.test.subject"),
                triggered_by="test",
                status="sent" if result.success else "failed",
                html_body=message.html_body[:50000] if message.html_body else None,
                text_body=message.text_body[:50000] if message.text_body else None,
                error_message=result.error,
                sent_at=utc_now() if result.success else None,
            )
            db.add(log)
            await db.commit()

            return success(data={
                "success": result.success,
                "message": result.message,
                "error": result.error,
            })


router = AdminEmailLogController.get_router()
