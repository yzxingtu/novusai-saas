"""
租户端智能体管理 API

提供智能体的 CRUD、发布等接口
"""

from fastapi import Request

from app.ai.agent_quota import AgentQuotaConfig, AgentQuotaManager
from app.ai.agent_stats import AgentStatsManager
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.core.response import created, deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.agent import AgentCreate, AgentUpdate
from app.schemas.ai.agent_access import AgentAccessUpdate
from app.schemas.ai.agent_memory import AgentMemoryDisableRequest
from app.services.ai.agent_service import AgentService


async def _ensure_tenant_owned_agent(db, tenant_id: int, agent_id: int):
    """
    确保智能体为租户自有（tenant_id 与当前租户匹配）才允许变更操作。

    平台创建的全局智能体（tenant_id=null）及其他租户的智能体对当前租户只读，
    不允许编辑、发布、回滚、绑定技能等变更操作。
    """
    service = AgentService(db, tenant_id)
    agent = await service.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))
    if agent.tenant_id != tenant_id:
        raise BusinessException(message=_("agent.error.system_protected"))
    return agent


def _build_agent_list_item(agent) -> dict:
    """从 ORM 对象构建列表项字典，提取 model_name + skill_count"""
    from app.api.shared._agent_helpers import build_agent_base_item

    item = build_agent_base_item(agent)
    item["visibility"] = agent.visibility
    return item


@permission_resource(
    resource="agent",
    name="menu.tenant.agent",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_workspace",
    menu=MenuConfig(
        icon="lucide:bot",
        path="/ai/agents",
        component="ai/agents/index",
        parent="ai_workspace",
        sort_order=10,
    ),
)
class TenantAgentController(TenantController):
    """
    租户智能体管理控制器

    提供智能体 CRUD、发布等操作
    """

    prefix = "/ai/agents"
    tags = [_("menu.tags.tenant_agent_mgmt")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
        register_tenant_recycle_bin_routes(
            router=router,
            service_class=AgentService,
            resource_name="agent",
            serialize=_build_agent_list_item,
        )

        @router.get("", summary="获取智能体列表")
        @action_read("action.agent.list")
        async def list_agents(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取智能体列表

            支持 JSON:API 分页、筛选、排序
            权限: agent:list
            """
            service = AgentService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            result = [_build_agent_list_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{agent_id}", summary="获取智能体详情")
        @action_read("action.agent.detail")
        async def get_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体详情

            权限: agent:detail
            """
            service = AgentService(db, tenant_admin.tenant_id)
            result = await service.get_agent_detail(agent_id)

            return success(data=result)

        @router.post("", summary="创建智能体")
        @action_create("action.agent.create")
        async def create_agent(
            request: Request,
            db: DbSession,
            data: AgentCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建智能体

            权限: agent:create
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(data=agent.to_dict(), message=_("agent.created"))

        @router.put("/{agent_id}", summary="更新智能体")
        @action_update("action.agent.update")
        async def update_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新智能体

            权限: agent:update
            """
            service = AgentService(db, tenant_admin.tenant_id)

            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(agent_id, update_data)
            await db.commit()

            return success(data=updated.to_dict(), message=_("agent.updated"))

        @router.delete("/{agent_id}", summary="删除智能体")
        @action_delete("action.agent.delete")
        async def delete_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除智能体（软删除）

            权限: agent:delete
            """
            service = AgentService(db, tenant_admin.tenant_id)

            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            await service.delete(agent_id)
            await db.commit()

            return deleted(message=_("agent.deleted"))

        @router.get("/{agent_id}/quota-usage", summary="获取智能体配额用量")
        @action_read("action.agent.quota_usage")
        async def get_quota_usage(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体配额使用情况

            权限: agent:quota_usage
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            config = AgentQuotaConfig.from_dict(agent.quota_config)
            usage = await AgentQuotaManager.get_usage_summary(
                tenant_id=tenant_admin.tenant_id,
                agent_id=agent_id,
                config=config,
            )

            return success(data=usage)

        # ========================================
        # 用量统计
        # ========================================

        @router.get("/{agent_id}/stats", summary="获取智能体用量统计")
        @action_read("action.agent.stats")
        async def get_agent_stats(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体用量统计（对话次数、Token 消耗）

            权限: agent:stats
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            stats = await AgentStatsManager.get_stats(
                tenant_id=tenant_admin.tenant_id,
                agent_id=agent_id,
            )

            return success(data=stats)

        # ========================================
        # 访问权限配置
        # ========================================

        @router.get("/{agent_id}/access", summary="获取智能体访问权限配置")
        @action_read("action.agent.access_config")
        async def get_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体访问权限配置

            权限: agent:access_config
            """
            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.get_access_config(agent_id)

            return success(data=config)

        @router.put("/{agent_id}/access", summary="更新智能体访问权限配置")
        @action_update("action.agent.update_access")
        async def update_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentAccessUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新智能体访问权限配置

            权限: agent:update_access
            """
            await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.update_access_config(
                agent_id=agent_id,
                visibility=data.visibility,
                access_type=data.access_type,
                org_node_ids=data.org_node_ids,
                user_ids=data.user_ids,
            )
            await db.commit()

            return success(data=config, message=_("agent.access.updated"))

        @router.get("/{agent_id}/memory", summary="获取智能体记忆开关状态")
        @action_read("action.agent.detail")
        async def get_memory_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取租户侧智能体记忆配置状态

            权限: agent:detail
            """
            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.get_memory_config(agent_id)
            return success(data=config)

        @router.put("/{agent_id}/memory", summary="设置租户侧记忆关闭覆盖")
        @action_update("action.agent.update")
        async def update_memory_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentMemoryDisableRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            设置租户侧“关闭记忆/恢复默认”

            权限: agent:update
            """
            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.set_memory_disabled(
                agent_id=agent_id,
                disabled=data.disabled,
            )
            await db.commit()
            return success(data=config, message=_("agent.updated"))

        # 包含子路由模块
        from app.api.tenant._agent_batch import router as batch_router
        from app.api.tenant._agent_skills import router as skills_router
        from app.api.tenant._agent_version import router as version_router

        router.include_router(version_router)
        router.include_router(skills_router)
        router.include_router(batch_router)


# 导出路由器
router = TenantAgentController.get_router()

__all__ = ["router", "TenantAgentController"]
