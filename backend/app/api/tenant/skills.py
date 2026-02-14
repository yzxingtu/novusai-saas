"""
租户端技能管理 API

提供技能的 CRUD 接口，仅限 tenant scope 技能
"""

from typing import Any

from fastapi import Body, Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
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
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.schemas.ai.skill import (
    SkillCreate,
    SkillUpdate,
)
from app.services.ai.skill_service import SkillService


@permission_resource(
    resource="skill",
    name="menu.tenant.skill",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:sparkles",
        path="/ai/skills",
        component="ai/skills/index",
        parent="ai_workspace",
        sort_order=12,
        hidden=True,
    ),
)
class TenantSkillController(TenantController):
    """
    租户技能管理控制器

    提供技能 CRUD 操作，仅限 tenant scope
    """

    prefix = "/ai/skills"
    tags = [_("tag.skill_management")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
        register_tenant_recycle_bin_routes(
            router=router,
            service_class=SkillService,
            resource_name="skill",
        )

        @router.get("/skill-types", summary="获取可用技能类型列表")
        @action_read("action.skill.list")
        async def list_skill_types(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取所有可用的技能类型（内置 + 插件注册）
            """
            from app.enums.agent import get_skill_type_options
            return success(data=get_skill_type_options())

        @router.get("", summary="获取技能列表")
        @action_read("action.skill.list")
        async def list_skills(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取技能列表

            支持 JSON:API 分页、筛选、排序
            """
            service = SkillService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            result = [item.to_dict() for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/select", summary="技能下拉选项")
        @action_read("action.skill.list")
        async def select_skills(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取技能下拉选项（用于 Agent 绑定等场景）
            """
            service = SkillService(db, tenant_admin.tenant_id)
            items = await service.get_select_options(query)
            return success(data=items)

        @router.get("/{skill_id}/stats", summary="技能调用统计")
        @action_read("action.skill.detail")
        async def get_skill_stats(
            request: Request,
            db: DbSession,
            skill_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取单个技能的调用统计
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.admin._skill_stats import get_skill_stats_by_id
            stats = await get_skill_stats_by_id(db, skill_id)
            return success(data=stats)

        @router.post("/{skill_id}/test", summary="测试技能配置")
        @action_read("action.skill.detail")
        async def test_skill_config(
            request: Request,
            db: DbSession,
            skill_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            测试技能配置是否正确（按类型执行不同的验证逻辑）
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.admin._skill_test import test_skill
            result = await test_skill(db, skill)
            return success(data=result)

        @router.get("/{skill_id}", summary="获取技能详情")
        @action_read("action.skill.detail")
        async def get_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取技能详情
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            return success(data=skill.to_dict())

        @router.post("", summary="创建技能")
        @action_create("action.skill.create")
        async def create_skill(
            request: Request,
            db: DbSession,
            data: SkillCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建技能（仅 tenant scope）
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(data=skill.to_dict(), message=_("skill.created"))

        @router.put("/{skill_id}", summary="更新技能")
        @action_update("action.skill.update")
        async def update_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            data: SkillUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新技能
            """
            service = SkillService(db, tenant_admin.tenant_id)

            skill = await service.get(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(skill_id, update_data)
            await db.commit()

            return success(data=updated.to_dict(), message=_("skill.updated"))

        @router.delete("/{skill_id}", summary="删除技能")
        @action_delete("action.skill.delete")
        async def delete_skill(
            request: Request,
            db: DbSession,
            skill_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除技能（软删除）
            """
            service = SkillService(db, tenant_admin.tenant_id)

            skill = await service.get(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            await service.delete(skill_id)
            await db.commit()

            return deleted(message=_("skill.deleted"))

        @router.post("/toolkit/parse", summary="解析 Toolkit 源码")
        @action_read("action.skill.list")
        async def parse_toolkit_source(
            request: Request,
            tenant_admin: ActiveTenantAdmin,
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
router = TenantSkillController.get_router()

__all__ = ["router", "TenantSkillController"]
