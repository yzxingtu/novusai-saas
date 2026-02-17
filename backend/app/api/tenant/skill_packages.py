"""
租户端技能包管理 API

提供技能包的 CRUD 接口，仅限 tenant scope 技能包
"""

from typing import Any

from fastapi import Query, Request, UploadFile

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.models.ai.skill_package import SkillPackage
from app.schemas.ai.skill_package import (
    SkillPackageCreate,
    SkillPackageUpdate,
)
from app.services.ai.skill_package_service import SkillPackageService


def _build_package_item(pkg: SkillPackage, skill_count: int = 0) -> dict[str, Any]:
    """从 ORM 对象构建列表项字典"""
    data = pkg.to_dict()
    data["skill_count"] = skill_count
    return data


@permission_resource(
    resource="skill_package",
    name="menu.tenant.skill_package",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:package",
        path="/ai/skill-packages",
        component="ai/skill-packages/index",
        parent="ai_workspace",
        sort_order=11,
    ),
)
class TenantSkillPackageController(TenantController):
    """
    租户技能包管理控制器

    提供技能包 CRUD 操作，仅限 tenant scope
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Management (Tenant)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册
        register_tenant_recycle_bin_routes(
            router=router,
            service_class=SkillPackageService,
            resource_name="skill_package",
        )

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

        @router.post("", summary="创建技能包")
        @action_create("action.skill_package.create")
        async def create_package(
            request: Request,
            db: DbSession,
            data: SkillPackageCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建技能包（仅 tenant scope）
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(data=pkg.to_dict(), message=_("skill_package.created"))

        @router.put("/{package_id}", summary="更新技能包")
        @action_update("action.skill_package.update")
        async def update_package(
            request: Request,
            db: DbSession,
            package_id: int,
            data: SkillPackageUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新技能包
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)

            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(package_id, update_data)
            await db.commit()

            return success(data=updated.to_dict(), message=_("skill_package.updated"))

        @router.delete("/{package_id}", summary="删除技能包")
        @action_delete("action.skill_package.delete")
        async def delete_package(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除技能包（软删除）
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)

            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            await service.delete(package_id)
            await db.commit()

            return deleted(message=_("skill_package.deleted"))

        @router.post("/upload", summary="上传技能 ZIP 包安装")
        @action_create("action.skill_package.upload")
        async def upload_skill_package(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            file: UploadFile = ...,
        ):
            """
            上传技能 ZIP 包并自动创建 SkillPackage + Skill (toolkit)

            ZIP 包结构参见 SKILL.md 规范。
            - scope=tenant, tenant_id=当前租户
            - 租户端不允许创建 is_system 包
            """
            from app.api.shared._skill_package_upload import process_skill_package_upload
            from app.enums.common import ResourceScopeEnum
            from app.services.ai.skill_service import SkillService

            tenant_id = tenant_admin.tenant_id
            service = SkillPackageService(db, tenant_id)
            skill_svc = SkillService(db, tenant_id)

            pkg, skill_name, skill_version = await process_skill_package_upload(
                db=db,
                file=file,
                package_service=service,
                skill_service=skill_svc,
                scope=ResourceScopeEnum.TENANT.value,
                tenant_id=tenant_id,
                is_system=False,
            )

            logger = LogManager.get_logger("ai")
            logger.info(
                "Skill package uploaded (tenant): name=%s version=%s package_id=%d tenant=%d",
                skill_name, skill_version, pkg.id, tenant_id,
            )

            return created(
                data=pkg.to_dict(),
                message=_("skill_package.created"),
            )

        @router.get("/{package_id}/valves", summary="获取技能包配置项")
        @action_read("action.skill_package.detail")
        async def get_package_valves(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取技能包的 valves 配置（schema + 当前值）
            """
            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data={
                "valves_schema": pkg.valves_schema,
                "valves_config": pkg.valves_config,
            })

        @router.put("/{package_id}/valves", summary="更新技能包配置项")
        @action_update("action.skill_package.update")
        async def update_package_valves(
            request: Request,
            db: DbSession,
            package_id: int,
            tenant_admin: ActiveTenantAdmin,
            data: dict[str, Any] = ...,
        ):
            """
            更新技能包的 valves_config（用户填写的环境变量配置值）
            """
            from app.api.shared._toolkit_helpers import validate_and_update_valves

            service = SkillPackageService(db, tenant_admin.tenant_id)
            result = await validate_and_update_valves(
                db=db, service=service, package_id=package_id, data=data,
            )
            return success(data=result)

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

            from app.services.ai.skill_service import SkillService
            from app.schemas.common.query import FilterRule
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
