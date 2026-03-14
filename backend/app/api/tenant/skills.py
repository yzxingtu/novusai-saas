"""
企业端技能管理 API（只读） / Tenant Skill Management API (Read-only)

提供技能的只读查询接口。
Provides read-only query endpoints for skills.
企业端不允许创建、编辑、删除技能（最小权限原则）。
Tenant is not allowed to create, edit, or delete skills (least privilege principle).
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    action_read,
    permission_resource,
)
from app.services.ai.skill_service import SkillService


@permission_resource(
    resource="skill",
    name="menu.tenant.skill",
    scope=PermissionScope.ALL_TENANTS,
    menu=None,
    parent_resource="skill_package",
)
class TenantSkillController(TenantController):
    """
    企业技能管理控制器（只读） / Tenant Skill Management Controller (Read-only)

    企业端不允许创建/编辑/删除技能，仅提供只读查询。
    Tenant is not allowed to create/edit/delete skills, only read-only queries.
    """

    prefix = "/ai/skills"
    tags = [_("tag.skill_management")]

    def _register_routes(self) -> None:
        """注册路由（仅只读端点） / Register routes (read-only endpoints only)"""
        router = self.router

        @router.get("/skill-types", summary="获取可用技能类型列表")
        @action_read("action.skill.list")
        async def list_skill_types(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取所有可用的技能类型（内置 + 插件注册）
            Get all available skill types (built-in + plugin registered)
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
            获取技能列表 / Get skill list

            支持 JSON:API 分页、筛选、排序 / Supports JSON:API pagination, filtering, sorting
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
            Get skill dropdown options (for Agent binding and similar scenarios)
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
            获取单个技能的调用统计 / Get call statistics for a single skill
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.shared._skill_stats import get_skill_stats_by_id
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
            Test if skill config is correct (execute different validation logic by type)
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.shared._skill_test import test_skill
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
            获取技能详情 / Get skill details

            插件注册的技能额外返回 source_plugin 和 plugin_tools 字段
            Plugin-registered skills additionally return source_plugin and plugin_tools fields
            """
            service = SkillService(db, tenant_admin.tenant_id)
            skill = await service.get_by_id(skill_id)
            if not skill:
                raise NotFoundException(message=_("skill.error.not_found"))

            from app.api.shared._skill_helpers import enrich_plugin_skill_info
            from app.schemas.ai.skill import SkillResponse

            data = SkillResponse.model_validate(skill, from_attributes=True)
            await enrich_plugin_skill_info(db, skill, data)

            return success(data=data)


# 导出路由器 / Export router
router = TenantSkillController.get_router()

__all__ = ["router", "TenantSkillController"]
