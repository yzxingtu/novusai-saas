"""
平台端技能包管理 API / Platform Skill Package Management API

提供技能包列表、详情、CRUD 接口（平台管理员专用）
Provides skill package listing, details, CRUD endpoints (platform admin only)
"""

from typing import Any

from fastapi import Query, Request, UploadFile

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import created, deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.skill_package import SkillPackage
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.skill_package import (
    SkillPackageCreate,
    SkillPackageResponse,
    SkillPackageUpdate,
)
from app.services.ai.skill_package_service import AdminSkillPackageService

logger = LogManager.get_logger("ai")


def _build_admin_package_item(pkg: SkillPackage, skill_count: int = 0) -> dict[str, Any]:
    """从 ORM 对象构建管理端列表项字典（不含 valves_config 敏感值） / Build admin list item dict from ORM object (excluding valves_config sensitive values)"""
    return {
        "id": pkg.id,
        "tenant_id": pkg.tenant_id,
        "name": pkg.name,
        "description": pkg.description,
        "avatar": pkg.avatar,
        "target_audience": pkg.target_audience,
        "is_system": pkg.is_system,
        "is_active": pkg.is_active,
        "sort_order": pkg.sort_order,
        "skill_count": skill_count,
        "source_plugin": pkg.source_plugin,
        "valves_schema": pkg.valves_schema,
        "created_at": pkg.created_at,
        "updated_at": pkg.updated_at,
    }


@permission_resource(
    resource="ai_skill_package",
    name="menu.admin.ai_skill_package",
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="ai_skill_mgmt",
    menu=MenuConfig(
        icon="lucide:package",
        path="/ai/skill-packages",
        component="ai/skill-packages/index",
        parent="ai_app",
        sort_order=64,
    ),
)
class AdminSkillPackageController(GlobalController):
    """
    平台端技能包管理控制器 / Platform Skill Package Management Controller

    提供技能包 CRUD 接口
    Provides skill package CRUD endpoints
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Management (Platform)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AdminSkillPackageService,
            resource_name="ai_skill_package",
            serialize=_build_admin_package_item,
        )

        @router.get("/select", summary="技能包下拉选项")
        @action_read("action.ai_skill_package.list")
        async def select_packages(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            search: str = Query("", description="搜索关键词 / Search keyword"),
            include_system: bool = Query(False, description="是否包含系统包（用于智能体绑定） / Include system packages (for agent binding)"),
        ):
            """
            获取技能包下拉选项（用于 Skill 创建时选择所属包）
            Get skill package dropdown options (for selecting parent package when creating Skill)
            """
            service = AdminSkillPackageService(db)
            response = await service.get_select_options(
                search=search,
                limit=100,
                is_system=None if include_system else False,
            )
            return success(data=response)

        @router.get("/recommended", summary="推荐技能包列表（管理端）")
        @action_read("action.ai_skill_package.list")
        async def list_recommended_packages(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有推荐技能包（is_recommended=true）
            Get all recommended skill packages (is_recommended=true)

            管理端无 target_audience 限制，返回全部推荐包。
            Admin has no target_audience restriction, returns all recommended packages.
            用于创建智能体时显示推荐绑定列表。
            Used to display recommended binding list when creating agents.
            """
            from sqlalchemy import and_, select

            from app.models.ai.skill import Skill

            stmt = select(SkillPackage).where(
                and_(
                    SkillPackage.is_recommended.is_(True),
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                )
            ).order_by(SkillPackage.sort_order)

            result = await db.execute(stmt)
            pkgs = list(result.scalars().all())

            service = AdminSkillPackageService(db)
            pkg_ids = [p.id for p in pkgs]
            skill_counts = await service.get_skill_counts_batch(pkg_ids) if pkg_ids else {}

            return success(data=[
                {**_build_admin_package_item(p, skill_counts.get(p.id, 0)),
                 "target_audience": getattr(p, "target_audience", "all"),
                 "is_recommended": True}
                for p in pkgs
            ])

        @router.get("", summary="全企业技能包列表")
        @action_read("action.ai_skill_package.list")
        async def list_packages(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全企业技能包列表
            Get cross-tenant skill package list

            支持 JSON:API 风格筛选、排序、分页
            Supports JSON:API style filtering, sorting, pagination
            """
            service = AdminSkillPackageService(db)
            items, total = await service.query_list(query)

            # 批量查询每个包的技能数 / Batch query skill count for each package
            pkg_ids = [item.id for item in items]
            skill_counts = await service.get_skill_counts_batch(pkg_ids)

            result = [
                _build_admin_package_item(item, skill_counts.get(item.id, 0))
                for item in items
            ]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{package_id}", summary="技能包详情")
        @action_read("action.ai_skill_package.detail")
        async def get_package(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取技能包详情（含技能数量）
            Get skill package details (including skill count)
            """
            service = AdminSkillPackageService(db)
            data = await service.get_with_skill_count(package_id)

            if not data:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data=data)

        @router.post("", summary="创建技能包")
        @action_create("action.ai_skill_package.create")
        async def create_package(
            request: Request,
            db: DbSession,
            data: SkillPackageCreate,
            admin: ActiveAdmin,
        ):
            """
            创建技能包 / Create skill package
            """
            service = AdminSkillPackageService(db)

            pkg_data = data.model_dump(exclude_unset=True)
            pkg = await service.create(pkg_data)

            await db.commit()

            return created(
                data=SkillPackageResponse.model_validate(pkg, from_attributes=True),
                message=_("skill_package.created"),
            )

        @router.put("/{package_id}", summary="更新技能包")
        @action_update("action.ai_skill_package.update")
        async def update_package(
            request: Request,
            db: DbSession,
            package_id: int,
            data: SkillPackageUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新技能包 / Update skill package
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)

            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(package_id, update_data)

            await db.commit()

            return success(
                data=SkillPackageResponse.model_validate(updated, from_attributes=True),
                message=_("skill_package.updated"),
            )

        @router.delete("/{package_id}", summary="删除技能包")
        @action_delete("action.ai_skill_package.delete")
        async def delete_package(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除技能包（软删除，连带包内所有技能）
            Delete skill package (soft delete, cascading to all skills in the package)
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)

            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            await service.delete(package_id)
            await db.commit()

            return deleted(message=_("skill_package.deleted"))

        @router.put("/{package_id}/status", summary="切换技能包状态")
        @action_update("action.ai_skill_package.update_status")
        async def toggle_package_status(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            切换技能包 is_active 状态 / Toggle skill package is_active status
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)

            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            if pkg.is_system:
                raise BusinessException(message=_("skill_package.error.system_protected"))

            updated = await service.update(package_id, {"is_active": not pkg.is_active})
            await db.commit()

            return success(
                data=_build_admin_package_item(updated),
                message=_("skill_package.updated"),
            )

        @router.post("/upload", summary="上传技能 ZIP 包安装")
        @action_create("action.ai_skill_package.upload")
        async def upload_skill_package(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            file: UploadFile = ...,
            is_system: bool = False,
        ):
            """
            上传技能 ZIP 包并自动创建 SkillPackage + Skill (toolkit)
            Upload skill ZIP package and auto-create SkillPackage + Skill (toolkit)

            ZIP 包结构参见 SKILL.md 规范。 / ZIP structure see SKILL.md spec.
            - scope=admin, tenant_id=NULL
            - is_system=True 时不可删除 / Cannot be deleted when is_system=True
            """
            from app.api.shared._skill_package_upload import (
                process_skill_package_upload,
            )
            from app.services.ai.skill_service import AdminSkillService

            service = AdminSkillPackageService(db)
            skill_svc = AdminSkillService(db)

            pkg, skill_name, skill_version = await process_skill_package_upload(
                db=db,
                file=file,
                package_service=service,
                skill_service=skill_svc,
                scope=ResourceScopeEnum.ADMIN_ONLY.value,
                tenant_id=None,
                is_system=is_system,
                source_plugin=True,
            )
            await db.commit()

            logger.info(
                "Skill package uploaded (admin): name=%s version=%s package_id=%d",
                skill_name, skill_version, pkg.id,
            )

            return created(
                data=SkillPackageResponse.model_validate(pkg, from_attributes=True),
                message=_("skill_package.created"),
            )

        @router.get("/{package_id}/valves", summary="获取技能包配置项")
        @action_read("action.ai_skill_package.detail")
        async def get_package_valves(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取技能包的 valves 配置（schema + 当前值，secret 字段脱敏）
            Get skill package valves config (schema + current values, secret fields masked)
            """
            from app.api.shared._toolkit_helpers import mask_secret_values

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data={
                "valves_schema": pkg.valves_schema,
                "valves_config": mask_secret_values(pkg.valves_config),
            })

        @router.put("/{package_id}/valves", summary="更新技能包配置项")
        @action_update("action.ai_skill_package.update")
        async def update_package_valves(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
            data: dict[str, Any] = ...,
        ):
            """
            更新技能包的 valves_config（用户填写的环境变量配置值）
            Update skill package valves_config (user-filled environment variable config values)
            """
            from app.api.shared._toolkit_helpers import validate_and_update_valves

            service = AdminSkillPackageService(db)
            result = await validate_and_update_valves(
                db=db, service=service, package_id=package_id, data=data,
            )
            return success(data=result)

        @router.get("/{package_id}/skills", summary="获取技能包内的技能列表")
        @action_read("action.ai_skill_package.detail")
        async def list_package_skills(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取指定技能包内的技能列表
            Get skill list within the specified skill package
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            from app.schemas.common.query import FilterRule
            from app.services.ai.skill_service import AdminSkillService
            skill_svc = AdminSkillService(db)
            items, total = await skill_svc.query_list(
                query,
                forced_filters=[FilterRule(field="package_id", value=package_id)],
            )

            result = [item.to_dict() for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{package_id}/resolved-tools", summary="获取技能包解析出的工具列表")
        @action_read("action.ai_skill_package.detail")
        async def get_resolved_tools(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取技能包内所有技能通过 resolve() 解析出的工具定义列表。
            Get tool definition list resolved from all skills in the package via resolve().

            仅对插件类型技能（source_plugin 不为空）有效。
            Only effective for plugin-type skills (source_plugin is not empty).
            Toolkit 类型技能的工具由 ToolkitResolver 解析。
            Tools for Toolkit-type skills are resolved by ToolkitResolver.
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            tools: list[dict] = []

            # Toolkit 类型技能：从 toolkit_content 解析 / Toolkit-type skills: resolve from toolkit_content
            if not tools:
                from app.schemas.common.query import FilterRule
                from app.services.ai.skill_service import AdminSkillService
                skill_svc = AdminSkillService(db)
                skill_items, skill_total = await skill_svc.query_list(
                    None,
                    forced_filters=[FilterRule(field="package_id", value=package_id)],
                )
                logger.debug(
                    "Resolved tools: loaded %d skills for package %d",
                    skill_total,
                    package_id,
                )
                for skill_item in skill_items:
                    if skill_item.type == "toolkit" and skill_item.toolkit_content:
                        try:
                            from app.ai.tools.toolkit_resolver import ToolkitResolver
                            resolver = ToolkitResolver()
                            tool_defs = resolver.resolve_from_source(
                                skill_item.toolkit_content,
                            )
                            for td in tool_defs:
                                tools.append({
                                    "name": td.name,
                                    "description": td.description,
                                    "parameters": getattr(td, "parameters", []),
                                    "source_skill_id": skill_item.id,
                                    "source_skill_name": skill_item.name,
                                })
                        except Exception:
                            pass

            return success(data={
                "package_id": package_id,
                "package_name": pkg.name,
                "source_plugin": pkg.source_plugin,
                "tool_count": len(tools),
                "tools": tools,
            })

        # ==================== 导入 / 导出 / Import / Export ====================

        @router.get("/{package_id}/export", summary="导出技能包")
        @action_read("action.ai_skill_package.detail")
        async def export_package(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
        ):
            """
            导出技能包为 JSON（含所有技能定义、valves_schema）
            Export skill package as JSON (including all skill definitions, valves_schema)

            导出内容： / Export content:
            - package_info: 技能包基本信息（不含 id/tenant_id/created_at 等运行时字段） / Basic info (excluding runtime fields like id/tenant_id/created_at)
            - skills: 包内所有技能的定义 / All skill definitions in the package
            - export_version: 导出格式版本号 / Export format version number
            """
            from app.api.shared._skill_package_export import export_skill_package

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            export_data = await export_skill_package(db, pkg)
            return success(data=export_data)

        @router.post("/import", summary="导入技能包")
        @action_create("action.ai_skill_package.create")
        async def import_package(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            data: dict[str, Any] = ...,
        ):
            """
            从导出 JSON 导入技能包 / Import skill package from exported JSON

            参数： / Parameters:
            - data: 导出的 JSON 数据 / Exported JSON data
            - conflict_mode (in data): skip / rename（同名技能包处理方式） / Conflict resolution for same-name packages
            - target_scope (in data): 目标作用域 (admin/tenant/global) / Target scope
            - target_tenant_id (in data): 目标企业 ID（scope=tenant 时必填） / Target tenant ID (required when scope=tenant)
            """
            from app.api.shared._skill_package_export import import_skill_package

            result = await import_skill_package(db, data)
            await db.commit()
            return created(data=result, message=_("skill_package.import_success"))

        # ==================== 克隆 / Clone ====================

        @router.post("/{package_id}/clone", summary="克隆技能包")
        @action_create("action.ai_skill_package.create")
        async def clone_package(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
            data: dict[str, Any] = ...,
        ):
            """
            克隆技能包（含所有技能） / Clone skill package (including all skills)

            参数： / Parameters:
            - new_name: 新技能包名称（可选，默认追加 " (Copy)"） / New name (optional, defaults to append " (Copy)")
            - target_scope: 目标作用域 (admin/tenant/global) / Target scope
            - target_tenant_id: 目标企业 ID（scope=tenant 时必填） / Target tenant ID (required when scope=tenant)
            """
            from app.api.shared._skill_package_export import (
                export_skill_package,
                import_skill_package,
            )

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            # 导出再导入实现克隆 / Clone via export-then-import
            export_data = await export_skill_package(db, pkg)

            new_name = data.get("new_name") or f"{pkg.name} (Copy)"
            export_data["package_info"]["name"] = new_name

            result = await import_skill_package(db, {
                "export_data": export_data,
                "conflict_mode": "rename",
                "target_tenant_id": data.get("target_tenant_id", pkg.tenant_id),
            })
            await db.commit()

            return created(data=result, message=_("skill_package.created"))

        # ==================== 调用统计 / Call Statistics ====================

        @router.get("/{package_id}/stats", summary="技能包调用统计")
        @action_read("action.ai_skill_package.detail")
        async def get_package_stats(
            request: Request,
            db: DbSession,
            package_id: int,
            admin: ActiveAdmin,
            days: int = Query(7, ge=1, le=90, description="统计天数"),
        ):
            """
            获取技能包内所有技能的调用统计
            Get call statistics for all skills in the package

            返回：总调用次数、成功率、平均耗时、按技能分组统计
            Returns: total calls, success rate, avg duration, per-skill grouped stats
            """
            from app.api.shared._skill_stats import get_package_call_stats

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            stats = await get_package_call_stats(db, package_id, days)
            return success(data=stats)


# 导出路由器 / Export router
router = AdminSkillPackageController.get_router()

__all__ = ["router", "AdminSkillPackageController"]
