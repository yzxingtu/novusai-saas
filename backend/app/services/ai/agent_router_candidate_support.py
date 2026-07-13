"""
Agent router candidate filtering support.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai")


async def filter_router_candidates(
    *,
    candidates: list[Agent],
    has_image_attachments: bool,
    agent_can_handle_images: Callable[[Agent], Awaitable[bool]],
) -> list[Agent]:
    if has_image_attachments:
        vision_candidates: list[Agent] = []
        for agent in candidates:
            if await agent_can_handle_images(agent):
                vision_candidates.append(agent)
        if not vision_candidates:
            raise BusinessException(
                message=_("agent_chat.error.no_vision_agent_available"),
            )
        candidates = vision_candidates
        logger.info(
            "Agent router: narrowed to {} vision-capable agents (image attachments)",
            len(candidates),
        )

    return candidates


__all__ = ["filter_router_candidates"]
