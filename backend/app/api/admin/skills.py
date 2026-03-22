"""
平台端技能管理 API / Platform Skill Management API

提供跨企业技能列表、详情与 CRUD。
Provides cross-tenant skill listing, details, and CRUD.
"""

from typing import Any

from fastapi import Body, Query, Request

from app.api.shared._skill_helpers import (
    enrich_plugin_skill_info as _enrich_plugin_skill_info,
)
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import created, deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.skill import (
    SkillCreate,
    SkillResponse,
    SkillUpdate,
)
from app.services.ai.skill_service import AdminSkillService

logger = LogManager.get_logger("ai")


def _build_admin_skill_item(skill) -> dict:
    """从 ORM 对象构建管理端列表项字典 / Build admin list item dict from ORM object"""
    return {
        "id": skill.id,
        "tenant_id": skill.tenant_id,
        "package_id": skill.package_id,
        "name": skill.name,
        "description": skill.description,
        "avatar": skill.avatar,
        "type": skill.type,
        "is_system": skill.is_system,
        "is_active": skill.is_active,
        "sort_order": skill.sort_order,
        "timeout": skill.timeout,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }


@permission_resource(
    resource="ai_skill",
    name="menu.admin.ai_skill",
    scope=PermissionScope.ADMIN,
    menu=None,
    parent_resource="ai_skill_package",
)
class AdminSkillController(GlobalController):
    """
    平台端技能管理控制器 / Platform Skill Management Controller

    跨企业查看 + 技能 CRUD + 状态管理。
    Cross-tenant viewing + skill CRUD + status management.
    """

    prefix = "/ai/skills"
    tags = ["Skill Management (Platform)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/skill-types", summary="获取可用技能类型列表")
        @action_read("action.ai_skill.list")
        async def list_skill_types(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有可用的技能类型（内置 + 插件注册）/ Get all available skill types (built-in + plugin).
            """
            from app.enums.agent import get_skill_type_options
            return success(data=get_skill_type_options())

        @router.get("/select", summary="技能绑定选择器（分页检索）")
        @action_read("action.ai_skill.list")
        async def select_skills_for_binding(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            package_id: int | None = Query(None, description="Filter by skill package id"),
            page: int = Query(1, ge=1, description="Page number"),
            page_size: int = Query(20, ge=1, le=100, description="Page size"),
            include_system: bool = Query(True, description="Include system skills"),
            only_active: bool = Query(True, description="Only active skills"),
        ):
            """
            Paginated skills with package metadata for admin agent binding picker.
            管理端智能体技能绑定选择器专用分页接口。
            """
            service = AdminSkillService(db)
            data = await service.get_binding_select_options(
                search=search,
                package_id=package_id,
                page=page,
                page_size=page_size,
                include_system=include_system,
                only_active=only_active,
            )
            return success(data=data)

        @router.get("", summary="全企业技能列表")
        @action_read("action.ai_skill.list")
        async def list_skills(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全企业技能列表 / Get cross-tenant skill list.

            支持 JSON:API 风格筛选、排序、分页
            Supports JSON:API style filtering, sorting, pagination
            - filter[tenant_id][eq]=1  按企业筛选 / Filter by tenant
            - filter[type][eq]=http  按类型筛选 / Filter by type
            - filter[name][ilike]=xxx  按名称模糊搜索 / Fuzzy search by name
            """
            service = AdminSkillService(db)
            items, total = await service.query_list(query)

            result = [_build_admin_skill_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{skill_id}", summary="技能详情")
        @action_read("action.ai_skill.detail")
        async def get_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取技能详情（跨企业）/ Get skill details (cross-tenant).

            插件注册的技能额外返回 source_plugin 和 plugin_tools 字段
            Plugin-registered skills additionally return source_plugin and plugin_tools fields
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)

            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            data = SkillResponse.model_validate(skill, from_attributes=True)

            # 补充插件来源信息 / Enrich plugin source info
            await _enrich_plugin_skill_info(db, skill, data)

            return success(data=data)

        @router.post("", summary="创建技能")
        @action_create("action.ai_skill.create")
        async def create_skill(
            request: Request,
            db: DbSession,
            data: SkillCreate,
            admin: ActiveAdmin,
        ):
            """
            创建技能 / Create skill.

            tenant_id 自动从所属技能包继承
            tenant_id is automatically inherited from the parent skill package
            """
            from app.models.ai.skill_package import SkillPackage

            skill_data = data.model_dump(exclude_unset=True)

            # 从所属技能包继承 tenant_id / Inherit tenant_id from parent skill package
            package_id = skill_data.get("package_id")
            if package_id:
                pkg = await db.get(SkillPackage, package_id)
                if not pkg:
                    raise NotFoundException(message=_("skill_package.error.not_found"))
                skill_data["tenant_id"] = pkg.tenant_id

            service = AdminSkillService(db)
            skill = await service.create(skill_data)
            await db.commit()

            return created(
                data=SkillResponse.model_validate(skill, from_attributes=True),
                message=_("skill.created"),
            )

        @router.put("/{skill_id}", summary="更新技能")
        @action_update("action.ai_skill.update")
        async def update_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            data: SkillUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新技能 / Update skill
            """
            service = AdminSkillService(db)
            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(skill_id, update_data)
            await db.commit()

            return success(
                data=SkillResponse.model_validate(updated, from_attributes=True),
                message=_("skill.updated"),
            )

        @router.delete("/{skill_id}", summary="删除技能")
        @action_delete("action.ai_skill.delete")
        async def delete_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除技能（软删除） / Delete skill (soft delete)
            """
            service = AdminSkillService(db)
            await service.delete(skill_id)
            await db.commit()

            return deleted(message=_("skill.deleted"))

        @router.get("/{skill_id}/stats", summary="技能调用统计")
        @action_read("action.ai_skill.detail")
        async def get_skill_stats(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取单个技能的调用统计：调用次数、成功率、平均耗时、最近调用时间 / Get single skill call stats: call count, success rate, avg duration, last called time.
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.admin._skill_stats import get_skill_stats_by_id
            stats = await get_skill_stats_by_id(db, skill_id)
            return success(data=stats)

        @router.get("/stats/overview", summary="全部技能调用统计概览")
        @action_read("action.ai_skill.list")
        async def get_skills_stats_overview(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有技能的汇总统计（调用次数、成功率、平均耗时）/ Get aggregated stats for all skills (call count, success rate, avg duration).
            """
            from app.api.admin._skill_stats import get_all_skills_stats
            stats = await get_all_skills_stats(db)
            return success(data=stats)

        @router.get("/{skill_id}/tools", summary="获取技能工具定义列表")
        @action_read("action.ai_skill.detail")
        async def get_skill_tools(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取技能关联的工具定义列表 / Get tool definition list associated with the skill.

            对于插件创建的技能，通过插件实例的 resolve() 获取运行时工具定义。
            For plugin-created skills, runtime tool definitions are obtained via plugin instance's resolve().
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            tools_data: list[dict] = []

            # 尝试通过 SkillResolver 解析出工具定义 / Try resolving tool definitions via SkillResolver
            try:
                from app.ai.skills.resolver import SkillResolver
                resolver = SkillResolver(db=db)
                resolve_result = await resolver.resolve([skill])
                for td in resolve_result.tools:
                    tools_data.append({
                        "name": td.name,
                        "description": td.description,
                        "tool_type": td.tool_type,
                        "parameters": [
                            {
                                "name": p.name,
                                "type": p.type,
                                "description": p.description,
                                "required": p.required,
                            }
                            for p in (td.parameters or [])
                        ],
                        "source_skill_id": td.source_skill_id,
                        "source_plugin": td.source_plugin,
                    })
            except Exception as exc:
                logger.warning("Failed to resolve tools for skill {}: {}", skill_id, exc)

            return success(data=tools_data)

        @router.post("/{skill_id}/test", summary="测试技能配置")
        @action_read("action.ai_skill.detail")
        async def test_skill_config(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            测试技能配置是否正确（按类型执行不同的验证逻辑）/ Test if skill config is correct (executes different validation logic by type).
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.admin._skill_test import test_skill
            result = await test_skill(db, skill)
            return success(data=result)

        @router.put("/{skill_id}/status", summary="切换技能状态")
        @action_update("action.ai_skill.update_status")
        async def toggle_skill_status(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            切换技能 is_active 状态 / Toggle skill is_active status
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)

            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            updated = await service.update_status(skill_id, not skill.is_active)
            await db.commit()

            return success(
                data=_build_admin_skill_item(updated),
                message=_("skill.updated"),
            )

        @router.post("/export", summary="批量导出技能")
        @action_read("action.ai_skill.list")
        async def export_skills_endpoint(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            skill_ids: list[int] = Body(default=[], embed=True),
        ):
            """
            批量导出指定技能为 JSON，自动脱敏敏感配置。
            Batch export specified skills as JSON, auto-sanitize sensitive config.
            skill_ids 为空时导出全部。 / Exports all when skill_ids is empty.
            """
            service = AdminSkillService(db)
            if skill_ids:
                skills = await service.get_by_ids(skill_ids)
            else:
                skills = await service.get_list(limit=2000)

            if not skills:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.admin._skill_io import export_skills
            data = export_skills(skills)
            return success(data=data)

        @router.post("/import", summary="批量导入技能")
        @action_create("action.ai_skill.create")
        async def import_skills_endpoint(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            items: list[dict[str, Any]] = Body(...),
            tenant_id: int | None = Body(None),
            conflict_mode: str = Body("skip"),
            package_id: int | None = Body(None),
        ):
            """
            从 JSON 批量导入技能 / Batch import skills from JSON

            conflict_mode: skip(跳过同名) / overwrite(覆盖) / rename(自动重命名)
            conflict_mode: skip(skip same-name) / overwrite / rename(auto-rename)
            package_id: 导入到指定技能包 / Import to specified skill package
            """
            from app.api.admin._skill_io import import_skills
            result = await import_skills(
                db, items, tenant_id, conflict_mode, package_id=package_id,
            )
            await db.commit()
            return success(data=result)

        @router.post("/toolkit/parse", summary="解析 Toolkit 源码")
        @action_read("action.ai_skill.list")
        async def parse_toolkit_source(
            request: Request,
            admin: ActiveAdmin,
            body: dict[str, Any] = Body(...),
        ):
            """
            解析 Toolkit Python 源码，返回元数据（tools 列表、Valves schema 等）/ Parse Toolkit Python source code, return metadata (tools list, Valves schema, etc.).

            供前端编辑器实时预览使用。
            For frontend editor real-time preview.

            Body: { "source": "..." }
            """
            source = body.get("source", "")
            if not source or not source.strip():
                return success(data={"tools": [], "valves_schema": {}, "errors": []})

            from app.ai.skills.toolkit_parser import (
                ToolkitParseError,
                parse_toolkit,
                validate_toolkit_source,
            )

            errors = validate_toolkit_source(source)
            if errors:
                return success(data={"tools": [], "valves_schema": {}, "errors": errors})

            try:
                meta = parse_toolkit(source)
                return success(data={
                    "title": meta.title,
                    "description": meta.description,
                    "version": meta.version,
                    "author": meta.author,
                    "requirements": meta.requirements,
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters,
                            "is_async": t.is_async,
                        }
                        for t in meta.tools
                    ],
                    "valves_schema": meta.valves_schema,
                    "errors": [],
                })
            except ToolkitParseError as exc:
                return success(data={"tools": [], "valves_schema": {}, "errors": [str(exc)]})


# 导出路由器 / Export router
router = AdminSkillController.get_router()

__all__ = ["router", "AdminSkillController"]
