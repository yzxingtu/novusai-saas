"""
企业端技能包辅助 API / Tenant Skill Package Helper API

仅保留智能体场景需要的技能包查询能力。
Only keeps skill package queries required by agent scenarios.
企业端不提供独立的技能包管理入口。
Tenant side does not expose standalone skill package management.
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
from app.services.ai.skill_package_service import SkillPackageService


@permission_resource(
    resource="agent",
    name="menu.tenant.agent",
    scope=PermissionScope.TENANT,
    parent_resource="agent",
    menu=None,
)
class TenantSkillPackageController(TenantController):
    """
    企业技能包辅助控制器 / Tenant Skill Package Helper Controller

    企业端仅在智能体绑定与展示场景下读取技能包信息。
    Tenant side only reads skill package data for agent binding and display scenarios.
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Helpers (Tenant)"]

    def _register_routes(self) -> None:
        """注册智能体场景所需的辅助路由 / Register helper routes for agent scenarios."""
        router = self.router

        @router.get("/available", summary="可绑定的技能包列表")
        @action_read("action.agent.skills")
        async def available_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取企业可绑定的所有技能包（用于智能体技能绑定下拉）/ Get tenant available skill packages (for agent binding).

            包括当前企业自有包 + admin 共享包，返回 label/value 格式。
            Includes current tenant's own packages + admin shared packages, returns label/value format.
            """
            from app.repositories.ai.skill_package_repository import (
                SkillPackageRepository,
            )

            repo = SkillPackageRepository(db, tenant_admin.tenant_id)
            packages = await repo.get_available_for_binding()

            result = [
                {
                    "label": pkg.name,
                    "value": pkg.id,
                    "description": pkg.description,
                    "is_system": pkg.is_system,
                }
                for pkg in packages
            ]
            return success(data=result)

        @router.get("/{package_id}/skills", summary="获取技能包内的技能列表")
        @action_read("action.agent.skills")
        async def list_package_skills(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取指定技能包内的技能列表 / Get skill list within specified skill package
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            from app.schemas.common.query import FilterRule
            from app.services.ai.skill_service import SkillService
            skill_service = SkillService(db, tenant_admin.tenant_id)
            items, total = await skill_service.query_list(
                spec=query,
                forced_filters=[FilterRule(field="package_id", value=package_id)],
            )

            result = [item.to_dict() for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )


# 导出路由器 / Export router
router = TenantSkillPackageController.get_router()

__all__ = ["router", "TenantSkillPackageController"]
