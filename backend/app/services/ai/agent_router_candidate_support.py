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
from app.services.ai.agent_router_capability_support import (
    agent_supports_families,
    agent_supports_page_operations,
)
from app.services.ai.agent_router_policy import (
    has_non_page_mixed_intent,
    requested_tool_families,
    requires_page_operation_routing,
    requires_vision_page_operation,
)

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
    page_operation_routing_required = requires_page_operation_routing(
        message,
        page_context,
    )
    mixed_non_page_intent = has_non_page_mixed_intent(message, page_context)
    requested_families = requested_tool_families(message, page_context)
    page_operation_filtered = False
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

    if page_operation_routing_required and not mixed_non_page_intent:
        page_operation_candidates = [
            agent
            for agent in candidates
            if agent_supports_page_operations(agent)
        ]
        if page_operation_candidates and requires_vision_page_operation(message):
            vision_page_candidates: list[Agent] = []
            for agent in page_operation_candidates:
                if await agent_can_handle_images(agent):
                    vision_page_candidates.append(agent)
            if not vision_page_candidates:
                raise BusinessException(
                    message=_("agent_chat.error.no_vision_agent_available"),
                )
            page_operation_candidates = vision_page_candidates
        if page_operation_candidates:
            candidates = page_operation_candidates
            page_operation_filtered = True
            logger.info(
                "Agent router: narrowed to {} page-operation-capable agents",
                len(candidates),
            )
        else:
            logger.warning(
                "Agent router: page operation intent detected but no page-operation-capable agent was found; using general candidate pool",
            )
    elif page_operation_routing_required and mixed_non_page_intent:
        logger.info(
            "Agent router: keeping full candidate pool for mixed page/non-page intent",
        )

    if any(family != "page_ops" for family in requested_families):
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
    if (page_operation_filtered or family_coverage_filtered) and len(candidates) == 1:
        direct_selected_agent = candidates[0]

    preferred_fallback_candidates = (
        candidates if (page_operation_filtered or family_coverage_filtered) else None
    )

    return CandidateFilterResult(
        candidates=candidates,
        preferred_fallback_candidates=preferred_fallback_candidates,
        direct_selected_agent=direct_selected_agent,
    )


__all__ = ["CandidateFilterResult", "filter_router_candidates"]
