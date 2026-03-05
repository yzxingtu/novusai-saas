"""
邮件日志管理 API

提供邮件发送日志查看 + 手动发送邮件接口（平台管理员专用）
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_read,
    permission_resource,
)
from app.repositories.system.email_log_repository import EmailLogRepository
from app.schemas.system.email_log import (
    EmailLogResponse,
    EmailSendRequest,
    EmailTestRequest,
)
from app.services.common.email_service import EmailMessage, EmailService
from app.services.common.email_templates import render_manual_email, render_test_email


@permission_resource(
    resource="email_log",
    name="menu.admin.email_log",
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:mail",
        path="/system/email-logs",
        component="admin/system/email-logs/index",
        parent="logs",
        sort_order=40,
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
            # 将用户输入的内容包裹在品牌 HTML 模板中
            raw_content = body.html_body or body.text_body or ""
            html_body, text_body = render_manual_email(
                subject=body.subject,
                content=raw_content,
            )

            service = EmailService(db)
            message = EmailMessage(
                to=body.to,
                subject=body.subject,
                html_body=html_body,
                text_body=text_body,
                cc=body.cc or [],
                bcc=body.bcc or [],
            )
            result = await service.send(message)

            # 记录日志
            from app.core.base_model import utc_now
            from app.models.system.email_log import EmailLog
            log = EmailLog(
                to_address=", ".join(body.to),
                cc=", ".join(body.cc) if body.cc else None,
                bcc=", ".join(body.bcc) if body.bcc else None,
                subject=body.subject,
                triggered_by="manual",
                status="sent" if result.success else "failed",
                html_body=html_body[:50000],
                text_body=text_body[:50000] if text_body else None,
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
            # 使用品牌模板渲染测试邮件
            subject, html_body, text_body = render_test_email(
                admin_name=current_admin.username,
            )

            service = EmailService(db)
            message = EmailMessage(
                to=[body.to],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            result = await service.send(message)

            # 记录日志
            from app.core.base_model import utc_now
            from app.models.system.email_log import EmailLog
            log = EmailLog(
                to_address=body.to,
                subject=subject,
                triggered_by="test",
                status="sent" if result.success else "failed",
                html_body=html_body[:50000],
                text_body=text_body[:50000] if text_body else None,
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
