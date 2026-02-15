"""
平台端技能管理 API

提供跨租户技能列表、详情、CRUD，支持 admin + tenant scope 技能管理
"""

from typing import Any

from fastapi import Body, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
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
from app.models.ai.skill import Skill
from app.schemas.ai.skill import (
    SkillCreate,
    SkillUpdate,
    SkillResponse,
)
from app.services.ai.skill_service import AdminSkillService

logger = LogManager.get_logger("ai")


def _build_admin_skill_item(skill) -> dict:
    """从 ORM 对象构建管理端列表项字典"""
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
)
class AdminSkillController(GlobalController):
    """
    平台端技能管理控制器

    跨租户查看 + admin/tenant scope 技能 CRUD + 状态管理
    """

    prefix = "/ai/skills"
    tags = ["Skill Management (Platform)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("/skill-types", summary="获取可用技能类型列表")
        @action_read("action.ai_skill.list")
        async def list_skill_types(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有可用的技能类型（内置 + 插件注册）
            """
            from app.enums.agent import get_skill_type_options
            return success(data=get_skill_type_options())

        @router.get("", summary="全租户技能列表")
        @action_read("action.ai_skill.list")
        async def list_skills(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全租户技能列表

            支持 JSON:API 风格筛选、排序、分页
            - filter[tenant_id][eq]=1  按租户筛选
            - filter[scope][eq]=admin  筛选管理技能
            - filter[type][eq]=http  按类型筛选
            - filter[name][ilike]=xxx  按名称模糊搜索
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
            获取技能详情（跨租户）
            """
            service = AdminSkillService(db)
            skill = await service.get_by_id(skill_id)

            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            return success(
                data=SkillResponse.model_validate(skill, from_attributes=True),
            )

        @router.post("", summary="创建技能")
        @action_create("action.ai_skill.create")
        async def create_skill(
            request: Request,
            db: DbSession,
            data: SkillCreate,
            admin: ActiveAdmin,
        ):
            """
            创建技能

            tenant_id 自动从所属技能包继承
            """
            from app.models.ai.skill_package import SkillPackage

            skill_data = data.model_dump(exclude_unset=True)

            # 从所属技能包继承 tenant_id
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
            更新技能
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
            删除技能（软删除）
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
            获取单个技能的调用统计：调用次数、成功率、平均耗时、最近调用时间
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
            获取所有技能的汇总统计（调用次数、成功率、平均耗时）
            """
            from app.api.admin._skill_stats import get_all_skills_stats
            stats = await get_all_skills_stats(db)
            return success(data=stats)

        @router.post("/{skill_id}/test", summary="测试技能配置")
        @action_read("action.ai_skill.detail")
        async def test_skill_config(
            request: Request,
            db: DbSession,
            skill_id: int,
            admin: ActiveAdmin,
        ):
            """
            测试技能配置是否正确（按类型执行不同的验证逻辑）
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
            切换技能 is_active 状态
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
            skill_ids 为空时导出全部。
            """
            service = AdminSkillService(db)
            if skill_ids:
                skills = await service.get_by_ids(skill_ids)
            else:
                skills = await service.get_list(limit=10000)

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
            从 JSON 批量导入技能

            conflict_mode: skip(跳过同名) / overwrite(覆盖) / rename(自动重命名)
            package_id: 导入到指定技能包
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
            解析 Toolkit Python 源码，返回元数据（tools 列表、Valves schema 等）。
            供前端编辑器实时预览使用。

            Body: { "source": "..." }
            """
            source = body.get("source", "")
            if not source or not source.strip():
                return success(data={"tools": [], "valves_schema": {}, "errors": []})

            from app.ai.skills.toolkit_parser import (
                validate_toolkit_source,
                parse_toolkit,
                ToolkitParseError,
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


# 导出路由器
router = AdminSkillController.get_router()

__all__ = ["router", "AdminSkillController"]
