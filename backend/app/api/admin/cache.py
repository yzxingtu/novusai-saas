"""
Cache management API (Admin)

Provides cache summary and clearing endpoints for platform administrators.
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.cache import CacheCategoryEnum
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    action_read,
    action_delete,
)
from app.schemas.system.cache import CacheClearRequest
from app.services.system.cache_management_service import CacheManagementService


@permission_resource(
    resource="cache_management",
    name="menu.admin.cache_management",
    scope=PermissionScope.ADMIN_ONLY,
)
class AdminCacheController(GlobalController):
    """
    Cache management controller

    Provides cache statistics and clearing capabilities.
    """

    prefix = "/cache"
    tags = [_("menu.tags.admin_cache")]

    def _register_routes(self) -> None:
        """Register routes"""
        router = self.router

        @router.get("/summary", summary="Get cache summary")
        @action_read("action.cache.summary")
        async def get_cache_summary(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            Get cache statistics for all categories.

            Returns key counts and size for each cache category
            including Redis caches, local file caches, and in-memory caches.

            Permission: cache_management:read
            """
            summary = await CacheManagementService.get_cache_summary()
            return success(data=summary.model_dump(), message=_("common.success"))

        @router.post("/clear", summary="Clear cache")
        @action_delete("action.cache.clear")
        async def clear_cache(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: CacheClearRequest,
        ):
            """
            Clear specified cache categories.

            Accepts a list of cache category codes and clears them.

            Permission: cache_management:delete
            """
            categories = [
                CacheCategoryEnum.from_value(c) for c in body.categories
            ]
            valid_categories = [c for c in categories if c is not None]

            result = await CacheManagementService.clear_cache(valid_categories)
            return success(
                data=result.model_dump(),
                message=_("cache_management.clear_success"),
            )


# Export router
router = AdminCacheController.get_router()

__all__ = ["router", "AdminCacheController"]
