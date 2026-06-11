"""
AI Proxy Token / AI 代理 Token

Issues a short-lived access token on behalf of the current conversation user
so the copilot agent can call internal APIs with exactly the user's identity
and permissions. Claims mark the actor as an AI agent for audit purposes.
为当前对话用户签发短时效访问 token，使 Copilot 智能体以该用户的身份与权限
调用内部 API。Claims 中标记操作者为 AI 智能体以供审计区分。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.config import settings
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    create_access_token,
)
from app.enums.common import UserRoleEnum

# Claim value marking AI-proxied requests / 标记 AI 代理请求的 claim 值
AI_PROXY_ACTOR = "ai_agent"

_USER_ROLE_TO_TOKEN_SCOPE: dict[str, str] = {
    UserRoleEnum.PLATFORM_ADMIN.value: TOKEN_SCOPE_ADMIN,
    UserRoleEnum.TENANT_ADMIN.value: TOKEN_SCOPE_TENANT_ADMIN,
    UserRoleEnum.TENANT_USER.value: TOKEN_SCOPE_TENANT_USER,
}


def issue_ai_proxy_token(
    *,
    user_id: int,
    user_role: str,
    tenant_id: int | None,
    agent_id: int | None,
    conversation_id: int | None,
) -> str:
    """
    Issue a short-lived AI proxy access token / 签发短时效 AI 代理访问 token

    The token reuses the standard access-token format so PermissionMiddleware
    loads the user's live permission set from DB — the agent can never hold
    more privileges than the user it acts for.
    复用标准访问 token 格式，PermissionMiddleware 会从数据库加载该用户的实时
    权限集 —— 智能体的权限永远不会超过被代理用户。

    Raises:
        ValueError: user_role 无法映射到 token scope / unmappable user_role
    """
    scope = _USER_ROLE_TO_TOKEN_SCOPE.get(str(user_role or "").strip())
    if not scope:
        raise ValueError(f"Cannot issue AI proxy token for user_role={user_role!r}")

    extra_claims: dict[str, Any] = {
        "actor": AI_PROXY_ACTOR,
        "ai_proxy": {
            "on_behalf_of": int(user_id),
            "user_role": str(user_role),
            "agent_id": int(agent_id) if agent_id else None,
            "conversation_id": int(conversation_id) if conversation_id else None,
        },
    }
    if scope in (TOKEN_SCOPE_TENANT_ADMIN, TOKEN_SCOPE_TENANT_USER):
        extra_claims["tenant_id"] = tenant_id

    token, _jti = create_access_token(
        subject=int(user_id),
        scope=scope,
        expires_delta=timedelta(
            seconds=settings.AI_PROXY_TOKEN_EXPIRE_SECONDS,
        ),
        extra_claims=extra_claims,
    )
    return token


__all__ = ["AI_PROXY_ACTOR", "issue_ai_proxy_token"]
