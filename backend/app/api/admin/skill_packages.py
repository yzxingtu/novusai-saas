"""
平台端技能包管理 API

提供跨租户技能包列表、详情、CRUD，支持 admin + tenant scope 技能包管理
"""

import shutil
import tempfile
from pathlib import Path as FilePath
from typing import Any

from fastapi import Query, Request, UploadFile
from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
from app.enums.common import ResourceScopeEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, BusinessException, ValidationException
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
    """从 ORM 对象构建管理端列表项字典"""
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
        "valves_config": pkg.valves_config,
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

            # 不允许修改 scope
            if "scope" in update_data and update_data["scope"] != pkg.scope:
                raise BusinessException(message=_("skill_package.error.invalid_scope"))

            # 名称唯一性等校验由 Service._before_update 处理
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

            if pkg.is_system and pkg.is_active:
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
            from app.ai.skills.packaging import (
                ALLOWED_SKILL_EXTENSIONS,
                MAX_ZIP_FILE_SIZE,
                SkillPackageError,
                extract_skill_package,
                get_skill_storage_dir,
                read_env_example,
                validate_zip_safety,
            )
            from app.ai.skills.env_parser import parse_env_example

            if not file.filename:
                raise ValidationException(
                    message=_("skill_package.error.file_required"),
                    code=4001,
                )

            ext = FilePath(file.filename).suffix.lower()
            if ext not in ALLOWED_SKILL_EXTENSIONS:
                raise ValidationException(
                    message=_("skill_package.error.file_must_be_zip"),
                    code=4001,
                )

            with tempfile.TemporaryDirectory() as tmp_dir:
                zip_path = FilePath(tmp_dir) / file.filename
                content = await file.read()

                # 上传大小检查（在写磁盘前拦截）
                if len(content) > MAX_ZIP_FILE_SIZE:
                    size_mb = len(content) / (1024 * 1024)
                    limit_mb = MAX_ZIP_FILE_SIZE / (1024 * 1024)
                    raise ValidationException(
                        message=f"ZIP file too large: {size_mb:.1f}MB (limit: {limit_mb:.0f}MB)",
                        code=4001,
                    )

                zip_path.write_bytes(content)

                try:
                    extract_dir = FilePath(tmp_dir) / "extracted"
                    metadata = extract_skill_package(zip_path, extract_dir)
                except SkillPackageError as e:
                    raise ValidationException(message=str(e), code=4001)

                skill_name = metadata.get("name", "")
                skill_version = metadata.get("version", "")
                skill_desc = metadata.get("description", "")
                raw_icon = metadata.get("icon", "")
                skill_icon = raw_icon if isinstance(raw_icon, str) and ":" in raw_icon else ""

                # 环境变量需求
                env_requires: list[str] = []
                meta_block = metadata.get("metadata", {})
                if isinstance(meta_block, dict):
                    clawdbot = meta_block.get("clawdbot", {})
                    if isinstance(clawdbot, dict):
                        requires = clawdbot.get("requires", {})
                        if isinstance(requires, dict):
                            env_requires = requires.get("env", [])

                # 解析 .env.example → valves_schema
                valves_schema = None
                env_example_content = read_env_example(extract_dir)
                if env_example_content:
                    valves_schema = parse_env_example(
                        env_example_content,
                        required_vars=env_requires,
                    ) or None

                # 名称唯一性检查 + 创建 SkillPackage（通过 Service，_before_create 处理校验）
                service = AdminSkillPackageService(db)
                pkg = await service.create({
                    "name": skill_name,
                    "description": skill_desc,
                    "avatar": skill_icon,
                    "scope": ResourceScopeEnum.ADMIN.value,
                    "is_system": is_system,
                    "is_active": True,
                    "tenant_id": None,
                    "valves_schema": valves_schema,
                })
                await db.flush()

                # 从解压目录中提取 toolkit_content
                # 通用转换：自动检测 class Tools / FastAPI 路由 / 回退模板
                from app.ai.skills.server_converter import (
                    convert_server_to_toolkit,
                )

                server_dir = extract_dir / "server"
                toolkit_content = ""
                if server_dir.exists():
                    toolkit_content = convert_server_to_toolkit(
                        server_dir, metadata,
                        env_schema=valves_schema,
                    )

                # 标记来源
                await service.update(pkg.id, {"source_plugin": skill_name})

                # 创建 Skill (toolkit type)
                from app.services.ai.skill_service import AdminSkillService
                skill_svc = AdminSkillService(db)
                skill = await skill_svc.create({
                    "package_id": pkg.id,
                    "name": skill_name,
                    "description": skill_desc,
                    "avatar": skill_icon,
                    "type": "toolkit",
                    "is_system": is_system,
                    "is_active": True,
                    "toolkit_content": toolkit_content,
                    "config": {
                        "version": str(skill_version),
                        "env_requires": env_requires,
                    },
                })
                await db.flush()

                # 拷贝到永久存储目录
                storage_dir = get_skill_storage_dir(pkg.id)
                if storage_dir.exists():
                    shutil.rmtree(storage_dir)
                shutil.copytree(extract_dir, storage_dir)

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
            获取技能包的 valves 配置（schema + 当前值）
            """
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            return success(data={
                "valves_schema": pkg.valves_schema,
                "valves_config": pkg.valves_config,
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
            service = AdminSkillPackageService(db)
            pkg = await service.get_by_id(package_id)
            if not pkg:
                raise NotFoundException(message=_("skill_package.error.not_found"))

            if not pkg.valves_schema:
                raise BusinessException(
                    message=_("skill_package.error.no_valves_schema"),
                )

            valves_config = data.get("valves_config", {})
            if not isinstance(valves_config, dict):
                raise ValidationException(
                    message=_("skill_package.error.invalid_valves_config"),
                    code=4001,
                )

            # 校验 required 字段是否存在
            schema = pkg.valves_schema or {}
            required_fields = schema.get("required", [])
            if required_fields:
                missing = [
                    f for f in required_fields
                    if f not in valves_config or valves_config[f] in (None, "")
                ]
                if missing:
                    raise ValidationException(
                        message=_("skill_package.error.valves_missing_required").format(
                            fields=", ".join(missing),
                        ),
                        code=4001,
                    )

            updated = await service.update(package_id, {"valves_config": valves_config})
            await db.commit()

            return success(data={
                "valves_schema": updated.valves_schema,
                "valves_config": updated.valves_config,
            })

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


# 导出路由器
router = AdminSkillPackageController.get_router()

__all__ = ["router", "AdminSkillPackageController"]
