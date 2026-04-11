"""
Plugin install preview routes (admin).

Thin adapter over PluginInstallPreviewService to keep helper exports/routes compatible.
"""

from __future__ import annotations

from fastapi import File, Form, Query, Response, UploadFile

from app.api.admin.plugin_admin_contracts import PluginInstallConfirmBody
from app.configs.definitions.platform.marketplace import (
    MARKETPLACE_GITHUB_URL,
    SKILL_REGISTRY_GITHUB_URL,
)
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.response import created, paginated, success
from app.rbac.decorators import action_create, action_read
from app.services.system.plugin_install_preview_service import (
    PluginInstallPreviewService,
    assert_install_preview_token,
    assert_marketplace_package_identity,
    create_install_preview_token,
    decode_install_preview_token,
    extract_plugin_from_zip,
    sanitize_marketplace_slug,
    test_registry_connection,
)


def _get_preview_service(db: DbSession) -> PluginInstallPreviewService:
    return PluginInstallPreviewService(db)


def register_plugin_install_preview_routes(controller: GlobalController) -> None:
    """Register admin plugin install preview routes."""

    @controller.router.get("/marketplace")
    @action_read("action.plugin.list")
    async def marketplace_list(
        db: DbSession,
        admin: ActiveAdmin,
        response: Response,
        search: str = Query("", description="Search keyword"),
        category: str = Query("", description="Category"),
        sort: str = Query("-downloads", description="Sort field"),
        page_number: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Page size"),
    ):
        _ = admin
        result = await _get_preview_service(db).marketplace_list(
            search=search,
            category=category,
            sort=sort,
            page_number=page_number,
            page_size=page_size,
        )
        response.headers["Cache-Control"] = "private, max-age=60"
        return paginated(
            items=result.get("items", []),
            total=int(result.get("total", 0) or 0),
            page=int(result.get("page", page_number) or page_number),
            page_size=int(result.get("page_size", page_size) or page_size),
        )

    @controller.router.get("/marketplace/{slug}")
    @action_read("action.plugin.list")
    async def marketplace_detail(
        slug: str,
        db: DbSession,
        admin: ActiveAdmin,
        response: Response,
    ):
        _ = admin
        detail = await _get_preview_service(db).marketplace_detail(slug=slug)
        response.headers["Cache-Control"] = "private, max-age=120"
        return success(data=detail)

    @controller.router.post("/marketplace/{slug}/install")
    @action_create("action.plugin.install")
    async def marketplace_preview_install(
        slug: str,
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        result = await _get_preview_service(db).marketplace_preview_install(
            slug=slug,
            admin_id=getattr(admin, "id", None),
        )
        return success(data=result)

    @controller.router.post("/marketplace/{slug}/confirm-install")
    @action_create("action.plugin.install")
    async def marketplace_confirm_install(
        slug: str,
        body: PluginInstallConfirmBody,
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        result = await _get_preview_service(db).marketplace_confirm_install(
            slug=slug,
            body=body,
            admin_id=getattr(admin, "id", None),
        )
        return created(data=result)

    @controller.router.post("/marketplace/test-connection")
    @action_read("action.plugin.list")
    async def marketplace_test_connection(
        db: DbSession,
        admin: ActiveAdmin,
        source_url: str = Query("", max_length=2048),
    ):
        _ = db, admin
        result = await test_registry_connection(
            source_url=source_url,
            default_url=str(MARKETPLACE_GITHUB_URL.default_value),
            log_label="Marketplace registry",
        )
        return success(data=result)

    @controller.router.post("/skill-registry/test-connection")
    @action_read("action.plugin.list")
    async def skill_registry_test_connection(
        db: DbSession,
        admin: ActiveAdmin,
        source_url: str = Query("", max_length=2048),
    ):
        _ = db, admin
        result = await test_registry_connection(
            source_url=source_url,
            default_url=str(SKILL_REGISTRY_GITHUB_URL.default_value),
            log_label="Skill registry",
        )
        return success(data=result)

    @controller.router.post("/preview")
    @action_create("action.plugin.preview")
    async def preview_install(
        file: UploadFile = File(...),
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        content = await file.read()
        result = await _get_preview_service(db).preview_upload_install(
            content=content,
            filename=file.filename or "",
            admin_id=getattr(admin, "id", None),
        )
        return success(data=result)

    @controller.router.post("/upload")
    @action_create("action.plugin.install")
    async def install_plugin(
        file: UploadFile = File(...),
        preview_token: str = Form("", max_length=4096),
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        content = await file.read()
        result = await _get_preview_service(db).install_upload_plugin(
            content=content,
            filename=file.filename or "",
            preview_token=preview_token,
            admin_id=getattr(admin, "id", None),
        )
        return created(data=result)


__all__ = [
    "PluginInstallPreviewService",
    "assert_install_preview_token",
    "assert_marketplace_package_identity",
    "create_install_preview_token",
    "decode_install_preview_token",
    "extract_plugin_from_zip",
    "sanitize_marketplace_slug",
    "test_registry_connection",
    "register_plugin_install_preview_routes",
]
