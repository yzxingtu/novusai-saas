"""
平台端智能体管理 API

提供跨租户智能体列表、详情、状态管理接口（平台管理员专用）
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
from app.enums.common import ResourceScopeEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.repositories.system.resource_tenant_assignment_repository import ResourceTenantAssignmentRepository

SCOPES_NEEDING_ASSIGNMENT = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.ai.agent import AdminAgentCreate, AdminAgentUpdate
from app.schemas.ai.agent_access import AgentAccessUpdate
from app.schemas.ai.agent_skill_binding import (
    AgentSkillBindRequest,
    AgentSkillBatchBindRequest,
    AgentSkillBindingUpdate,
)
from app.schemas.ai.agent_version import AgentPublishRequest, AgentRollbackRequest
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.services.ai.agent_service import AgentService, AdminAgentService
from app.services.ai.agent_skill_binding_service import AgentSkillBindingService

logger = LogManager.get_logger("ai")


def _build_admin_agent_item(agent) -> dict:
    """从 ORM 对象构建管理端列表项字典，提取 model_name + skill_packages"""
    from app.api.shared._agent_helpers import build_agent_base_item

    item = build_agent_base_item(agent)
    item["scope"] = agent.scope
    item["model_id"] = agent.model_id
    return item


@permission_resource(
    resource="ai_agent",
    name="menu.admin.ai_agent",
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:bot",
        path="/ai/agents",
        component="ai/agents/index",
        parent="ai_app",
        sort_order=10,
    ),
)
class AdminAgentController(GlobalController):
    """
    平台端智能体管理控制器

    跨租户只读查看 + 状态管理
    """

    prefix = "/ai/agents"
    tags = [_("menu.tags.admin_agent_mgmt")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AdminAgentService,
            resource_name="admin_agent",
            serialize=_build_admin_agent_item,
        )

        @router.get("", summary="全租户智能体列表")
        @action_read("action.ai_agent.list")
        async def list_agents(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全租户智能体列表

            支持 JSON:API 风格筛选、排序、分页
            - filter[tenant_id][eq]=1  按租户筛选
            - filter[status][eq]=published  按状态筛选
            - filter[name][ilike]=xxx  按名称模糊搜索
            权限: ai_agent:list
            """
            service = AdminAgentService(db)
            items, total = await service.query_list(query)

            result = [_build_admin_agent_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.post("", summary="创建智能体（支持全局/租户/管理端专属）")
        @action_create("action.ai_agent.create")
        async def create_agent(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: AdminAgentCreate,
        ):
            """
            管理端创建智能体

            支持 3 种 scope:
            - tenant: 属于指定租户（需提供 tenant_id）
            - global: 全局共享（所有租户可见）
            - admin: 仅管理端可见

            权限: ai_agent:create
            """
            service = AdminAgentService(db)
            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            agent = await service.create(data)

            # 同步租户分配
            if agent.scope in SCOPES_NEEDING_ASSIGNMENT and tenant_ids is not None:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.sync_assignments("agent", agent.id, tenant_ids)

            await db.commit()
            await db.refresh(agent)

            return created(
                data=_build_admin_agent_item(agent),
                message=_("agent.created"),
            )

        @router.put("/{agent_id}", summary="更新智能体")
        @action_update("action.ai_agent.update")
        async def update_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            body: AdminAgentUpdate,
        ):
            """
            管理端更新智能体

            权限: ai_agent:update
            """
            service = AdminAgentService(db)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            agent = await service.update(agent_id, data)

            # 同步租户分配
            effective_scope = agent.scope
            if effective_scope in SCOPES_NEEDING_ASSIGNMENT and tenant_ids is not None:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.sync_assignments("agent", agent_id, tenant_ids)
            elif effective_scope not in SCOPES_NEEDING_ASSIGNMENT:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.delete_all_for_resource("agent", agent_id)

            await db.commit()
            await db.refresh(agent)

            return success(
                data=_build_admin_agent_item(agent),
                message=_("agent.updated"),
            )

        @router.delete("/{agent_id}", summary="删除智能体")
        @action_delete("action.ai_agent.delete")
        async def delete_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            管理端删除智能体

            权限: ai_agent:delete
            """
            service = AdminAgentService(db)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            await service.delete(agent_id)
            await db.commit()

            return deleted(message=_("agent.deleted"))

        @router.get("/{agent_id}", summary="智能体详情")
        @action_read("action.ai_agent.detail")
        async def get_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体详情（跨租户只读）

            权限: ai_agent:detail
            """
            admin_service = AdminAgentService(db)
            agent = await admin_service.get_by_id(agent_id)

            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            # 使用租户 Service 获取完整详情（含模型关联）
            service = AgentService(db, agent.tenant_id)
            detail = await service.get_agent_detail(agent_id)

            # 追加已分配的租户 ID 列表
            if agent.scope in SCOPES_NEEDING_ASSIGNMENT:
                repo = ResourceTenantAssignmentRepository(db)
                detail["assigned_tenant_ids"] = await repo.get_assigned_tenant_ids(
                    "agent", agent_id
                )
            else:
                detail["assigned_tenant_ids"] = []

            return success(data=detail)

        @router.put("/{agent_id}/status", summary="更新智能体状态")
        @action_update("action.ai_agent.update_status")
        async def update_agent_status(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            status: str = Query(..., description="目标状态: disabled / draft / published"),
        ):
            """
            管理员更新智能体状态（启用/禁用）

            权限: ai_agent:update_status
            """
            service = AdminAgentService(db)
            updated = await service.update_status(agent_id, status)
            await db.commit()
            await db.refresh(updated)

            return success(
                data=_build_admin_agent_item(updated),
                message=_("common.success"),
            )

        # ========================================
        # 技能绑定
        # ========================================

        async def _get_agent_for_binding(db, agent_id: int):
            """获取智能体（用于绑定操作，需要 tenant_id）"""
            service = AdminAgentService(db)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))
            return agent

        @router.get("/{agent_id}/skills", summary="获取智能体技能包绑定列表")
        @action_read("action.ai_agent.skills")
        async def get_agent_skills(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体绑定的所有技能包（含 SkillPackage 详情）

            权限: ai_agent:skills
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)
            result = await binding_service.get_agent_packages(agent_id)
            return success(data=result)

        @router.post("/{agent_id}/skills", summary="绑定技能包到智能体")
        @action_update("action.ai_agent.bind_skill")
        async def bind_skill(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentSkillBindRequest,
            admin: ActiveAdmin,
        ):
            """
            绑定单个技能包到智能体

            权限: ai_agent:bind_skill
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)
            binding = await binding_service.bind_package(
                agent_id=agent_id,
                package_id=data.package_id,
                config_override=data.config_override,
                sort_order=data.sort_order,
                consent_mode=data.consent_mode,
            )
            await db.commit()
            return created(data=binding.to_dict())

        @router.put("/{agent_id}/skills/batch", summary="批量绑定技能包（替换模式）")
        @action_update("action.ai_agent.batch_bind_skills")
        async def batch_bind_skills(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentSkillBatchBindRequest,
            admin: ActiveAdmin,
        ):
            """
            批量绑定技能包（替换模式：先清空再批量插入）

            权限: ai_agent:batch_bind_skills
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)
            bindings = await binding_service.batch_bind(
                agent_id=agent_id,
                package_ids=data.package_ids,
                consent_modes=data.consent_modes,
            )
            await db.commit()
            return success(data=[b.to_dict() for b in bindings])

        @router.put("/{agent_id}/skills/{binding_id}", summary="更新技能绑定配置")
        @action_update("action.ai_agent.update_skill_binding")
        async def update_skill_binding(
            request: Request,
            db: DbSession,
            agent_id: int,
            binding_id: int,
            data: AgentSkillBindingUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新技能绑定（enabled / config_override / sort_order / consent_mode）

            权限: ai_agent:update_skill_binding
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)

            # update_binding internally checks existence
            updated = await binding_service.update_binding(
                binding_id=binding_id,
                data=data.model_dump(exclude_unset=True),
            )
            if updated.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_skill_binding.error.binding_not_found")
                )
            await db.commit()
            return success(data=updated.to_dict())

        @router.delete("/{agent_id}/skills/{package_id}", summary="解绑技能包")
        @action_update("action.ai_agent.unbind_skill")
        async def unbind_skill(
            request: Request,
            db: DbSession,
            agent_id: int,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            解绑指定技能包

            权限: ai_agent:unbind_skill
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)
            await binding_service.unbind_package(
                agent_id=agent_id, package_id=package_id
            )
            await db.commit()
            return deleted()

        # ========================================
        # 发布 / 版本管理
        # ========================================

        @router.post("/{agent_id}/publish", summary="发布智能体")
        @action_update("action.ai_agent.publish")
        async def publish_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            data: AgentPublishRequest,
        ):
            """
            发布智能体（冻结当前配置为新版本快照）

            权限: ai_agent:publish
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            result = await service.publish_agent(
                agent_id, change_log=data.change_log, created_by=admin.id,
            )
            await db.commit()
            return success(data=result.to_dict(), message=_("agent.published"))

        @router.post("/{agent_id}/rollback", summary="回滚智能体")
        @action_update("action.ai_agent.rollback")
        async def rollback_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            data: AgentRollbackRequest,
        ):
            """
            回滚智能体到指定版本

            权限: ai_agent:rollback
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            result = await service.rollback_agent(agent_id, data.version)
            await db.commit()
            return success(data=result.to_dict(), message=_("agent.version.rolled_back"))

        @router.get("/{agent_id}/versions", summary="获取版本历史")
        @action_read("action.ai_agent.versions")
        async def list_versions(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体版本历史列表

            权限: ai_agent:versions
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            versions = await service.get_versions(agent_id)
            return success(data=versions)

        @router.get("/{agent_id}/versions/{version}", summary="获取版本详情")
        @action_read("action.ai_agent.version_detail")
        async def get_version_detail(
            request: Request,
            db: DbSession,
            agent_id: int,
            version: int,
            admin: ActiveAdmin,
        ):
            """
            获取指定版本的完整配置快照

            权限: ai_agent:version_detail
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            detail = await service.get_version_detail(agent_id, version)
            return success(data=detail)

        # ========================================
        # 访问权限配置
        # ========================================

        @router.get("/{agent_id}/access", summary="获取访问权限配置")
        @action_read("action.ai_agent.access_config")
        async def get_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体访问权限配置

            权限: ai_agent:access_config
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            config = await service.get_access_config(agent_id)
            return success(data=config)

        @router.put("/{agent_id}/access", summary="更新访问权限配置")
        @action_update("action.ai_agent.update_access")
        async def update_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            data: AgentAccessUpdate,
        ):
            """
            更新智能体访问权限配置

            权限: ai_agent:update_access
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            config = await service.update_access_config(
                agent_id=agent_id,
                visibility=data.visibility,
                access_type=data.access_type,
                org_node_ids=data.org_node_ids,
                user_ids=data.user_ids,
            )
            await db.commit()
            return success(data=config, message=_("agent.access.updated"))


# 导出路由器
router = AdminAgentController.get_router()

__all__ = ["router", "AdminAgentController"]
