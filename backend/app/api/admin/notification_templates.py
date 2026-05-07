"""
平台管理端通知模板管理 API / Platform Admin Notification Template Management API

管理员可查看、编辑通知模板的渠道配置、优先级、启用状态。
Admins can view and edit notification template channel config, priority, and enable status.
系统内置模板不可删除，仅可编辑渠道和优先级。
System built-in templates cannot be deleted, only channels and priority can be edited.
"""

from fastapi import Request
from pydantic import BaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.models.common.notification_template import NotificationTemplate
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    permission_resource,
)
from app.repositories.common.notification_template_repository import (
    NotificationTemplateRepository,
)


class UpdateTemplateRequest(BaseModel):
    """更新通知模板请求 / Update notification template request"""

    channels: list[str] | None = Field(None, description=_("api.param.channels"))
    priority: str | None = Field(None, description=_("api.param.priority"))
    title_template: str | None = Field(None, description=_("api.param.title_template"))
    body_template: str | None = Field(None, description=_("api.param.body_template"))
    is_enabled: bool | None = Field(None, description=_("api.param.is_enabled"))
    enabled: bool | None = Field(None, description=_("api.param.is_enabled"))


@permission_resource(
    resource="notification_template",
    name="menu.admin.notification_template",
    scope=PermissionScope.ADMIN,
    parent_resource="system_config",
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
    平台端通知模板管理控制器 / Platform Notification Template Management Controller

    管理通知模板的渠道配置、优先级等 / Manage notification template channel config, priority, etc.
    """

    prefix = "/notification-templates"
    tags = [_("menu.tags.notification_template")]

    @staticmethod
    def _preview_payload(
        template: NotificationTemplate | None,
    ) -> dict[str, list[str] | str | None]:
        if template is None:
            return {
                "title_template": "",
                "body_template": None,
                "channels": [],
                "priority": "normal",
            }
        return {
            "title_template": template.title_template,
            "body_template": template.body_template,
            "channels": template.channels or [],
            "priority": template.priority,
        }

    async def _serialize_template(
        self,
        repo: NotificationTemplateRepository,
        template: NotificationTemplate,
        *,
        tenant_name_map: dict[int, str] | None = None,
    ) -> dict:
        effective = (
            await repo.resolve_effective_template(template.code, template.tenant_id)
        ) or template
        tenant_name = None
        if template.tenant_id is not None and tenant_name_map is not None:
            tenant_name = tenant_name_map.get(template.tenant_id)
        return {
            "id": template.id,
            "code": template.code,
            "category": template.category,
            "title_template": template.title_template,
            "body_template": template.body_template,
            "channels": template.channels,
            "priority": template.priority,
            "scope": template.scope,
            "source": template.source,
            "plugin_name": template.plugin_name,
            "is_enabled": template.is_enabled,
            "enabled": template.is_enabled,
            "is_system": template.is_system,
            "tenant_id": template.tenant_id,
            "tenant_name": tenant_name,
            "override_of": template.override_of,
            "is_override": template.override_of is not None,
            "locked_fields": template.locked_fields,
            "effective_preview": self._preview_payload(effective),
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }

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
            """获取所有通知模板（分页 + 筛选） / Get all notification templates (paginated + filtered)"""
            repo = NotificationTemplateRepository(db)
            items, total = await repo.query_list(query)
            tenant_name_map = await repo.get_tenant_name_map(
                {template.tenant_id for template in items if template.tenant_id}
            )

            result = [
                await self._serialize_template(
                    repo,
                    t,
                    tenant_name_map=tenant_name_map,
                )
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
            更新通知模板的渠道配置、优先级等 / Update notification template channel config, priority, etc.

            系统内置模板仅允许修改 channels 和 priority。
            System built-in templates only allow modifying channels and priority.
            """
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                raise NotFoundException(message=_("common.not_found"))

            update_fields = data.model_dump(exclude_unset=True)
            if "enabled" in update_fields:
                update_fields["is_enabled"] = update_fields.pop("enabled")
            if not update_fields:
                return success(message=_("common.success"))

            for field, value in update_fields.items():
                if template.locked_fields and field in template.locked_fields:
                    continue
                setattr(template, field, value)

            await db.commit()
            await db.refresh(template)
            tenant_name_map = await repo.get_tenant_name_map(
                {template.tenant_id} if template.tenant_id else set()
            )

            return success(
                data=await self._serialize_template(
                    repo,
                    template,
                    tenant_name_map=tenant_name_map,
                ),
                message=_("common.update_success"),
            )

        @router.get("/{template_id}/effective-preview", summary="获取通知模板生效预览")
        @action_read("action.notification_template.list")
        async def effective_preview(
            request: Request,
            db: DbSession,
            template_id: int,
            admin: ActiveAdmin,
        ):
            _ = (request, admin)
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                raise NotFoundException(message=_("common.not_found"))

            effective = (
                await repo.resolve_effective_template(template.code, template.tenant_id)
            ) or template
            return success(data=self._preview_payload(effective))

        @router.post("/{template_id}/restore-default", summary="恢复通知模板默认配置")
        @action_update("action.notification_template.update")
        async def restore_default(
            request: Request,
            db: DbSession,
            template_id: int,
            admin: ActiveAdmin,
        ):
            _ = (request, admin)
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                raise NotFoundException(message=_("common.not_found"))
            default_template = await repo.resolve_default_template(template)
            if default_template is None:
                raise NotFoundException(message=_("common.not_found"))

            template.soft_delete()
            await db.commit()
            await db.refresh(default_template)
            tenant_name_map = await repo.get_tenant_name_map(
                {default_template.tenant_id} if default_template.tenant_id else set()
            )
            return success(
                data=await self._serialize_template(
                    repo,
                    default_template,
                    tenant_name_map=tenant_name_map,
                ),
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
            发送测试通知给当前管理员 / Send test notification to current admin

            使用模板定义的所有渠道发送一条测试通知，
            占位符使用示例数据自动填充。
            Sends a test notification via all channels defined in the template,
            placeholders are auto-filled with sample data.
            """
            repo = NotificationTemplateRepository(db)
            template = await repo.get_by_id(template_id)
            if not template:
                raise NotFoundException(message=_("common.not_found"))

            from app.services.common.notification_service import NotificationService

            # 构造示例数据（覆盖所有已知占位符） / Build sample data (cover all known placeholders)
            sample_data = {
                "content": "这是一条测试通知内容",
                "message": "这是一条测试安全警告消息",
                "version": "2.1.0",
                "start_time": "2025-03-01 02:00",
                "duration": "2 小时",
                "tenant_name": "演示企业",
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
                tenant_id=None,
                force_all_channels=True,
            )
            await db.commit()

            return success(
                data={"sent": count, "template_code": template.code},
                message=_("common.success"),
            )


router = AdminNotificationTemplateController.get_router()

__all__ = ["router", "AdminNotificationTemplateController"]
