"""
公开 API 路由模块

聚合所有无需认证的公开 API 路由
"""

from fastapi import APIRouter

from app.api.public.tenant import router as tenant_router
from app.api.public.captcha import router as captcha_router
from app.api.public.platform import router as platform_router

# 创建公开 API 路由器
public_router = APIRouter()

# 注册子路由
public_router.include_router(tenant_router)
public_router.include_router(captcha_router)
public_router.include_router(platform_router)


__all__ = ["public_router"]
