"""
Agent router candidate filtering support.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.models.ai.agent import Agent
from app.services.ai.agent_router_capability_support import agent_supports_families
from app.services.ai.agent_router_policy import requested_tool_families

logger = LogManager.get_logger("ai")


@dataclass
class CandidateFilterResult:
    candidates: list[Agent]
    preferred_fallback_candidates: list[Agent] | None
    direct_selected_agent: Agent | None


async def filter_router_candidates(
    *,
    message: str,
    page_context: dict[str, Any] | None,
    candidates: list[Agent],
    has_image_attachments: bool,
    agent_can_handle_images: Callable[[Agent], Awaitable[bool]],
) -> CandidateFilterResult:
    requested_families = requested_tool_families(message, page_context)
    family_coverage_filtered = False

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

    if requested_families:
        coverage_candidates = [
            agent
            for agent in candidates
            if agent_supports_families(agent, requested_families)
        ]
        if coverage_candidates:
            if len(coverage_candidates) < len(candidates):
                family_coverage_filtered = True
                logger.info(
                    "Agent router: narrowed to {} candidates covering requested families {}",
                    len(coverage_candidates),
                    requested_families,
                )
            candidates = coverage_candidates

    direct_selected_agent: Agent | None = None
    if family_coverage_filtered and len(candidates) == 1:
        direct_selected_agent = candidates[0]

    preferred_fallback_candidates = (
        candidates if family_coverage_filtered else None
    )

    return CandidateFilterResult(
        candidates=candidates,
        preferred_fallback_candidates=preferred_fallback_candidates,
        direct_selected_agent=direct_selected_agent,
    )


__all__ = ["CandidateFilterResult", "filter_router_candidates"]
