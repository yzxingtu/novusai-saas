"""
用户端 API 路由模块 / User-facing API router module.

聚合所有用户端的 API 路由 / Aggregates all user-facing API routes.
"""

from fastapi import APIRouter

from app.api.user.agent_chat import router as agent_chat_router
from app.api.user.agents import router as agents_router
from app.api.user.attachments import router as attachments_router
from app.api.user.auth import router as auth_router
from app.api.user.permissions import router as permissions_router

# 创建用户端路由器 / Create user router
user_router = APIRouter()

# 注册子路由 / Register sub-routers
user_router.include_router(auth_router)
user_router.include_router(attachments_router)
user_router.include_router(permissions_router)
user_router.include_router(agent_chat_router)
user_router.include_router(agents_router)


__all__ = ["user_router"]
