"""
平台管理端通知模板管理 API

管理员可查看、编辑通知模板的渠道配置、优先级、启用状态。
系统内置模板不可删除，仅可编辑渠道和优先级。
"""

from fastapi import Request
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.models.common.notification_template import NotificationTemplate
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
)
from app.repositories.common.notification_template_repository import (
    NotificationTemplateRepository,
)


class UpdateTemplateRequest(BaseModel):
    """更新通知模板请求"""
    channels: list[str] | None = Field(None, description="投递渠道列表")
    priority: str | None = Field(None, description="优先级: low/normal/high/urgent")
    title_template: str | None = Field(None, description="标题模板")
    body_template: str | None = Field(None, description="正文模板")


@permission_resource(
    resource="notification_template",
    name="menu.admin.notification_template",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:bell-ring",
        path="/system/notification-templates",
        component="system/notification-templates/index",
        parent="system_mgmt",
        sort_order=55,
    ),
)
class AdminNotificationTemplateController(GlobalController):
    """
    平台端通知模板管理控制器

    管理通知模板的渠道配置、优先级等
    """

    prefix = "/notification-templates"
    tags = [_("menu.tags.notification_template")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取通知模板列表")
        @action_read("action.notification_template.list")
        async def list_templates(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """获取所有通知模板（分页 + 筛选）"""
            repo = NotificationTemplateRepository(db)
            items, total = await repo.query_list(query)

            result = [
                {
                    "id": t.id,
                    "code": t.code,
                    "category": t.category,
                    "title_template": t.title_template,
                    "body_template": t.body_template,
                    "channels": t.channels,
                    "priority": t.priority,
                    "is_system": t.is_system,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in items
            ]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.put("/{template_id}", summary="更新通知模板")
        @action_update("action.notification_template.update")
        async def update_template(
            request: Request,
            db: DbSession,
            template_id: int,
            admin: ActiveAdmin,
            data: UpdateTemplateRequest,
        ):
            """
            更新通知模板的渠道配置、优先级等

            系统内置模板仅允许修改 channels 和 priority。
            """
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("common.not_found"))

            update_fields = data.model_dump(exclude_unset=True)
            if not update_fields:
                return success(message=_("common.success"))

            for field, value in update_fields.items():
                setattr(template, field, value)

            await db.commit()
            await db.refresh(template)

            return success(
                data={
                    "id": template.id,
                    "code": template.code,
                    "category": template.category,
                    "title_template": template.title_template,
                    "body_template": template.body_template,
                    "channels": template.channels,
                    "priority": template.priority,
                    "is_system": template.is_system,
                },
                message=_("common.update_success"),
            )


        @router.post("/{template_id}/test", summary="测试通知模板")
        @action_read("action.notification_template.test")
        async def test_template(
            request: Request,
            db: DbSession,
            template_id: int,
            admin: ActiveAdmin,
        ):
            """
            发送测试通知给当前管理员

            使用模板定义的所有渠道发送一条测试通知，
            占位符使用示例数据自动填充。
            """
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("common.not_found"))

            from app.services.common.notification_service import NotificationService

            # 构造示例数据（覆盖所有已知占位符）
            sample_data = {
                "content": "这是一条测试通知内容",
                "message": "这是一条测试安全警告消息",
                "version": "2.1.0",
                "start_time": "2025-03-01 02:00",
                "duration": "2 小时",
                "tenant_name": "演示租户",
                "admin_name": admin.nickname or admin.username,
                "user_name": admin.nickname or admin.username,
                "task_name": "test_task",
                "task_id": "test-001",
                "error": "测试错误信息",
                "domain": "example.com",
                "days_remaining": 7,
                "progress": 75,
                "completed": 75,
                "total": 100,
                "kb_name": "测试知识库",
                "doc_count": 50,
                "model_name": "gpt-4",
                "usage_percent": 85,
                "filename": "export_2025.csv",
                "count": 1000,
                "old_plan": "基础版",
                "new_plan": "专业版",
                "plugin_name": "示例插件",
                "new_version": "1.2.0",
                "current_version": "1.1.0",
                "role_name": "管理员",
                "old_role": "普通用户",
                "new_role": "管理员",
                "operator": "系统",
                "ip": "192.168.1.100",
                "location": "北京",
            }

            service = NotificationService(db)
            count = await service.send(
                template_code=template.code,
                recipients=[("admin", admin.id)],
                data=sample_data,
                force_all_channels=True,
            )
            await db.commit()

            return success(
                data={"sent": count, "template_code": template.code},
                message=_("common.success"),
            )


router = AdminNotificationTemplateController.get_router()

__all__ = ["router", "AdminNotificationTemplateController"]
