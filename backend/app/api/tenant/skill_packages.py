"""
企业端技能包管理 API（只读） / Tenant Skill Package Management API (Read-only)

提供技能包的只读查询接口。
Provides read-only query endpoints for skill packages.
企业端不允许创建、编辑、删除技能包（最小权限原则）。
Tenant is not allowed to create, edit, or delete skill packages (least privilege principle).
"""

from typing import Any

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.models.ai.skill_package import SkillPackage
from app.rbac.decorators import (
    action_read,
    permission_resource,
)
from app.services.ai.skill_package_service import SkillPackageService


def _build_package_item(pkg: SkillPackage, skill_count: int = 0) -> dict[str, Any]:
    """从 ORM 对象构建列表项字典（不含 valves_config 敏感值） / Build list item dict from ORM object (without valves_config sensitive values)"""
    data = pkg.to_dict(exclude={"valves_config"})
    data["skill_count"] = skill_count
    return data


@permission_resource(
    resource="skill_package",
    name="menu.tenant.skill_package",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_workspace",
    menu=None,
)
class TenantSkillPackageController(TenantController):
    """
    企业技能包管理控制器（只读） / Tenant Skill Package Management Controller (Read-only)

    企业端不允许创建/编辑/删除技能包，仅提供只读查询。
    Tenant is not allowed to create/edit/delete skill packages, only read-only queries.
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Management (Tenant)"]

    def _register_routes(self) -> None:
        """注册路由（仅只读端点） / Register routes (read-only endpoints only)"""
        router = self.router

        @router.get("/select", summary="技能包下拉选项")
        @action_read("action.skill_package.list")
        async def select_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            search: str = Query("", description=_("api.param.search")),
        ):
            """
            获取技能包下拉选项（用于 Skill 创建时选择所属包）/ Get skill package select options (for Skill create).
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            response = await service.get_select_options(
                search=search,
                limit=50,
            )
            return success(data=response)

        @router.get("/recommended", summary="推荐技能包列表（企业端）")
        @action_read("action.skill_package.list")
        async def list_recommended_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取推荐技能包（is_recommended=true） / Get recommended skill packages (is_recommended=true)

            企业端自动过滤掉 target_audience=admin_only 的包。
            Tenant automatically filters out packages with target_audience=admin_only.
            用于创建智能体时显示推荐绑定列表。
            Used for displaying recommended binding list when creating agents.
            """
            from sqlalchemy import and_, select

            from app.enums.common import AudienceEnum
            from app.models.ai.skill_package import SkillPackage

            stmt = select(SkillPackage).where(
                and_(
                    SkillPackage.is_recommended.is_(True),
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    SkillPackage.target_audience.in_([
                        AudienceEnum.ALL.value,
                        AudienceEnum.ADMIN_TENANT.value,
                    ]),
                )
            ).order_by(SkillPackage.sort_order)

            result = await db.execute(stmt)
            pkgs = list(result.scalars().all())

            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg_ids = [p.id for p in pkgs]
            skill_counts = await service.get_skill_counts_batch(pkg_ids) if pkg_ids else {}

            return success(data=[
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "avatar": p.avatar,
                    "target_audience": getattr(p, "target_audience", "all"),
                    "is_recommended": True,
                    "is_system": p.is_system,
                    "skill_count": skill_counts.get(p.id, 0),
                    "source_plugin": p.source_plugin,
                }
                for p in pkgs
            ])

        @router.get("/available", summary="可绑定的技能包列表")
        @action_read("action.skill_package.list")
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

        @router.get("", summary="获取技能包列表")
        @action_read("action.skill_package.list")
        async def list_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取技能包列表 / Get skill package list

            支持 JSON:API 分页、筛选、排序 / Supports JSON:API pagination, filtering, sorting
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)

            # 批量查询每个包的技能数 / Batch query skill count for each package
            pkg_ids = [item.id for item in items]
            skill_counts = await service.get_skill_counts_batch(pkg_ids)

            result = [
                _build_package_item(item, skill_counts.get(item.id, 0))
                for item in items
            ]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{package_id}", summary="获取技能包详情")
        @action_read("action.skill_package.detail")
        async def get_package(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取技能包详情（含技能数量） / Get skill package details (with skill count)
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            data = await service.get_with_skill_count(package_id)
            if not data:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data=data)

        @router.get("/{package_id}/valves", summary="获取技能包配置项")
        @action_read("action.skill_package.detail")
        async def get_package_valves(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取技能包的 valves 配置（schema + 当前值，secret 字段脱敏）/ Get skill package valves config (schema + current values, secret fields masked).
            """
            from app.api.shared._toolkit_helpers import mask_secret_values

            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data={
                "valves_schema": pkg.valves_schema,
                "valves_config": mask_secret_values(pkg.valves_config),
            })

        @router.get("/{package_id}/skills", summary="获取技能包内的技能列表")
        @action_read("action.skill_package.detail")
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
