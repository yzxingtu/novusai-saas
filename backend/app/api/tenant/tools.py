"""
租户端工具管理 API

提供工具定义的 CRUD 和测试执行接口
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, created, deleted, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.ai.tool_definition import (
    ToolDefinitionCreate,
    ToolDefinitionUpdate,
    ToolTestRequest,
)
from app.services.ai.tool_definition_service import ToolDefinitionService


@permission_resource(
    resource="agent_tool",
    name="menu.tenant.agent_tool",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:wrench",
        path="/ai/tools",
        component="ai/tools/index",
        parent="ai_mgmt",
        sort_order=15,
    ),
)
class TenantToolController(TenantController):
    """
    租户工具管理控制器

    提供工具定义 CRUD、测试执行等操作
    """

    prefix = "/ai/tools"
    tags = ["工具管理"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取工具列表")
        @action_read("action.agent_tool.list")
        async def list_tools(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取工具定义列表

            支持 JSON:API 分页、筛选、排序
            权限: agent_tool:list
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            result = [item.to_dict() for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{tool_id}", summary="获取工具详情")
        @action_read("action.agent_tool.detail")
        async def get_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取工具定义详情

            权限: agent_tool:detail
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)
            tool = await service.get(tool_id)
            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            return success(data=tool.to_dict())

        @router.post("", summary="创建工具")
        @action_create("action.agent_tool.create")
        async def create_tool(
            request: Request,
            db: DbSession,
            data: ToolDefinitionCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建工具定义

            权限: agent_tool:create
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)
            tool = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(data=tool.to_dict(), message=_("tool_definition.created"))

        @router.put("/{tool_id}", summary="更新工具")
        @action_update("action.agent_tool.update")
        async def update_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            data: ToolDefinitionUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新工具定义

            系统内置工具不可编辑
            权限: agent_tool:update
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)

            tool = await service.get(tool_id)
            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(tool_id, update_data)
            await db.commit()

            return success(data=updated.to_dict(), message=_("tool_definition.updated"))

        @router.delete("/{tool_id}", summary="删除工具")
        @action_delete("action.agent_tool.delete")
        async def delete_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除工具定义（软删除）

            系统内置工具不可删除
            权限: agent_tool:delete
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)

            tool = await service.get(tool_id)
            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            await service.delete(tool_id)
            await db.commit()

            return deleted(message=_("tool_definition.deleted"))

        @router.post("/{tool_id}/test", summary="测试执行工具")
        @action_update("action.agent_tool.test")
        async def test_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            data: ToolTestRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            测试执行工具

            传入参数模拟执行，返回执行结果
            权限: agent_tool:test
            """
            service = ToolDefinitionService(db, tenant_admin.tenant_id)
            result = await service.test_execute(tool_id, data.arguments)

            return success(data=result)


# 导出路由器
router = TenantToolController.get_router()

__all__ = ["router", "TenantToolController"]
