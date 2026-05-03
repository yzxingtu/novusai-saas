"""Read-model helpers for conversation detail/list/message surfaces."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.json_safe import normalize_json_safe_dict
from app.ai.text_semantics import extract_public_attachment_reference
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_chat_message_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.enums.agent import MessageRoleEnum
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.conversation_message import ConversationMessage
from app.models.tenant.attachment import Attachment
from app.services.ai.agent_chat_interaction_support import (
    normalize_requested_interaction_mode,
    strip_legacy_interaction_mode_fields,
)
from app.services.ai.conversation_payload_sanitizer import (
    sanitize_assistant_error_payload,
    sanitize_conversation_last_error_payload,
    strip_assistant_legacy_turn_projection_fields,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.recovery_evidence_read_model import (
    patch_recovery_evidence_answer_payload,
)
from app.services.tenant.attachment_download_service import AttachmentDownloadService

if TYPE_CHECKING:
    from app.repositories.tenant.tenant_admin_repository import (
        TenantAdminRepository,
    )


class ConversationReadModelService:
    """Builds stable conversation read models outside the main service facade."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        tenant_admin_repo: TenantAdminRepository,
    ) -> None:
        self.db = db
        self.tenant_admin_repo = tenant_admin_repo

    @staticmethod
    def format_dt(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @staticmethod
    def _safe_attr(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        if hasattr(obj, "__dict__") and key in vars(obj):
            return vars(obj).get(key, default)
        value = getattr(obj, key, default)
        return default if isinstance(value, Mock) else value

    @staticmethod
    def extract_attachment_id(raw_url: Any) -> int | None:
        attachment_id, _ = extract_public_attachment_reference(raw_url)
        return attachment_id

    async def hydrate_chat_attachments(
        self,
        attachments: Any,
    ) -> Any:
        if not isinstance(attachments, list) or not attachments:
            return attachments

        normalized: list[Any] = []
        attachment_ids: set[int] = set()

        for item in attachments:
            if not isinstance(item, dict):
                normalized.append(item)
                continue

            payload = dict(item)
            raw_id = payload.get("attachment_id")
            attachment_id = raw_id if isinstance(raw_id, int) and raw_id > 0 else None
            if attachment_id is None:
                attachment_id = self.extract_attachment_id(payload.get("url"))
            if attachment_id is not None:
                payload["attachment_id"] = attachment_id
                attachment_ids.add(attachment_id)
            normalized.append(payload)

        if not attachment_ids:
            return normalized

        result = await self.db.execute(
            select(Attachment).where(
                Attachment.id.in_(attachment_ids),
                Attachment.is_deleted.is_(False),
            )
        )
        attachment_map = {item.id: item for item in result.scalars()}

        for payload in normalized:
            if not isinstance(payload, dict):
                continue

            attachment_id = payload.get("attachment_id")
            if not isinstance(attachment_id, int):
                continue
            attachment = attachment_map.get(attachment_id)
            if not attachment:
                continue

            tenant_id = (
                attachment.tenant_id
                if attachment.tenant_id is not None
                else PLATFORM_TENANT_ID
            )
            payload.setdefault("name", attachment.original_name or attachment.name)
            payload.setdefault("mime_type", attachment.mime_type)
            if payload.get("type") == "image":
                payload["url"] = AttachmentDownloadService.build_preview_url(
                    attachment_id=attachment.id,
                    tenant_id=tenant_id,
                    visibility=attachment.visibility,
                )
            else:
                payload["url"] = AttachmentDownloadService.build_client_access_url(
                    attachment_id=attachment.id,
                    tenant_id=tenant_id,
                    visibility=attachment.visibility,
                )

        return normalized

    async def serialize_conversation_message(
        self,
        msg: ConversationMessage,
    ) -> dict[str, Any]:
        msg_dict = msg.to_dict()
        agent_obj = getattr(msg, "agent", None)
        if agent_obj is not None:
            msg_dict["agent_name"] = agent_obj.name
            msg_dict["agent_avatar"] = agent_obj.avatar
        else:
            msg_dict["agent_name"] = None
            msg_dict["agent_avatar"] = None
        runtime_meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
        metadata_payload = dict(msg_dict.get("metadata") or {})
        if runtime_meta:
            metadata_payload.update(runtime_meta)
        hydrated_attachments = await self.hydrate_chat_attachments(
            runtime_meta.get("attachments")
        )
        if hydrated_attachments is not None:
            metadata_payload["attachments"] = hydrated_attachments
        metadata_payload = strip_legacy_interaction_mode_fields(metadata_payload)
        if metadata_payload:
            msg_dict["metadata"] = metadata_payload
        msg_dict["model_name"] = runtime_meta.get("model_name")
        if not msg_dict["model_name"] and getattr(msg, "model", None) is not None:
            msg_dict["model_name"] = msg.model.name
        msg_dict["provider_id"] = runtime_meta.get("provider_id")
        msg_dict["provider_name"] = runtime_meta.get("provider_name")
        msg_dict = sanitize_assistant_error_payload(msg_dict)
        msg_dict = patch_recovery_evidence_answer_payload(msg_dict)
        turn_flow = ConversationTurnFlowProjector.project_from_message_payload(msg_dict)
        if turn_flow is not None:
            msg_dict["turn_flow"] = turn_flow
            metadata_payload = dict(msg_dict.get("metadata") or {})
            metadata_payload["turn_flow"] = turn_flow
            msg_dict["metadata"] = metadata_payload
        return strip_assistant_legacy_turn_projection_fields(msg_dict)

    async def serialize_conversation_messages(
        self,
        messages: list[ConversationMessage],
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for message in messages:
            payload.append(await self.serialize_conversation_message(message))
        return payload

    async def serialize_search_messages(
        self,
        messages: list[ConversationMessage],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for msg in messages:
            msg_dict = msg.to_dict()
            runtime_meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            hydrated_attachments = await self.hydrate_chat_attachments(
                runtime_meta.get("attachments")
            )
            if runtime_meta or hydrated_attachments is not None:
                metadata_payload = dict(msg_dict.get("metadata") or {})
                metadata_payload.update(runtime_meta)
                if hydrated_attachments is not None:
                    metadata_payload["attachments"] = hydrated_attachments
                metadata_payload = strip_legacy_interaction_mode_fields(
                    metadata_payload
                )
                msg_dict["metadata"] = metadata_payload
            items.append(strip_assistant_legacy_turn_projection_fields(msg_dict))
        return items

    async def serialize_export_messages(
        self,
        messages: list[Any],
    ) -> list[dict[str, Any]]:
        serialized_messages: list[dict[str, Any]] = []
        for msg in messages:
            metadata_raw = self._safe_attr(msg, "metadata_")
            metadata_payload = (
                dict(metadata_raw) if isinstance(metadata_raw, dict) else None
            )
            hydrated_attachments = await self.hydrate_chat_attachments(
                metadata_payload.get("attachments") if metadata_payload else None
            )
            if hydrated_attachments is not None:
                metadata_payload = metadata_payload or {}
                metadata_payload["attachments"] = hydrated_attachments
            metadata_payload = strip_legacy_interaction_mode_fields(metadata_payload)
            agent_obj = self._safe_attr(msg, "agent")
            message_payload = {
                "role": self._safe_attr(msg, "role"),
                "content": self._safe_attr(msg, "content"),
                "token_count": self._safe_attr(msg, "token_count"),
                "tool_calls": self._safe_attr(msg, "tool_calls"),
                "tool_call_id": self._safe_attr(msg, "tool_call_id"),
                "tool_name": self._safe_attr(msg, "tool_name"),
                "agent_id": self._safe_attr(msg, "agent_id"),
                "agent_name": self._safe_attr(agent_obj, "name"),
                "agent_avatar": self._safe_attr(agent_obj, "avatar"),
                "created_at": self.format_dt(self._safe_attr(msg, "created_at")),
                "metadata": metadata_payload,
            }
            message_payload = sanitize_assistant_error_payload(message_payload)
            message_payload = patch_recovery_evidence_answer_payload(message_payload)
            projected_turn_flow = (
                ConversationTurnFlowProjector.project_from_message_payload(
                    message_payload
                )
            )
            if projected_turn_flow is not None:
                message_payload["turn_flow"] = projected_turn_flow
                next_metadata = (
                    dict(message_payload.get("metadata") or {})
                    if isinstance(message_payload.get("metadata"), dict)
                    else {}
                )
                next_metadata["turn_flow"] = projected_turn_flow
                message_payload["metadata"] = next_metadata
            export_payload = strip_assistant_legacy_turn_projection_fields(
                message_payload
            )
            if str(export_payload.get("role") or "") == "assistant":
                export_payload.pop("tool_calls", None)
            serialized_messages.append(export_payload)
        return serialized_messages

    async def resolve_last_assistant_message(
        self,
        *,
        conversation_id: int,
        message_list: list[dict[str, Any]],
        latest_assistant_loader: Callable[[int], Any] | None,
    ) -> dict[str, Any] | None:
        last_assistant_message = next(
            (
                msg
                for msg in reversed(message_list)
                if msg.get("role") == MessageRoleEnum.ASSISTANT.value
            ),
            None,
        )
        if not callable(latest_assistant_loader):
            return last_assistant_message

        latest_assistant_candidate = latest_assistant_loader(conversation_id)
        if not inspect.isawaitable(latest_assistant_candidate):
            return last_assistant_message
        latest_assistant_candidate = await latest_assistant_candidate
        if latest_assistant_candidate is None:
            return last_assistant_message
        return await self.serialize_conversation_message(latest_assistant_candidate)

    @staticmethod
    def build_conversation_detail_base(
        conversation: AgentConversation,
        *,
        message_list: list[dict[str, Any]],
        message_count: int,
    ) -> dict[str, Any]:
        result = conversation.to_dict()
        if "metadata" in result:
            metadata_payload = strip_legacy_interaction_mode_fields(
                result.get("metadata")
            )
            if isinstance(metadata_payload, dict) and metadata_payload.get(
                "last_error"
            ):
                metadata_payload["last_error"] = (
                    sanitize_conversation_last_error_payload(
                        metadata_payload.get("last_error")
                    )
                )
            if metadata_payload:
                result["metadata"] = metadata_payload
            else:
                result.pop("metadata", None)
        result["message_list"] = message_list
        result["message_count"] = message_count
        agent_obj = getattr(conversation, "agent", None)
        result["agent_name"] = agent_obj.name if agent_obj is not None else None
        return result

    @staticmethod
    def extract_interaction_modes(
        conversation_metadata: dict[str, Any] | None,
    ) -> tuple[str, str]:
        metadata = (
            conversation_metadata if isinstance(conversation_metadata, dict) else {}
        )
        raw_requested_mode = str(
            metadata.get("interaction_mode_requested")
            or metadata.get("interaction_mode")
            or "trusted_auto"
        )
        raw_effective_mode = str(metadata.get("interaction_mode") or "trusted_auto")
        interaction_mode_requested = normalize_requested_interaction_mode(
            raw_requested_mode
        )
        interaction_mode_effective = normalize_requested_interaction_mode(
            raw_effective_mode
        )
        return interaction_mode_requested, interaction_mode_effective

    @staticmethod
    def build_error_only_runtime_projection(
        *,
        conversation_last_error: dict[str, Any] | None,
        compaction_snapshot: dict[str, Any] | None,
        interaction_mode_effective: str,
        downgrade_reason: Any,
    ) -> dict[str, Any]:
        del interaction_mode_effective, downgrade_reason
        payload = {
            "context_diagnostics": {
                "estimated_tokens": None,
                "context_compacted": False,
                "compact_summary_present": bool(
                    (compaction_snapshot or {}).get("summary")
                ),
                "memory_recalled": False,
                "memory_flush_triggered": False,
                "prune_stats": None,
                "rag_source_kinds": [],
                "last_interrupted": bool(
                    (conversation_last_error or {}).get("partial")
                ),
                "turn_outcome": "failed" if conversation_last_error else None,
                "termination_reason": "stream_execution_error"
                if conversation_last_error
                else None,
                "failure_kind": (conversation_last_error or {}).get("error_type"),
                "persistence_error": bool(conversation_last_error),
                "last_error": conversation_last_error,
            },
            "last_run_summary": {
                "completion_reason": "stream_execution_error"
                if conversation_last_error
                else None,
                "created_at": (conversation_last_error or {}).get("timestamp"),
                "interrupted": bool((conversation_last_error or {}).get("partial")),
                "provider_name": None,
                "runtime_model_name": None,
                "turn_outcome": "failed" if conversation_last_error else None,
                "termination_reason": "stream_execution_error"
                if conversation_last_error
                else None,
                "failure_kind": (conversation_last_error or {}).get("error_type"),
                "persistence_error": bool(conversation_last_error),
                "error_message": (conversation_last_error or {}).get(
                    "friendly_message"
                ),
            },
        }
        if conversation_last_error:
            payload["last_error"] = conversation_last_error
        payload["turn_flow"] = ConversationTurnFlowProjector.build_error_only_turn_flow(
            conversation_last_error=conversation_last_error
        )
        return payload

    @staticmethod
    def _to_chat_message(msg: ConversationMessage) -> ChatMessage | None:
        if msg.role == MessageRoleEnum.SYSTEM.value:
            return None

        msg_attachments = None
        msg_reasoning_content = None
        if msg.metadata_ and isinstance(msg.metadata_, dict):
            msg_attachments = msg.metadata_.get("attachments")
            raw_thinking = msg.metadata_.get("thinking_content")
            if isinstance(raw_thinking, str) and raw_thinking.strip():
                msg_reasoning_content = raw_thinking.strip()

        msg_content = msg.content or ""
        if (
            msg.role == MessageRoleEnum.ASSISTANT.value
            and msg.tool_calls
            and msg_reasoning_content
            and msg_content.strip() == msg_reasoning_content
        ):
            msg_content = ""

        return ChatMessage(
            role=msg.role,
            content=msg_content,
            tool_calls=msg.tool_calls,
            tool_call_id=msg.tool_call_id,
            attachments=msg_attachments,
            reasoning_content=msg_reasoning_content,
            metadata=normalize_json_safe_dict(msg.metadata_),
        )

    @staticmethod
    def build_chat_history_messages(
        db_messages: list[ConversationMessage],
        *,
        max_tokens: int,
    ) -> list[ChatMessage]:
        chat_messages: list[ChatMessage] = []
        for msg in db_messages:
            chat_message = ConversationReadModelService._to_chat_message(msg)
            if chat_message is not None:
                chat_messages.append(chat_message)

        if max_tokens > 0 and chat_messages:
            total = sum(estimate_chat_message_tokens(m) for m in chat_messages)
            while total > max_tokens and len(chat_messages) > 1:
                removed = chat_messages.pop(0)
                total -= estimate_chat_message_tokens(removed)

        return chat_messages

    async def enrich_conversation_list(
        self,
        items: list[AgentConversation],
        *,
        include_user_info: bool = False,
    ) -> list[dict[str, Any]]:
        user_map: dict[int, dict[str, Any]] = {}
        if include_user_info:
            user_ids = {
                conversation.user_id
                for conversation in items
                if conversation.user_id is not None
            }
            user_map = await self.tenant_admin_repo.batch_load_user_info(user_ids)

        result: list[dict[str, Any]] = []
        for item in items:
            payload = item.to_dict()
            agent_obj = getattr(item, "agent", None)
            if agent_obj is not None:
                payload["agent_name"] = agent_obj.name
                payload["agent_avatar"] = agent_obj.avatar
            else:
                payload["agent_name"] = None
                payload["agent_avatar"] = None

            if include_user_info:
                payload["user_info"] = (
                    user_map.get(item.user_id) if item.user_id else None
                )

            result.append(payload)
        return result

    async def enrich_conversation_detail(
        self,
        detail: dict[str, Any],
        *,
        conversation: AgentConversation,
    ) -> dict[str, Any]:
        agent_obj = getattr(conversation, "agent", None)
        detail["agent_avatar"] = agent_obj.avatar if agent_obj else None

        if conversation.user_id is not None:
            user_map = await self.tenant_admin_repo.batch_load_user_info(
                {conversation.user_id},
            )
            detail["user_info"] = user_map.get(conversation.user_id)
        else:
            detail["user_info"] = None

        return detail


__all__ = ["ConversationReadModelService"]
