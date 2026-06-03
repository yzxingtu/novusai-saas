"""
AI 对话 API 共享逻辑 / AI Chat API Shared Logic

admin/tenant 两端 agent chat controller 的公共部分提取。
Common logic extracted from admin/tenant agent chat controllers.
"""

from __future__ import annotations

from typing import Any

from app.core.response import success
from app.schemas.ai.agent_chat import AgentRouteResponse


async def handle_route(
    db: Any,
    *,
    tenant_id: int | None,
    message: str,
    conversation_id: int | None,
    user_role: str,
    user_role_id: int | None,
    pinned_agent_id: int | None,
    user_id: int | None = None,
    force_reroute: bool = False,
    has_image_attachments: bool = False,
    has_audio_attachments: bool = False,
    has_video_attachments: bool = False,
    has_file_attachments: bool = False,
) -> dict[str, Any]:
    """
    智能路由的共享逻辑 / Shared logic for smart routing

    admin/tenant/user 三端 route 端点共用。
    Shared by admin/tenant/user route endpoints.

    Args:
        user_role: 调用方角色（UserRoleEnum 值），用于候选过滤 / Caller role (UserRoleEnum value), used for candidate filtering
    """
    from app.services.ai.agent_router_service import AgentRouterService

    router_svc = AgentRouterService(db)
    result = await router_svc.route(
        tenant_id=tenant_id,
        message=message,
        conversation_id=conversation_id,
        pinned_agent_id=pinned_agent_id,
        user_role=user_role,
        user_role_id=user_role_id,
        user_id=user_id,
        force_reroute=force_reroute,
        has_image_attachments=has_image_attachments,
        has_audio_attachments=has_audio_attachments,
        has_video_attachments=has_video_attachments,
        has_file_attachments=has_file_attachments,
    )
    return success(
        data=AgentRouteResponse(
            agent_id=result.agent_id,
            agent_name=result.agent_name,
            confidence=result.confidence,
            routed_by=result.routed_by,
        ).model_dump()
    )


def enrich_conversations_with_agent(
    items: list[Any],
) -> list[dict[str, Any]]:
    """
    将对话列表 ORM 对象转为字典并补充 agent_name / agent_avatar
    Convert conversation list ORM objects to dicts and enrich with agent_name / agent_avatar

    admin/tenant 两端 list_all_conversations 共用。
    Shared by admin/tenant list_all_conversations.
    """
    result: list[dict[str, Any]] = []
    for item in items:
        d = item.to_dict()
        agent_obj = getattr(item, "agent", None)
        if agent_obj is not None:
            d["agent_name"] = agent_obj.name
            d["agent_avatar"] = agent_obj.avatar
        else:
            d["agent_name"] = None
            d["agent_avatar"] = None
        result.append(d)
    return result


__all__ = [
    "enrich_conversations_with_agent",
    "handle_route",
]
