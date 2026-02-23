"""
平台端技能包管理 API

提供跨租户技能包列表、详情、CRUD，支持 admin / tenant / global scope 技能包管理
"""

from typing import Any

from fastapi import Query, Request, UploadFile
from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
from app.enums.common import ResourceScopeEnum
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
from app.models.ai.skill_package import SkillPackage
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.services.ai.skill_package_service import AdminSkillPackageService
from app.schemas.ai.skill_package import (
    SkillPackageCreate,
    SkillPackageUpdate,
    SkillPackageResponse,
)

logger = LogManager.get_logger("ai")


def _build_admin_package_item(pkg: SkillPackage, skill_count: int = 0) -> dict[str, Any]:
    """从 ORM 对象构建管理端列表项字典（不含 valves_config 敏感值）"""
    return {
        "id": pkg.id,
        "tenant_id": pkg.tenant_id,
        "name": pkg.name,
        "description": pkg.description,
        "avatar": pkg.avatar,
        "scope": pkg.scope,
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
    scope=PermissionScope.ADMIN,
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
    平台端技能包管理控制器

    跨租户查看 + admin/tenant scope 技能包 CRUD
    """

    prefix = "/ai/skill-packages"
    tags = ["Skill Package Management (Platform)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
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
            search: str = Query("", description="搜索关键词"),
        ):
            """
            获取技能包下拉选项（用于 Skill 创建时选择所属包）
            """
            service = AdminSkillPackageService(db)
            response = await service.get_select_options(
                search=search,
                limit=50,
            )
            return success(data=response)

        @router.get("", summary="全租户技能包列表")
        @action_read("action.ai_skill_package.list")
        async def list_packages(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全租户技能包列表

            支持 JSON:API 风格筛选、排序、分页
            """
            service = AdminSkillPackageService(db)
            items, total = await service.query_list(query)

            # 批量查询每个包的技能数
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
            创建技能包

            - scope=admin: tenant_id 自动设为 NULL
            - scope=tenant: 需要指定 tenant_id
            """
            service = AdminSkillPackageService(db)

            pkg_data = data.model_dump(exclude_unset=True)

            # 校验和创建均由 Service._before_create 处理
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
            更新技能包
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)

            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)

            # scope 不可变 + 名称唯一性等校验统一由 Service._before_update 处理
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
            切换技能包 is_active 状态
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

            ZIP 包结构参见 SKILL.md 规范。
            - scope=admin, tenant_id=NULL
            - is_system=True 时不可删除
            """
            from app.api.shared._skill_package_upload import process_skill_package_upload
            from app.services.ai.skill_service import AdminSkillService

            service = AdminSkillPackageService(db)
            skill_svc = AdminSkillService(db)

            pkg, skill_name, skill_version = await process_skill_package_upload(
                db=db,
                file=file,
                package_service=service,
                skill_service=skill_svc,
                scope=ResourceScopeEnum.ADMIN.value,
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
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            from app.services.ai.skill_service import AdminSkillService
            from app.schemas.common.query import FilterRule
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

            仅对插件类型技能（source_plugin 不为空）有效。
            Toolkit 类型技能的工具由 ToolkitResolver 解析。
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            tools: list[dict] = []

            # Toolkit 类型技能：从 toolkit_content 解析
            if not tools:
                from app.services.ai.skill_service import AdminSkillService
                from app.schemas.common.query import FilterRule
                skill_svc = AdminSkillService(db)
                skill_items, _ = await skill_svc.query_list(
                    None,
                    forced_filters=[FilterRule(field="package_id", value=package_id)],
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

        # ==================== 导入 / 导出 ====================

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

            导出内容：
            - package_info: 技能包基本信息（不含 id/tenant_id/created_at 等运行时字段）
            - skills: 包内所有技能的定义
            - export_version: 导出格式版本号
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
            从导出 JSON 导入技能包

            参数：
            - data: 导出的 JSON 数据
            - conflict_mode (in data): skip / rename（同名技能包处理方式）
            - target_scope (in data): 目标作用域 (admin/tenant/global)
            - target_tenant_id (in data): 目标租户 ID（scope=tenant 时必填）
            """
            from app.api.shared._skill_package_export import import_skill_package

            result = await import_skill_package(db, data)
            await db.commit()
            return created(data=result, message=_("skill_package.import_success"))

        # ==================== 克隆 ====================

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
            克隆技能包（含所有技能）

            参数：
            - new_name: 新技能包名称（可选，默认追加 " (Copy)"）
            - target_scope: 目标作用域 (admin/tenant/global)
            - target_tenant_id: 目标租户 ID（scope=tenant 时必填）
            """
            from app.api.shared._skill_package_export import (
                export_skill_package,
                import_skill_package,
            )

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            # 导出再导入实现克隆
            export_data = await export_skill_package(db, pkg)

            new_name = data.get("new_name") or f"{pkg.name} (Copy)"
            export_data["package_info"]["name"] = new_name

            result = await import_skill_package(db, {
                "export_data": export_data,
                "conflict_mode": "rename",
                "target_scope": data.get("target_scope", pkg.scope),
                "target_tenant_id": data.get("target_tenant_id", pkg.tenant_id),
            })
            await db.commit()

            return created(data=result, message=_("skill_package.created"))

        # ==================== 调用统计 ====================

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

            返回：总调用次数、成功率、平均耗时、按技能分组统计
            """
            from app.api.shared._skill_stats import get_package_call_stats

            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            stats = await get_package_call_stats(db, package_id, days)
            return success(data=stats)


# 导出路由器
router = AdminSkillPackageController.get_router()

__all__ = ["router", "AdminSkillPackageController"]
