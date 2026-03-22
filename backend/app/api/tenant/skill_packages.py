"""
Tenant skill package catalog API / 企业端技能包目录 API

Tenant side exposes a read-only catalog entry for browsing package metadata,
skills, and resolved tools. Runtime authorization remains direct skill grants.
企业端提供只读的技能包目录入口，用于浏览包信息、技能列表与解析后的工具；
运行时授权真相仍然是直接技能授予，不在此处重新引入包级运行绑定语义。
"""

from fastapi import Request

from app.api.shared._skill_package_summary import build_skill_package_payload
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.schemas.common.query import FilterRule
from app.services.ai.skill_package_service import SkillPackageService


@permission_resource(
    resource="skill_package",
    name="menu.tenant.skill_package",
    scope=PermissionScope.TENANT,
    parent_resource="ai_workspace",
    menu=MenuConfig(
        icon="lucide:package-search",
        path="/ai/skill-packages",
        component="ai/skill-packages/index",
        parent="ai_workspace",
        sort_order=11,
    ),
)
class TenantSkillPackageController(TenantController):
    """
    Tenant read-only skill package catalog controller.
    企业端只读技能包目录控制器。
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Catalog (Tenant)"]

    def _register_routes(self) -> None:
        """Register tenant read-only catalog routes. / 注册企业端只读目录路由。"""
        router = self.router

        @router.get("", summary="获取技能包目录列表")
        @action_read("action.skill_package.list")
        async def list_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """Get tenant-visible package catalog. / 获取企业可见的技能包目录。"""
            service = SkillPackageService(db, tenant_admin.tenant_id)
            items, total = await service.get_catalog_list(query)

            package_ids = [item.id for item in items]
            skill_counts = await service.get_skill_counts_batch(package_ids)
            result = [
                build_skill_package_payload(
                    item,
                    skill_count=skill_counts.get(item.id, 0),
                )
                for item in items
            ]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{package_id}", summary="获取技能包目录详情")
        @action_read("action.skill_package.detail")
        async def get_package(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """Get tenant-visible package detail. / 获取企业可见技能包详情。"""
            service = SkillPackageService(db, tenant_admin.tenant_id)
            data = await service.get_catalog_detail(package_id)

            if not data:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data=build_skill_package_payload(data))

        @router.get("/{package_id}/skills", summary="获取技能包内的技能列表")
        @action_read("action.skill_package.detail")
        async def list_package_skills(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """Get skills under a tenant-visible package. / 获取企业可见技能包下的技能列表。"""
            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

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

        @router.get("/{package_id}/resolved-tools", summary="获取技能包解析后的工具列表")
        @action_read("action.skill_package.detail")
        async def get_resolved_tools(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """Get resolved tools for a tenant-visible package. / 获取企业可见技能包的解析工具列表。"""
            service = SkillPackageService(db, tenant_admin.tenant_id)
            data = await service.get_resolved_tools(package_id)
            return success(data=data)


router = TenantSkillPackageController.get_router()

__all__ = ["router", "TenantSkillPackageController"]
