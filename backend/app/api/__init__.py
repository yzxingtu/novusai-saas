"""
API 路由模块

路由结构:
- /admin/*: 平台管理后台 API
- /tenant/*: 企业管理后台 API
- /api/user/*: 企业业务用户 API
"""

from app.api.admin import admin_router
from app.api.tenant import tenant_router

__all__ = [
    "admin_router",
    "tenant_router",
]
