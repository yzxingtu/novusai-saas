"""
租户端技能包管理 API（只读）

提供技能包的只读查询接口。
租户端不允许创建、编辑、删除技能包（最小权限原则）。
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
    """从 ORM 对象构建列表项字典（不含 valves_config 敏感值）"""
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
    租户技能包管理控制器（只读）

    租户端不允许创建/编辑/删除技能包，仅提供只读查询。
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Management (Tenant)"]

    def _register_routes(self) -> None:
        """注册路由（仅只读端点）"""
        router = self.router

        @router.get("/select", summary="技能包下拉选项")
        @action_read("action.skill_package.list")
        async def select_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            search: str = Query("", description="搜索关键词"),
        ):
            """
            获取技能包下拉选项（用于 Skill 创建时选择所属包）
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            response = await service.get_select_options(
                search=search,
                limit=50,
            )
            return success(data=response)

        @router.get("/recommended", summary="推荐技能包列表（租户端）")
        @action_read("action.skill_package.list")
        async def list_recommended_packages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取推荐技能包（is_recommended=true）

            租户端自动过滤掉 target_audience=admin_only 的包。
            用于创建智能体时显示推荐绑定列表。
            """
            from sqlalchemy import and_, or_, select

            from app.enums.common import AudienceEnum, ResourceScopeEnum
            from app.models.ai.skill_package import SkillPackage

            stmt = select(SkillPackage).where(
                and_(
                    SkillPackage.is_recommended.is_(True),
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    # 租户端不显示 admin_only 的推荐包
                    SkillPackage.target_audience.in_([
                        AudienceEnum.ALL.value,
                        AudienceEnum.ADMIN_TENANT.value,
                    ]),
                    # scope 可见性：租户端可见的 scope
                    SkillPackage.scope.in_([
                        ResourceScopeEnum.ALL_TENANTS.value,
                        ResourceScopeEnum.ADMIN_AND_ALL.value,
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
                    "scope": p.scope,
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
            获取租户可绑定的所有技能包（用于智能体技能绑定下拉）。

            包括当前租户自有包 + admin 共享包，返回 label/value 格式。
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
                    "scope": pkg.scope,
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
            获取技能包列表

            支持 JSON:API 分页、筛选、排序
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)

            # 批量查询每个包的技能数
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
            获取技能包详情（含技能数量）
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
            获取技能包的 valves 配置（schema + 当前值，secret 字段脱敏）
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
            获取指定技能包内的技能列表
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


# 导出路由器
router = TenantSkillPackageController.get_router()

__all__ = ["router", "TenantSkillPackageController"]
