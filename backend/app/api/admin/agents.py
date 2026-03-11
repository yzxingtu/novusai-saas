"""
平台端智能体管理 API / Platform Agent Management API

提供跨租户智能体列表、详情、状态管理接口（平台管理员专用）/ Provides cross-tenant agent list, details, and status management interfaces (for platform administrators only)
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import created, deleted, paginated, success
from app.enums.common import ResourceScopeEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.repositories.system.resource_tenant_assignment_repository import (
    ResourceTenantAssignmentRepository,
)
from app.schemas.ai.agent import AdminAgentCreate, AdminAgentUpdate
from app.schemas.ai.agent_access import AgentAccessUpdate
from app.schemas.ai.agent_memory import AgentMemoryToggleRequest
from app.schemas.ai.agent_kb_binding import (
    AgentKBBatchBindRequest,
    AgentKBBindingUpdate,
    AgentKBBindRequest,
)
from app.schemas.ai.agent_skill_binding import (
    AgentSkillBatchBindRequest,
    AgentSkillBindingUpdate,
    AgentSkillBindRequest,
)
from app.schemas.ai.agent_version import AgentPublishRequest, AgentRollbackRequest
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.agent_service import AdminAgentService, AgentService
from app.services.ai.agent_skill_binding_service import AgentSkillBindingService

SCOPES_NEEDING_ASSIGNMENT = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)

logger = LogManager.get_logger("ai")


def _build_admin_agent_item(agent) -> dict:
    """从 ORM 对象构建管理端列表项字典，提取 model_name + skill_packages / Build admin list item dict from ORM object, extracting model_name + skill_packages"""
    from app.api.shared._agent_helpers import build_agent_base_item

    item = build_agent_base_item(agent)
    item["scope"] = agent.scope
    item["model_id"] = agent.model_id
    return item


@permission_resource(
    resource="ai_agent",
    name="menu.admin.ai_agent",
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="ai_agent_mgmt",
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
    平台端智能体管理控制器 / Platform Agent Management Controller

    跨租户只读查看 + 状态管理 / Cross-tenant read-only view + status management
    """

    prefix = "/ai/agents"
    tags = [_("menu.tags.admin_agent_mgmt")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AdminAgentService,
            resource_name="ai_agent",
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
            获取全租户智能体列表 / Get all-tenant agent list

            支持 JSON:API 风格筛选、排序、分页 / Supports JSON:API style filtering, sorting, pagination
            - filter[tenant_id][eq]=1  按租户筛选 / Filter by tenant
            - filter[status][eq]=published  按状态筛选 / Filter by status
            - filter[name][ilike]=xxx  按名称模糊搜索 / Fuzzy search by name
            权限 / Permission: ai_agent:list
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
            管理端创建智能体 / Admin create agent

            支持 3 种 scope / Supports 3 scopes:
            - tenant: 属于指定租户（需提供 tenant_id） / Belongs to specified tenant (tenant_id required)
            - global: 全局共享（所有租户可见） / Global shared (visible to all tenants)
            - admin: 仅管理端可见 / Admin-only visible

            权限 / Permission: ai_agent:create
            """
            service = AdminAgentService(db)
            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            agent = await service.create(data)

            # 同步租户分配 / Sync tenant assignments
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
            管理端更新智能体 / Admin update agent

            权限 / Permission: ai_agent:update
            """
            service = AdminAgentService(db)
            agent = await service.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            agent = await service.update(agent_id, data)

            # 同步租户分配 / Sync tenant assignments
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
            管理端删除智能体 / Admin delete agent

            权限 / Permission: ai_agent:delete
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
            获取智能体详情（跨租户只读） / Get agent details (cross-tenant read-only)

            权限 / Permission: ai_agent:detail
            """
            admin_service = AdminAgentService(db)
            agent = await admin_service.get_by_id(agent_id)

            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            # 使用租户 Service 获取完整详情（含模型关联） / Use tenant Service to get full details (including model associations)
            service = AgentService(db, agent.tenant_id)
            detail = await service.get_agent_detail(agent_id)

            # 追加已分配的租户 ID 列表 / Append assigned tenant ID list
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
            管理员更新智能体状态（启用/禁用） / Admin update agent status (enable/disable)

            权限 / Permission: ai_agent:update_status
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
        # 技能绑定 / Skill Bindings
        # ========================================

        async def _get_agent_for_binding(db, agent_id: int):
            """获取智能体（用于绑定操作，需要 tenant_id） / Get agent (for binding operations, requires tenant_id)"""
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
            获取智能体绑定的所有技能包（含 SkillPackage 详情） / Get all skill packages bound to agent (with SkillPackage details)

            权限 / Permission: ai_agent:skills
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
            绑定单个技能包到智能体 / Bind a single skill package to agent

            权限 / Permission: ai_agent:bind_skill
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
            批量绑定技能包（替换模式：先清空再批量插入） / Batch bind skill packages (replace mode: clear then bulk insert)

            权限 / Permission: ai_agent:batch_bind_skills
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
            解绑指定技能包 / Unbind specified skill package

            权限 / Permission: ai_agent:unbind_skill
            """
            agent = await _get_agent_for_binding(db, agent_id)
            binding_service = AgentSkillBindingService(db, agent.tenant_id)
            await binding_service.unbind_package(
                agent_id=agent_id, package_id=package_id
            )
            await db.commit()
            return deleted()

        # ========================================
        # 知识库绑定 / Knowledge Base Bindings
        # ========================================

        @router.get("/{agent_id}/knowledge-bases", summary="获取智能体知识库绑定列表")
        @action_read("action.ai_agent.knowledge_bases")
        async def get_agent_kbs(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体绑定的所有知识库（含 KnowledgeBase 详情） / Get all knowledge bases bound to agent (with KnowledgeBase details)

            权限 / Permission: ai_agent:knowledge_bases
            """
            agent = await _get_agent_for_binding(db, agent_id)
            kb_service = AgentKBBindingService(db, agent.tenant_id)
            result = await kb_service.get_agent_kb_bindings(agent_id)
            return success(data=result)

        @router.post("/{agent_id}/knowledge-bases", summary="绑定知识库到智能体")
        @action_update("action.ai_agent.bind_kb")
        async def bind_kb(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentKBBindRequest,
            admin: ActiveAdmin,
        ):
            """
            绑定单个知识库到智能体 / Bind a single knowledge base to agent

            权限 / Permission: ai_agent:bind_kb
            """
            agent = await _get_agent_for_binding(db, agent_id)
            kb_service = AgentKBBindingService(db, agent.tenant_id)
            binding = await kb_service.bind_kb(
                agent_id=agent_id,
                knowledge_base_id=data.knowledge_base_id,
                weight=data.weight,
                sort_order=data.sort_order,
                enabled=data.enabled,
            )
            await db.commit()
            return created(data=binding.to_dict())

        @router.put("/{agent_id}/knowledge-bases/batch", summary="批量绑定知识库（替换模式）")
        @action_update("action.ai_agent.batch_bind_kbs")
        async def batch_bind_kbs(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentKBBatchBindRequest,
            admin: ActiveAdmin,
        ):
            """
            批量绑定知识库（替换模式：先清空再批量插入） / Batch bind knowledge bases (replace mode: clear then bulk insert)

            权限 / Permission: ai_agent:batch_bind_kbs
            """
            agent = await _get_agent_for_binding(db, agent_id)
            kb_service = AgentKBBindingService(db, agent.tenant_id)
            bindings = await kb_service.batch_bind(
                agent_id=agent_id,
                knowledge_base_ids=data.knowledge_base_ids,
            )
            await db.commit()
            return success(data=[b.to_dict() for b in bindings])

        @router.put("/{agent_id}/knowledge-bases/{binding_id}", summary="更新知识库绑定配置")
        @action_update("action.ai_agent.update_kb_binding")
        async def update_kb_binding(
            request: Request,
            db: DbSession,
            agent_id: int,
            binding_id: int,
            data: AgentKBBindingUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新知识库绑定（weight / enabled / sort_order） / Update knowledge base binding (weight / enabled / sort_order)

            权限 / Permission: ai_agent:update_kb_binding
            """
            agent = await _get_agent_for_binding(db, agent_id)
            kb_service = AgentKBBindingService(db, agent.tenant_id)
            updated = await kb_service.update_binding(
                binding_id=binding_id,
                data=data.model_dump(exclude_unset=True),
            )
            if updated.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_kb_binding.error.binding_not_found")
                )
            await db.commit()
            return success(data=updated.to_dict())

        @router.delete("/{agent_id}/knowledge-bases/{knowledge_base_id}", summary="解绑知识库")
        @action_update("action.ai_agent.unbind_kb")
        async def unbind_kb(
            request: Request,
            db: DbSession,
            agent_id: int,
            knowledge_base_id: int,
            admin: ActiveAdmin,
        ):
            """
            解绑指定知识库 / Unbind specified knowledge base

            权限 / Permission: ai_agent:unbind_kb
            """
            agent = await _get_agent_for_binding(db, agent_id)
            kb_service = AgentKBBindingService(db, agent.tenant_id)
            await kb_service.unbind_kb(
                agent_id=agent_id, knowledge_base_id=knowledge_base_id
            )
            await db.commit()
            return deleted()

        # ========================================
        # 发布 / 版本管理 / Publish / Version Management
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
            发布智能体（冻结当前配置为新版本快照） / Publish agent (freeze current config as new version snapshot)

            权限 / Permission: ai_agent:publish
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
            回滚智能体到指定版本 / Rollback agent to specified version

            权限 / Permission: ai_agent:rollback
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
            获取智能体版本历史列表 / Get agent version history list

            权限 / Permission: ai_agent:versions
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
            获取指定版本的完整配置快照 / Get full config snapshot of specified version

            权限 / Permission: ai_agent:version_detail
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            detail = await service.get_version_detail(agent_id, version)
            return success(data=detail)

        # ========================================
        # 访问权限配置 / Access Permission Config
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
            获取智能体访问权限配置 / Get agent access permission config

            权限 / Permission: ai_agent:access_config
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
            更新智能体访问权限配置 / Update agent access permission config

            权限 / Permission: ai_agent:update_access
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.tenant_id)
            config = await service.update_access_config(
                agent_id=agent_id,
                admin_role_ids=data.admin_role_ids,
                tenant_role_ids=data.tenant_role_ids,
                user_role_ids=data.user_role_ids,
            )
            await db.commit()
            return success(data=config, message=_("agent.access.updated"))

        @router.get("/{agent_id}/memory", summary="获取智能体记忆开关状态")
        @action_read("action.ai_agent.detail")
        async def get_memory_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取管理端智能体记忆配置状态 / Get admin agent memory config status

            权限 / Permission: ai_agent:detail
            """
            service = AdminAgentService(db)
            config = await service.get_memory_config(agent_id)
            return success(data=config)

        @router.put("/{agent_id}/memory", summary="更新智能体记忆开关")
        @action_update("action.ai_agent.update")
        async def update_memory_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            data: AgentMemoryToggleRequest,
        ):
            """
            管理端更新 Agent 级记忆开关 / Admin update agent-level memory toggle

            权限 / Permission: ai_agent:update
            """
            service = AdminAgentService(db)
            config = await service.set_memory_enabled(agent_id, data.enabled)
            await db.commit()
            return success(data=config, message=_("agent.updated"))


# 导出路由器 / Export router
router = AdminAgentController.get_router()

__all__ = ["router", "AdminAgentController"]
