"""
Agent router runtime helpers (prompt build and router execution).
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.text_semantics import extract_fenced_json_block, extract_first_json_object_with_key
from app.ai.types import ChatMessage
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum
from app.models.ai.agent import Agent
from app.services.ai.agent_router_capability_support import grant_skill_name_if_active
from app.configs.service import PLATFORM_TENANT_ID

logger = LogManager.get_logger("ai")

ROUTER_TIMEOUT_SECONDS = 15


class AgentRouterRuntimeSupport:
    def __init__(self, db: Any):
        self.db = db

    async def call_router_agent(
        self,
        *,
        router_agent: Agent,
        candidates: list[Agent],
        message: str,
        page_context: dict[str, Any] | None,
        execution_tenant_id: int | None,
        execution_user_role: str,
        execution_user_role_id: int | None = None,
        user_id: int | None = None,
        has_image_attachments: bool = False,
        has_audio_attachments: bool = False,
        has_video_attachments: bool = False,
        has_file_attachments: bool = False,
        agent_can_handle_images_fn: Callable[[Agent], Awaitable[bool]],
        billing_context: dict[str, Any],
        timeout_seconds: int = ROUTER_TIMEOUT_SECONDS,
    ) -> dict[str, Any] | None:
        import asyncio

        from app.ai.engine.dispatcher import ExecutionDispatcher
        from app.ai.engine.types import ExecutionRequest

        agent_list = []
        for candidate in candidates:
            entry: dict[str, Any] = {
                "id": candidate.id,
                "name": candidate.name,
                "description": candidate.description or "",
            }
            entry["supports_vision"] = await agent_can_handle_images_fn(candidate)
            skill_grants = getattr(candidate, "skill_grants", None)
            if skill_grants:
                skill_names = []
                for grant in skill_grants:
                    skill_name = grant_skill_name_if_active(grant)
                    if skill_name:
                        skill_names.append(skill_name)
                if skill_names:
                    entry["capabilities"] = skill_names
            agent_list.append(entry)

        vision_preamble = ""
        if has_image_attachments:
            vision_preamble = render_prompt_contract("agent_router_vision_preamble")
        attachment_notes: list[str] = []
        if has_audio_attachments:
            attachment_notes.append("audio")
        if has_video_attachments:
            attachment_notes.append("video")
        if has_file_attachments:
            attachment_notes.append("file")

        attachment_preamble = ""
        if attachment_notes:
            attachment_preamble = render_prompt_contract(
                "agent_router_attachment_preamble",
                attachment_types=", ".join(attachment_notes),
            )

        routing_prompt = render_prompt_contract(
            "agent_router_selection",
            vision_preamble=vision_preamble.strip(),
            attachment_preamble=attachment_preamble.strip(),
            agent_list_json=json.dumps(agent_list, ensure_ascii=False),
            page_context_json=(
                json.dumps(page_context, ensure_ascii=False) if page_context else ""
            ),
            message=message,
        )

        request = ExecutionRequest(
            agent_id=router_agent.id,
            tenant_id=execution_tenant_id,
            user_id=user_id,
            messages=[ChatMessage(role="user", content=routing_prompt)],
            execution_mode=AgentExecutionModeEnum.TASK.value,
            stream=False,
            user_role=execution_user_role,
            user_role_id=execution_user_role_id,
            billing_context=billing_context,
        )

        dispatcher = ExecutionDispatcher(self.db)

        try:
            result = await asyncio.wait_for(
                dispatcher.dispatch(request),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("Router agent timed out after {}s", timeout_seconds)
            return None

        if not result.success or not result.output:
            logger.warning("Router agent returned no output: {}", result.error)
            return None

        return self.parse_router_output(result.output)

    @staticmethod
    def parse_router_output(output: str) -> dict[str, Any] | None:
        try:
            data = json.loads(output.strip())
            if isinstance(data, dict) and "agent_id" in data:
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        json_block = extract_fenced_json_block(output)
        if json_block:
            try:
                data = json.loads(json_block)
                if isinstance(data, dict) and "agent_id" in data:
                    return {
                        "agent_id": int(data["agent_id"]),
                        "confidence": float(data.get("confidence", 0.5)),
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        data = extract_first_json_object_with_key(output, "agent_id")
        if data is not None:
            try:
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        logger.warning("Failed to parse router output: {}", output[:200])
        return None

    @staticmethod
    def build_router_billing_context(
        *,
        router_agent: Agent,
        tenant_id: int | None,
        user_id: int | None,
        user_role: str,
    ) -> dict[str, Any]:
        from app.enums.ai import CallAccessChannelEnum

        billing_tenant_id = (
            tenant_id
            if tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
            else None
        )
        if user_role == "platform_admin":
            access_channel = CallAccessChannelEnum.ADMIN_INTERNAL.value
        elif user_role == "tenant_user":
            access_channel = CallAccessChannelEnum.TENANT_USER.value
        else:
            access_channel = CallAccessChannelEnum.TENANT_ADMIN.value

        _otid = getattr(router_agent, "owner_tenant_id", None)
        return {
            "billing_tenant_id": billing_tenant_id,
            "actor_user_id": user_id,
            "actor_user_type": user_role,
            "access_channel": access_channel,
            "agent_owner_type": ("platform" if _otid is None else "tenant"),
            "agent_owner_tenant_id": _otid,
            "agent_resource_scope": getattr(router_agent, "scope", None),
            "tenant_publication_id": None,
            "publication_enabled_snapshot": None,
            "publication_access_type_snapshot": None,
        }


__all__ = [
    "AgentRouterRuntimeSupport",
    "ROUTER_TIMEOUT_SECONDS",
]
