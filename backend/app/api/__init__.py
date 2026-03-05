"""
API 路由模块

路由结构:
- /admin/*: 平台管理后台 API
- /tenant/*: 租户管理后台 API
- /api/v1/*: 租户业务用户 API
"""

from app.api.admin import admin_router
from app.api.tenant import tenant_router
from app.api.v1 import api_router as api_v1_router

__all__ = [
    "api_v1_router",
    "admin_router",
    "tenant_router",
]
