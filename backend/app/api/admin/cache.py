"""
缓存管理 API (Admin) / Cache Management API (Admin)

提供平台管理员缓存摘要和清理接口
Provides cache summary and clearing endpoints for platform administrators.
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.cache import CacheCategoryEnum
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    action_delete,
    action_read,
    permission_resource,
)
from app.schemas.system.cache import CacheClearRequest
from app.services.system.cache_management_service import CacheManagementService


@permission_resource(
    resource="cache_management",
    name="menu.admin.cache_management",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
)
class AdminCacheController(GlobalController):
    """
    缓存管理控制器 / Cache Management Controller

    提供缓存统计和清理功能 / Provides cache statistics and clearing capabilities.
    """

    prefix = "/cache"
    tags = [_("menu.tags.admin_cache")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/summary", summary="Get cache summary")
        @action_read("action.cache.summary")
        async def get_cache_summary(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有分类的缓存统计 / Get cache statistics for all categories.

            返回每个缓存分类的键数量和大小，包括 Redis 缓存、本地文件缓存和内存缓存。
            Returns key counts and size for each cache category
            including Redis caches, local file caches, and in-memory caches.

            权限 / Permission: cache_management:read
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
            清除指定缓存分类 / Clear specified cache categories.

            接受缓存分类代码列表并清除它们 / Accepts a list of cache category codes and clears them.

            权限 / Permission: cache_management:delete
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


# 导出路由器 / Export router
router = AdminCacheController.get_router()

__all__ = ["router", "AdminCacheController"]
