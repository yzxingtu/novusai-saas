"""
平台端工具定义管理 API

提供跨租户工具列表、详情、状态管理，以及系统工具 CRUD（平台管理员专用）
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, BusinessException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.repositories.ai.tool_definition_repository import AdminToolDefinitionRepository
from app.schemas.ai.tool_definition import (
    ToolDefinitionCreate,
    ToolDefinitionUpdate,
    ToolDefinitionResponse,
)

logger = LogManager.get_logger("ai")


def _build_admin_tool_item(tool) -> dict:
    """从 ORM 对象构建管理端列表项字典"""
    return {
        "id": tool.id,
        "tenant_id": tool.tenant_id,
        "name": tool.name,
        "description": tool.description,
        "type": tool.type,
        "is_system": tool.is_system,
        "is_active": tool.is_active,
        "timeout": tool.timeout,
        "created_at": tool.created_at,
        "updated_at": tool.updated_at,
    }


@permission_resource(
    resource="ai_tool",
    name="menu.admin.ai_tool",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:wrench",
        path="/ai/tools",
        component="ai/tools/index",
        parent="ai_mgmt",
        sort_order=70,
    ),
)
class AdminToolController(GlobalController):
    """
    平台端工具定义管理控制器

    跨租户查看 + 系统工具 CRUD + 状态管理
    """

    prefix = "/ai/tools"
    tags = ["工具管理（平台）"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="全租户工具定义列表")
        @action_read("action.ai_tool.list")
        async def list_tools(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全租户工具定义列表

            支持 JSON:API 风格筛选、排序、分页
            - filter[tenant_id][eq]=1  按租户筛选
            - filter[is_system][eq]=true  筛选系统工具
            - filter[type][eq]=http  按类型筛选
            - filter[name][ilike]=xxx  按名称模糊搜索
            权限: ai_tool:list
            """
            repo = AdminToolDefinitionRepository(db)
            items, total = await repo.query_list(query)

            result = [_build_admin_tool_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{tool_id}", summary="工具定义详情")
        @action_read("action.ai_tool.detail")
        async def get_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取工具定义详情（跨租户只读）

            权限: ai_tool:detail
            """
            repo = AdminToolDefinitionRepository(db)
            tool = await repo.get_by_id(tool_id)

            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            return success(
                data=ToolDefinitionResponse.model_validate(tool, from_attributes=True),
            )

        @router.post("", summary="创建系统工具")
        @action_create("action.ai_tool.create")
        async def create_system_tool(
            request: Request,
            db: DbSession,
            data: ToolDefinitionCreate,
            admin: ActiveAdmin,
        ):
            """
            创建系统工具（is_system=True, tenant_id=NULL）

            权限: ai_tool:create
            """
            repo = AdminToolDefinitionRepository(db)

            tool_data = data.model_dump(exclude_unset=True)
            tool_data["is_system"] = True
            tool_data["tenant_id"] = None

            tool = await repo.create(tool_data)
            await db.commit()

            return success(
                data=ToolDefinitionResponse.model_validate(tool, from_attributes=True),
                message=_("common.success"),
            )

        @router.put("/{tool_id}", summary="更新系统工具")
        @action_update("action.ai_tool.update")
        async def update_system_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            data: ToolDefinitionUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新系统工具（仅允许修改 is_system=True 的工具）

            权限: ai_tool:update
            """
            repo = AdminToolDefinitionRepository(db)
            tool = await repo.get_by_id(tool_id)

            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            if not tool.is_system:
                raise BusinessException(
                    message=_("tool_definition.error.tenant_tool_readonly")
                )

            update_data = data.model_dump(exclude_unset=True)
            updated = await repo.update(tool_id, update_data)
            await db.commit()

            return success(
                data=ToolDefinitionResponse.model_validate(updated, from_attributes=True),
                message=_("common.success"),
            )

        @router.delete("/{tool_id}", summary="删除系统工具")
        @action_delete("action.ai_tool.delete")
        async def delete_system_tool(
            request: Request,
            db: DbSession,
            tool_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除系统工具（仅允许删除 is_system=True 的工具）

            权限: ai_tool:delete
            """
            repo = AdminToolDefinitionRepository(db)
            tool = await repo.get_by_id(tool_id)

            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            if not tool.is_system:
                raise BusinessException(
                    message=_("tool_definition.error.tenant_tool_readonly")
                )

            await repo.delete(tool_id)
            await db.commit()

            return success(message=_("common.success"))

        @router.put("/{tool_id}/status", summary="切换工具状态")
        @action_update("action.ai_tool.update_status")
        async def toggle_tool_status(
            request: Request,
            db: DbSession,
            tool_id: int,
            admin: ActiveAdmin,
        ):
            """
            切换工具 is_active 状态

            权限: ai_tool:update_status
            """
            repo = AdminToolDefinitionRepository(db)
            tool = await repo.get_by_id(tool_id)

            if not tool:
                raise NotFoundException(message=_("tool_definition.error.not_found"))

            updated = await repo.update(tool_id, {"is_active": not tool.is_active})
            await db.commit()

            return success(
                data=_build_admin_tool_item(updated),
                message=_("common.success"),
            )


# 导出路由器
router = AdminToolController.get_router()

__all__ = ["router", "AdminToolController"]
