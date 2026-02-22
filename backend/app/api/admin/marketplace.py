"""
平台管理端插件市场 API

提供插件市场的浏览、搜索、一键安装、更新检查、缓存刷新等接口
"""

from __future__ import annotations

from fastapi import Path, Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, SuperAdmin
from app.core.i18n import _
from app.core.response import success, created
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
)
from app.schemas.system.marketplace import (
    MarketplaceInstallRequest,
    MarketplaceListResponse,
    MarketplaceDetailResponse,
    PluginUpdateInfo,
    RegistryRefreshResponse,
    UpdateCheckResponse,
)


def _mask_plugin_response(plugin) -> dict:
    """序列化 Plugin 并对敏感配置字段脱敏"""
    from app.plugins.security import mask_sensitive_config
    from app.schemas.system.plugin import PluginResponse

    resp = PluginResponse.model_validate(plugin, from_attributes=True).model_dump()
    if resp.get("default_config") and resp.get("config_schema"):
        resp["default_config"] = mask_sensitive_config(
            resp["default_config"], resp["config_schema"]
        )
    return resp


@permission_resource(
    resource="marketplace",
    name="menu.admin.marketplace",
    menu=MenuConfig(
        path="/admin/system/marketplace",
        icon="lucide:store",
        sort_order=35,
        parent="system",
    ),
)
class AdminMarketplaceController(GlobalController):
    """插件市场管理控制器"""

    prefix = "/admin/marketplace"
    tags = ["Admin - Plugin Marketplace"]

    def __init__(self) -> None:
        super().__init__()
        router = self.router

        # ========================================
        # GET /admin/marketplace — 市场插件列表
        # ========================================

        @router.get("", summary="获取市场插件列表")
        @action_read("action.marketplace.list")
        async def list_marketplace_plugins(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            keyword: str | None = Query(None, alias="filter[keyword]", description="关键词搜索"),
            category: str | None = Query(None, alias="filter[category]", description="分类过滤"),
            official: bool | None = Query(None, alias="filter[official]", description="官方/社区过滤"),
            install_status: str | None = Query(None, alias="filter[install_status]", description="安装状态过滤"),
            plugin_type: str | None = Query(None, alias="filter[plugin_type]", description="插件类型过滤"),
            sort: str | None = Query(None, description="排序（name/-name）"),
            mirror: str | None = Query(None, description="镜像节点（github/gitee）"),
        ) -> MarketplaceListResponse:
            from app.plugins.marketplace.registry_service import PluginRegistryService

            svc = PluginRegistryService()
            need_refresh = mirror is not None and mirror in ("github", "gitee")
            result = await svc.get_marketplace_list(
                db,
                keyword=keyword,
                category=category,
                official=official,
                install_status=install_status,
                plugin_type=plugin_type,
                sort=sort,
                force_refresh=need_refresh,
                mirror_override=mirror if need_refresh else None,
            )
            return success(data=result.model_dump())

        # ========================================
        # GET /admin/marketplace/check-updates — 更新检查
        # 注意：必须在 /{slug} 之前注册，否则 FastAPI 会把 "check-updates" 当 slug 匹配
        # ========================================

        @router.get("/check-updates", summary="检查已安装插件的可用更新")
        @action_read("action.marketplace.check_updates")
        async def check_marketplace_updates(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            from app.plugins.marketplace.registry_service import PluginRegistryService

            svc = PluginRegistryService()
            updates_raw = await svc.check_updates(db)

            updates = [
                PluginUpdateInfo(**u) for u in updates_raw
            ]

            return success(data=UpdateCheckResponse(
                updates=updates,
                total=len(updates),
            ).model_dump())

        # ========================================
        # POST /admin/marketplace/refresh — 刷新缓存
        # 注意：必须在 /{slug} 之前注册
        # ========================================

        @router.post("/refresh", summary="强制刷新市场注册中心缓存")
        @action_update("action.marketplace.refresh")
        async def refresh_marketplace_cache(
            request: Request,
            db: DbSession,
            current_admin: SuperAdmin,
        ):
            from app.plugins.marketplace.registry_service import PluginRegistryService
            from app.plugins.github_client import get_mirror

            svc = PluginRegistryService()
            registry = await svc.get_registry(force_refresh=True)

            return success(data=RegistryRefreshResponse(
                refreshed=True,
                plugin_count=len(registry.get("plugins", [])),
                mirror=get_mirror(),
                updated_at=registry.get("updated_at"),
            ).model_dump())

        # ========================================
        # GET /admin/marketplace/{slug} — 插件详情
        # ========================================

        @router.get("/{slug}", summary="获取市场插件详情")
        @action_read("action.marketplace.detail")
        async def get_marketplace_plugin_detail(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            slug: str = Path(..., description="插件 slug"),
        ):
            from app.plugins.marketplace.registry_service import PluginRegistryService
            from app.plugins.github_client import (
                async_get,
                build_raw_url,
                get_repo_for_mirror,
                build_repo_url,
            )
            from app.exceptions import NotFoundException

            svc = PluginRegistryService()
            plugin = await svc.get_plugin_by_slug(slug, db)
            if not plugin:
                raise NotFoundException(_("marketplace.plugin_not_found"))

            # 拉取 README
            readme_content: str | None = None
            registry = await svc.get_registry()
            raw_plugins = registry.get("plugins", [])
            raw_entry = next(
                (p for p in raw_plugins if p.get("slug") == slug), None,
            )

            if raw_entry:
                readme_url_path = raw_entry.get("readme_url")
                if readme_url_path:
                    repos = raw_entry.get("repo", {})
                    if isinstance(repos, str):
                        repos = {"github": repos, "gitee": repos}
                    try:
                        repo = get_repo_for_mirror(repos)
                        url = build_raw_url(repo, "main", readme_url_path)
                        content = await async_get(url, raw_response=True)
                        if isinstance(content, (str, bytes)):
                            readme_content = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
                    except Exception as exc:
                        from app.core.logging import LogManager
                        LogManager.get_logger("app").warning(
                            "Failed to fetch README for %s: %s", slug, str(exc),
                        )

            # 构建仓库 URL
            repo_url: str | None = None
            if raw_entry:
                repos = raw_entry.get("repo", {})
                if isinstance(repos, str):
                    repos = {"github": repos, "gitee": repos}
                try:
                    r = get_repo_for_mirror(repos)
                    repo_url = build_repo_url(r)
                except ValueError:
                    pass

            detail = plugin.model_dump()
            detail["readme"] = readme_content
            detail["repo_url"] = repo_url
            return success(data=detail)

        # ========================================
        # POST /admin/marketplace/{slug}/install — 一键安装
        # ========================================

        @router.post("/{slug}/install", summary="从市场一键安装插件")
        @action_create("action.marketplace.install")
        async def install_from_marketplace(
            request: Request,
            db: DbSession,
            current_admin: SuperAdmin,
            slug: str = Path(..., description="插件 slug"),
            body: MarketplaceInstallRequest | None = None,
        ):
            from app.plugins.marketplace.download_service import PluginDownloadService

            version = body.version if body else None
            svc = PluginDownloadService()
            plugin = await svc.install_from_registry(
                db,
                slug=slug,
                version=version,
                admin_id=current_admin.id,
            )
            return created(data=_mask_plugin_response(plugin))

        # ========================================
        # POST /admin/marketplace/{slug}/update — 一键更新
        # ========================================

        @router.post("/{slug}/update", summary="从市场一键更新插件")
        @action_update("action.marketplace.update")
        async def update_from_marketplace(
            request: Request,
            db: DbSession,
            current_admin: SuperAdmin,
            slug: str = Path(..., description="插件 slug"),
        ):
            from app.plugins.marketplace.download_service import PluginDownloadService

            svc = PluginDownloadService()
            plugin = await svc.update_from_registry(
                db,
                slug=slug,
                admin_id=current_admin.id,
            )
            return success(data=_mask_plugin_response(plugin))


router = AdminMarketplaceController.get_router()
