"""
平台端智能体管理 API / Platform Agent Management API

提供跨企业智能体列表、详情、状态管理接口（平台管理员专用）/ Provides cross-tenant agent list, details, and status management interfaces (for platform administrators only)
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
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuAIConfig,
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
from app.schemas.ai.agent_kb_binding import (
    AgentKBBatchBindRequest,
    AgentKBBindingUpdate,
    AgentKBBindRequest,
)
from app.schemas.ai.agent_memory import AgentMemoryToggleRequest
from app.schemas.ai.agent_skill_grant import (
    AgentSkillGrantBatchBindRequest,
    AgentSkillGrantCreate,
    AgentSkillGrantUpdate,
)
from app.schemas.ai.agent_version import AgentPublishRequest, AgentRollbackRequest
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.agent_service import AdminAgentService, AgentService
from app.services.ai.agent_skill_grant_service import AgentSkillGrantService
from app.services.system.plugin_managed_agent_sync_service import (
    PluginManagedAgentSyncService,
    SourcePluginInfo,
)

RESOURCE_SCOPES_NEEDING_ASSIGNMENT = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)

logger = LogManager.get_logger("ai")


def _build_source_plugin_payload(
    source_plugin: str | None,
    plugin_info: SourcePluginInfo | None,
) -> dict[str, object]:
    if not source_plugin:
        return {
            "source_plugin": None,
            "source_plugin_display_name": None,
            "source_plugin_enabled": False,
            "source_plugin_scope": None,
        }

    return {
        "source_plugin": source_plugin,
        "source_plugin_display_name": (
            plugin_info.display_name if plugin_info else source_plugin
        ),
        "source_plugin_enabled": plugin_info.enabled if plugin_info else False,
        "source_plugin_scope": plugin_info.scope if plugin_info else None,
    }


def _build_admin_agent_item(
    agent,
    plugin_meta_map: dict[str, SourcePluginInfo] | None = None,
) -> dict:
    """从 ORM 对象构建管理端列表项字典，提取 model_name + skills / Build admin list item dict from ORM object, extracting model_name + skills"""
    from app.api.shared._agent_helpers import build_agent_base_item

    item = build_agent_base_item(agent)
    item["model_id"] = agent.model_id
    item.update(
        _build_source_plugin_payload(
            getattr(agent, "source_plugin", None),
            (plugin_meta_map or {}).get(getattr(agent, "source_plugin", None) or ""),
        )
    )
    return item


@permission_resource(
    resource="ai_agent",
    name="menu.admin.ai_agent",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_agent_mgmt",
    menu=MenuConfig(
        ai=MenuAIConfig(
            description="Create, edit, publish, and manage AI agents and their behaviors",
            keywords=[
                "智能体",
                "智能代理",
                "AI 助手",
                "AI助手",
                "agent",
                "agents",
                "assistant",
                "assistants",
                "bot",
                "bots",
                "机器人",
            ],
            capabilities=[
                "create_agent",
                "edit_agent",
                "publish_agent",
                "view_agents",
            ],
            category="ai",
        ),
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

    跨企业只读查看 + 状态管理 / Cross-tenant read-only view + status management
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

        @router.get("/select", summary="获取智能体下拉选项")
        @action_read("action.ai_agent.list")
        async def select_agents(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(
                20, ge=1, le=100, description=_("api.param.page_size")
            ),
        ):
            """获取智能体远程下拉选项 / Get paginated remote agent select options."""
            service = AdminAgentService(db)
            response = await service.get_select_options(
                search=search,
                page=page,
                page_size=page_size,
            )
            return success(data=response, message=_("common.success"))

        @router.get("", summary="全企业智能体列表")
        @action_read("action.ai_agent.list")
        async def list_agents(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全企业智能体列表 / Get all-tenant agent list

            支持 JSON:API 风格筛选、排序、分页 / Supports JSON:API style filtering, sorting, pagination
            - filter[tenant_id][eq]=1  按企业筛选 / Filter by tenant
            - filter[status][eq]=published  按状态筛选 / Filter by status
            - filter[name][ilike]=xxx  按名称模糊搜索 / Fuzzy search by name
            权限 / Permission: ai_agent:list
            """
            service = AdminAgentService(db)
            items, total = await service.query_list(query)
            plugin_meta_map = await PluginManagedAgentSyncService(
                db
            ).get_source_plugin_map(
                getattr(item, "source_plugin", None) for item in items
            )

            result = [
                _build_admin_agent_item(item, plugin_meta_map=plugin_meta_map)
                for item in items
            ]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.post("", summary="创建智能体（支持全局/企业/管理端专属）")
        @action_create("action.ai_agent.create")
        async def create_agent(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: AdminAgentCreate,
        ):
            """
            管理端创建智能体 / Admin create agent

            使用统一资源作用域 ResourceScopeEnum（五类）与 tenant_ids 分配列表。
            权限 / Permission: ai_agent:create
            """
            service = AdminAgentService(db)
            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            agent = await service.create(data)

            # 同步企业分配 / Sync tenant assignments
            if (
                agent.scope in RESOURCE_SCOPES_NEEDING_ASSIGNMENT
                and tenant_ids is not None
            ):
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
            plugin_sync_service = PluginManagedAgentSyncService(db)
            if getattr(agent, "source_plugin", None):
                plugin_meta_map = await plugin_sync_service.get_source_plugin_map(
                    [agent.source_plugin]
                )
                plugin_info = plugin_meta_map.get(agent.source_plugin)
                if plugin_info is None:
                    raise NotFoundException(message=_("plugin.error.not_found"))
                requested_scope = data.get("scope")
                if requested_scope not in (None, plugin_info.scope):
                    raise BusinessException(
                        message=_("plugin.error.source_agent_scope_locked").format(
                            plugin=plugin_info.display_name or plugin_info.name,
                        )
                    )
                data["scope"] = plugin_info.scope
            agent = await service.update(agent_id, data)

            # 同步企业分配 / Sync tenant assignments
            eff_scope = agent.scope
            if getattr(agent, "source_plugin", None):
                await plugin_sync_service.sync_from_agent_update(agent, tenant_ids)
            elif (
                eff_scope in RESOURCE_SCOPES_NEEDING_ASSIGNMENT
                and tenant_ids is not None
            ):
                repo = ResourceTenantAssignmentRepository(db)
                await repo.sync_assignments("agent", agent_id, tenant_ids)
            elif eff_scope not in RESOURCE_SCOPES_NEEDING_ASSIGNMENT:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.delete_all_for_resource("agent", agent_id)

            await db.commit()
            await db.refresh(agent)
            plugin_meta_map = await plugin_sync_service.get_source_plugin_map(
                [getattr(agent, "source_plugin", None)]
            )

            return success(
                data=_build_admin_agent_item(agent, plugin_meta_map=plugin_meta_map),
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
            获取智能体详情（跨企业只读） / Get agent details (cross-tenant read-only)

            权限 / Permission: ai_agent:detail
            """
            admin_service = AdminAgentService(db)
            agent = await admin_service.get_by_id(agent_id)

            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            detail = agent.to_dict()
            detail["owner_tenant_id"] = agent.owner_tenant_id
            model_obj = getattr(agent, "model", None)
            detail["model_name"] = getattr(model_obj, "name", None)
            detail["model_code"] = getattr(model_obj, "code", None)
            memory_config = await admin_service.get_memory_config(agent_id)
            detail["memory_enabled"] = bool(getattr(agent, "memory_enabled", True))
            detail["effective_memory_enabled"] = memory_config[
                "effective_memory_enabled"
            ]
            detail["memory_disabled_by_tenant"] = False
            plugin_sync_service = PluginManagedAgentSyncService(db)
            plugin_meta_map = await plugin_sync_service.get_source_plugin_map(
                [getattr(agent, "source_plugin", None)]
            )
            detail.update(
                _build_source_plugin_payload(
                    getattr(agent, "source_plugin", None),
                    plugin_meta_map.get(getattr(agent, "source_plugin", None) or ""),
                )
            )

            # 追加已分配的企业 ID 列表 / Append assigned tenant ID list
            if getattr(agent, "source_plugin", None):
                detail["assigned_tenant_ids"] = (
                    await plugin_sync_service.get_effective_agent_assignment_ids(agent)
                )
            elif agent.scope in RESOURCE_SCOPES_NEEDING_ASSIGNMENT:
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
            status: str = Query(..., description=_("api.param.status_target")),
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

        @router.get("/{agent_id}/skills", summary="获取智能体技能绑定列表")
        @action_read("action.ai_agent.skills")
        async def get_agent_skills(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体绑定的所有技能（含 Skill / Package 详情） / Get all skills bound to agent (with skill and package details)

            权限 / Permission: ai_agent:skills
            """
            agent = await _get_agent_for_binding(db, agent_id)
            grant_service = AgentSkillGrantService(db, agent.owner_tenant_id)
            result = await grant_service.get_agent_skills(agent_id)
            return success(data=result)

        @router.post("/{agent_id}/skills", summary="绑定技能到智能体")
        @action_update("action.ai_agent.bind_skill")
        async def bind_skill(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentSkillGrantCreate,
            admin: ActiveAdmin,
        ):
            """
            绑定单个技能到智能体 / Bind a single skill to agent

            权限 / Permission: ai_agent:bind_skill
            """
            agent = await _get_agent_for_binding(db, agent_id)
            grant_service = AgentSkillGrantService(db, agent.owner_tenant_id)
            grant = await grant_service.bind_skill(
                agent_id=agent_id,
                skill_id=data.skill_id,
                config_override=data.config_override,
                sort_order=data.sort_order,
                default_consent_mode=data.default_consent_mode,
                capability_consent_overrides=data.capability_consent_overrides,
            )
            await db.commit()
            return created(data=grant_service.serialize_grant_public(grant))

        @router.put("/{agent_id}/skills/batch", summary="批量绑定技能（替换模式）")
        @action_update("action.ai_agent.batch_bind_skills")
        async def batch_bind_skills(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentSkillGrantBatchBindRequest,
            admin: ActiveAdmin,
        ):
            """
            批量绑定技能（替换模式：先清空再批量插入） / Batch bind skills (replace mode: clear then bulk insert)

            权限 / Permission: ai_agent:batch_bind_skills
            """
            agent = await _get_agent_for_binding(db, agent_id)
            grant_service = AgentSkillGrantService(db, agent.owner_tenant_id)
            grants = await grant_service.batch_bind(
                agent_id=agent_id,
                skill_ids=data.skill_ids,
                default_consent_modes=data.default_consent_modes,
            )
            await db.commit()
            return success(
                data=[grant_service.serialize_grant_public(g) for g in grants],
            )

        @router.put("/{agent_id}/skills/{binding_id}", summary="更新技能绑定配置")
        @action_update("action.ai_agent.update_skill_binding")
        async def update_skill_binding(
            request: Request,
            db: DbSession,
            agent_id: int,
            binding_id: int,
            data: AgentSkillGrantUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新技能绑定（enabled / config_override / sort_order / default_consent_mode）

            权限: ai_agent:update_skill_binding
            """
            agent = await _get_agent_for_binding(db, agent_id)
            grant_service = AgentSkillGrantService(db, agent.owner_tenant_id)

            updated = await grant_service.update_grant(
                grant_id=binding_id,
                data=data.model_dump(exclude_unset=True),
            )
            if updated.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_skill_grant.error.binding_not_found")
                )
            await db.commit()
            return success(data=grant_service.serialize_grant_public(updated))

        @router.delete("/{agent_id}/skills/{skill_id}", summary="解绑技能")
        @action_update("action.ai_agent.unbind_skill")
        async def unbind_skill(
            request: Request,
            db: DbSession,
            agent_id: int,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            解绑指定技能 / Unbind specified skill

            权限 / Permission: ai_agent:unbind_skill
            """
            agent = await _get_agent_for_binding(db, agent_id)
            grant_service = AgentSkillGrantService(db, agent.owner_tenant_id)
            await grant_service.unbind_skill(agent_id=agent_id, skill_id=skill_id)
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
            kb_service = AgentKBBindingService(db, agent.owner_tenant_id)
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
            kb_service = AgentKBBindingService(db, agent.owner_tenant_id)
            binding = await kb_service.bind_kb(
                agent_id=agent_id,
                knowledge_base_id=data.knowledge_base_id,
                weight=data.weight,
                sort_order=data.sort_order,
                enabled=data.enabled,
            )
            await db.commit()
            return created(data=kb_service.serialize_binding_public(binding))

        @router.put(
            "/{agent_id}/knowledge-bases/batch", summary="批量绑定知识库（替换模式）"
        )
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
            kb_service = AgentKBBindingService(db, agent.owner_tenant_id)
            bindings = await kb_service.batch_bind(
                agent_id=agent_id,
                knowledge_base_ids=data.knowledge_base_ids,
            )
            await db.commit()
            return success(
                data=[kb_service.serialize_binding_public(b) for b in bindings]
            )

        @router.put(
            "/{agent_id}/knowledge-bases/{binding_id}", summary="更新知识库绑定配置"
        )
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
            kb_service = AgentKBBindingService(db, agent.owner_tenant_id)
            updated = await kb_service.update_binding(
                binding_id=binding_id,
                data=data.model_dump(exclude_unset=True),
            )
            if updated.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_kb_binding.error.binding_not_found")
                )
            await db.commit()
            return success(data=kb_service.serialize_binding_public(updated))

        @router.delete(
            "/{agent_id}/knowledge-bases/{knowledge_base_id}", summary="解绑知识库"
        )
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
            kb_service = AgentKBBindingService(db, agent.owner_tenant_id)
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

            service = AgentService(db, agent.owner_tenant_id)
            result = await service.publish_agent(
                agent_id,
                change_log=data.change_log,
                created_by=admin.id,
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

            service = AgentService(db, agent.owner_tenant_id)
            result = await service.rollback_agent(agent_id, data.version)
            await db.commit()
            return success(
                data=result.to_dict(), message=_("agent.version.rolled_back")
            )

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

            service = AgentService(db, agent.owner_tenant_id)
            versions = await service.get_versions(agent_id)
            return success(data=versions)

        @router.get("/{agent_id}/versions/diff", summary="对比两个版本")
        @action_read("action.ai_agent.version_diff")
        async def diff_versions(
            request: Request,
            db: DbSession,
            agent_id: int,
            v1: int,
            v2: int,
            admin: ActiveAdmin,
        ):
            """
            对比两个版本的字段差异 / Compare field differences between two versions

            Query params: v1, v2
            权限 / Permission: ai_agent:version_diff
            """
            admin_svc = AdminAgentService(db)
            agent = await admin_svc.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            service = AgentService(db, agent.owner_tenant_id)
            diff = await service.diff_versions(agent_id, v1, v2)
            return success(data=diff)

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

            service = AgentService(db, agent.owner_tenant_id)
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

            service = AdminAgentService(db)
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

            service = AdminAgentService(db)
            patch = data.model_dump(exclude_unset=True)
            config = await service.update_access_config(agent_id, patch)
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
