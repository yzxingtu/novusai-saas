"""
租户端技能包管理 API

提供技能包的 CRUD 接口，仅限 tenant scope 技能包
"""

import shutil
import tempfile
from pathlib import Path as FilePath
from typing import Any

from fastapi import Query, Request, UploadFile

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, created, deleted, paginated
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

            pkg = await service.get(package_id)
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

            pkg = await service.get(package_id)
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
            from app.ai.skills.packaging import (
                ALLOWED_SKILL_EXTENSIONS,
                MAX_ZIP_FILE_SIZE,
                SkillPackageError,
                extract_skill_package,
                get_skill_storage_dir,
                read_env_example,
            )
            from app.ai.skills.env_parser import parse_env_example
            from app.enums.common import ResourceScopeEnum

            tenant_id = tenant_admin.tenant_id
            _logger = LogManager.get_logger("ai")

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

                # 创建 SkillPackage（Service._before_create 已含名称唯一性检查）
                service = SkillPackageService(db, tenant_id)
                pkg = await service.create({
                    "name": skill_name,
                    "description": skill_desc,
                    "avatar": skill_icon,
                    "scope": ResourceScopeEnum.TENANT.value,
                    "is_system": False,
                    "is_active": True,
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

                # 创建 Skill (toolkit type)
                from app.services.ai.skill_service import SkillService
                skill_service = SkillService(db, tenant_id)
                skill = await skill_service.create({
                    "package_id": pkg.id,
                    "name": skill_name,
                    "description": skill_desc,
                    "avatar": skill_icon,
                    "type": "toolkit",
                    "is_system": False,
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

            _logger.info(
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
            pkg = await service.get(package_id)
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
            service = SkillPackageService(db, tenant_admin.tenant_id)
            pkg = await service.get(package_id)
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
            pkg = await service.get(package_id)
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
