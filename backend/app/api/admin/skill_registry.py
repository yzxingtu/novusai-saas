"""
Skill registry API / 技能注册表 API
"""

from fastapi import Query

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.response import created, paginated, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    action_create,
    action_read,
    permission_resource,
)
from app.services.ai.skill_registry_service import SkillRegistryService


@permission_resource(
    resource="plugin_skill_registry",
    name="menu.admin.plugin_skill_registry",
    scope=PermissionScope.ADMIN,
    parent_resource="plugin",
)
class AdminSkillRegistryController(GlobalController):
    """Skill catalog API lives under plugin marketplace (same RBAC resource)."""

    prefix = "/plugins/skill-registry"
    tags = ["Skill Registry (Platform)"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="技能注册表列表")
        @action_read("action.plugin_skill_registry.list")
        async def list_registry_packages(
            db: DbSession,
            admin: ActiveAdmin,
            search: str = Query("", description="Search keyword"),
            sort: str = Query("-downloads", description="Sort field"),
            tag: str = Query("", description="Filter by tag"),
            page_number: int = Query(1, ge=1, description="Page number"),
            page_size: int = Query(24, ge=1, le=100, description="Page size"),
        ):
            _ = admin
            result = await SkillRegistryService(db).list_packages(
                search=search,
                sort=sort,
                tag=tag,
                page_number=page_number,
                page_size=page_size,
            )
            return paginated(
                items=result["items"],
                total=result["total"],
                page=page_number,
                page_size=page_size,
            )

        @router.get("/updates", summary="获取可升级的技能注册表包")
        @action_read("action.plugin_skill_registry.detail")
        async def list_registry_updates(
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            result = await SkillRegistryService(db).list_installed_updates()
            return success(data=result)

        @router.get("/{slug}/upgrade-preview", summary="技能注册表升级预览")
        @action_read("action.plugin_skill_registry.detail")
        async def preview_upgrade(
            slug: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            result = await SkillRegistryService(db).upgrade_preview(slug)
            return success(data=result)

        @router.get("/{slug}", summary="技能注册表详情")
        @action_read("action.plugin_skill_registry.detail")
        async def get_registry_package(
            slug: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            detail = await SkillRegistryService(db).fetch_package_detail(slug)
            return success(data=detail)

        @router.post("/{slug}/install-preview", summary="技能注册表安装预览")
        @action_read("action.plugin_skill_registry.detail")
        async def preview_install(
            slug: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            detail = await SkillRegistryService(db).install_preview(slug)
            return success(data=detail)

        @router.post("/{slug}/install", summary="安装技能注册表包")
        @action_create("action.plugin_skill_registry.install")
        async def install_registry_package(
            slug: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            result = await SkillRegistryService(db).install_package(slug)
            return created(data=result)

        @router.post("/{slug}/upgrade", summary="升级已安装技能注册表包")
        @action_create("action.plugin_skill_registry.install")
        async def upgrade_registry_package(
            slug: str,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            result = await SkillRegistryService(db).upgrade_package(slug)
            return success(data=result)

        @router.post("/upgrade-batch", summary="批量升级已安装技能注册表包")
        @action_create("action.plugin_skill_registry.install")
        async def batch_upgrade_registry_packages(
            db: DbSession,
            admin: ActiveAdmin,
            slugs: list[str] | None = None,
        ):
            _ = admin
            result = await SkillRegistryService(db).batch_upgrade(slugs=slugs)
            return success(data=result)


router = AdminSkillRegistryController.get_router()


__all__ = ["AdminSkillRegistryController", "router"]
