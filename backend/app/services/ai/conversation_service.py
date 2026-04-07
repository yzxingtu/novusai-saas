"""
对话数据生命周期管理 Service / Conversation Lifecycle Service

提供对话列表、详情、搜索、归档、删除和导出
Provides conversation list, detail, search, archive, delete and export.
"""

import inspect
import json
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine.output_parser import parse_output
from app.ai.engine.types import ExecutionResult
from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.text_semantics import extract_public_attachment_reference
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    ActionLevelEnum,
    ConversationOwnerTypeEnum,
    ConversationStatusEnum,
    MessageRoleEnum,
)
from app.enums.execution import (
    ExecutionDecisionScopeEnum,
    ExecutionDecisionStatusEnum,
    ExecutionDecisionSubjectEnum,
    ExecutionDecisionTypeEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.action_log import AIActionLog
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.call_log import AICallLog
from app.models.ai.conversation_message import ConversationMessage
from app.models.ai.execution_decision import ExecutionDecision
from app.models.tenant.attachment import Attachment
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.action_log_service import resolve_action_level, write_ai_action_log
from app.services.ai.execution_decision_service import ExecutionDecisionService
from app.services.ai.execution_trust_policy_service import ExecutionTrustPolicyService
from app.services.ai.session_memory_service import SessionMemoryService
from app.services.tenant.attachment_download_service import AttachmentDownloadService

if TYPE_CHECKING:
    from app.repositories.tenant.tenant_admin_repository import (
        TenantAdminRepository,
    )

logger = LogManager.get_logger("ai.conversation_service")
_CONTEXT_COMPACTION_METADATA_KEY = "context_compaction"


class ConversationService(
    TenantService[AgentConversation, AgentConversationRepository]
):
    """
    对话数据生命周期管理 Service / Conversation lifecycle service.

    提供对话列表、详情、搜索、归档、删除和导出
    """

    model = AgentConversation
    repository_class = AgentConversationRepository

    @staticmethod
    def _format_dt(dt: datetime | None) -> str | None:
        """将 naive UTC 时间序列化为 ISO 8601（带 +00:00）/ Serialize naive UTC datetime to ISO 8601 with +00:00 suffix."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @staticmethod
    def _extract_attachment_id(raw_url: Any) -> int | None:
        attachment_id, _ = extract_public_attachment_reference(raw_url)
        return attachment_id

    async def _hydrate_chat_attachments(
        self,
        attachments: Any,
    ) -> Any:
        """Refresh persisted chat attachment URLs and backfill attachment_id."""
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
                attachment_id = self._extract_attachment_id(payload.get("url"))
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

    @property
    def message_repo(self) -> ConversationMessageRepository:
        """获取消息 Repository（延迟创建） / Get message repo (lazy init)."""
        if not hasattr(self, "_message_repo"):
            self._message_repo = ConversationMessageRepository(
                self.db,
                self.tenant_id,
            )
        return self._message_repo

    @property
    def tenant_admin_repo(self) -> "TenantAdminRepository":
        """获取企业管理员 Repository（延迟创建） / Get tenant admin repo (lazy init)."""
        if not hasattr(self, "_tenant_admin_repo"):
            from app.repositories.tenant.tenant_admin_repository import (
                TenantAdminRepository,
            )

            self._tenant_admin_repo = TenantAdminRepository(
                self.db,
                self.tenant_id,
            )
        return self._tenant_admin_repo

    async def _serialize_conversation_message(
        self,
        msg: ConversationMessage,
    ) -> dict[str, Any]:
        """Normalize a conversation message for detail/CLI surfaces."""
        msg_dict = msg.to_dict()
        agent_obj = getattr(msg, "agent", None)
        if agent_obj is not None:
            msg_dict["agent_name"] = agent_obj.name
            msg_dict["agent_avatar"] = agent_obj.avatar
        else:
            msg_dict["agent_name"] = None
            msg_dict["agent_avatar"] = None
        runtime_meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
        hydrated_attachments = await self._hydrate_chat_attachments(
            runtime_meta.get("attachments")
        )
        if hydrated_attachments is not None:
            metadata_payload = dict(msg_dict.get("metadata") or {})
            metadata_payload["attachments"] = hydrated_attachments
            msg_dict["metadata"] = metadata_payload
        msg_dict["model_name"] = runtime_meta.get("model_name")
        if not msg_dict["model_name"] and getattr(msg, "model", None) is not None:
            msg_dict["model_name"] = msg.model.name
        msg_dict["provider_id"] = runtime_meta.get("provider_id")
        msg_dict["provider_name"] = runtime_meta.get("provider_name")
        return msg_dict

    async def enrich_conversation_list(
        self,
        items: list[AgentConversation],
        include_user_info: bool = False,
    ) -> list[dict]:
        """
        将对话列表 ORM 对象转为字典并补充 agent/user 信息 / Convert conversation list to dict and enrich agent/user info.

        Args:
            items: 对话 ORM 对象列表
            include_user_info: 是否附加 user_info（企业端管理页使用）
        """
        user_map: dict[int, dict] = {}
        if include_user_info:
            user_ids = {c.user_id for c in items if c.user_id is not None}
            user_map = await self.tenant_admin_repo.batch_load_user_info(user_ids)

        result: list[dict] = []
        for item in items:
            d = item.to_dict()
            agent_obj = getattr(item, "agent", None)
            if agent_obj is not None:
                d["agent_name"] = agent_obj.name
                d["agent_avatar"] = agent_obj.avatar
            else:
                d["agent_name"] = None
                d["agent_avatar"] = None

            if include_user_info:
                d["user_info"] = user_map.get(item.user_id) if item.user_id else None

            result.append(d)
        return result

    async def enrich_conversation_detail(
        self,
        detail: dict,
        conversation: AgentConversation,
    ) -> dict:
        """
        补充对话详情的 agent_avatar 和 user_info / Enrich detail with agent_avatar and user_info.

        Args:
            detail: get_conversation_detail 返回的字典
            conversation: 对话 ORM 对象
        """
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

    # ========================================
    # 详情 / Detail
    # ========================================

    @classmethod
    async def get_service_for_conversation(
        cls,
        db: AsyncSession,
        conversation_id: int,
    ) -> tuple["ConversationService", AgentConversation]:
        repo = AdminAgentConversationRepository(db)
        conversation = await repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return cls(db, conversation.tenant_id), conversation

    @classmethod
    async def get_platform_admin_chat_service_for_user(
        cls,
        db: AsyncSession,
        conversation_id: int,
        admin_user_id: int,
    ) -> tuple["ConversationService", AgentConversation]:
        """Resolve platform-admin chat conversation scoped to current admin / 解析当前平台管理员自己的聊天会话。"""
        service = cls(db, PLATFORM_TENANT_ID)
        conversation = await service.get_accessible_conversation(
            conversation_id,
            user_id=admin_user_id,
            owner_type=ConversationOwnerTypeEnum.PLATFORM_ADMIN.value,
        )
        return service, conversation

    async def get_accessible_conversation(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> AgentConversation:
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        if owner_type is not None and conversation.owner_type != owner_type:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        if user_id is not None and conversation.user_id != user_id:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return conversation

    async def get_conversation_detail(
        self,
        conversation_id: int,
        message_skip: int = 0,
        message_limit: int = 50,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any]:
        """
        获取对话详情（含分页消息列表）/ Get conversation detail with paginated messages.

        Args:
            conversation_id: 对话 ID
            message_skip: 消息跳过数量
            message_limit: 消息返回数量

        Returns:
            对话详情字典，含 messages 和 message_count
        """
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )

        # 获取分页消息 / Fetch paginated messages
        messages = await self.message_repo.get_by_conversation(
            conversation_id=conversation_id,
            skip=message_skip,
            limit=message_limit,
        )
        message_count = await self.message_repo.count_by_conversation(
            conversation_id,
        )

        result = conversation.to_dict()
        # Enrich messages with agent info for avatars / 为消息补充智能体信息供头像展示
        message_list = []
        for msg in messages:
            message_list.append(await self._serialize_conversation_message(msg))
        result["message_list"] = message_list
        result["message_count"] = message_count

        # Extract linked agent name from conversation / 提取会话关联智能体名称
        result["agent_name"] = None
        try:
            agent_obj = getattr(conversation, "agent", None)
            if agent_obj is not None:
                result["agent_name"] = agent_obj.name
        except AttributeError:
            pass

        last_assistant_message = next(
            (
                msg
                for msg in reversed(message_list)
                if msg.get("role") == MessageRoleEnum.ASSISTANT.value
            ),
            None,
        )
        latest_assistant_loader = getattr(
            self.message_repo,
            "get_latest_assistant_message",
            None,
        )
        latest_assistant_message = None
        if callable(latest_assistant_loader):
            latest_assistant_candidate = latest_assistant_loader(conversation_id)
            if inspect.isawaitable(latest_assistant_candidate):
                latest_assistant_message = await latest_assistant_candidate
        if latest_assistant_message is not None:
            last_assistant_message = await self._serialize_conversation_message(
                latest_assistant_message
            )
        conversation_last_error = self._normalize_json_safe_dict(
            (conversation.metadata_ or {}).get("last_error")
            if isinstance(conversation.metadata_, dict)
            else None
        )
        compaction_snapshot = await self.get_context_compaction_snapshot(
            conversation.id
        )
        interaction_mode_effective = str(
            (conversation.metadata_ or {}).get("interaction_mode") or "confirm"
        )
        result["interaction_mode_effective"] = interaction_mode_effective
        if last_assistant_message is not None:
            result["context_diagnostics"] = self._build_context_diagnostics_payload(
                last_assistant_message,
                compaction_snapshot=compaction_snapshot,
                interaction_mode_effective=interaction_mode_effective,
            )
            result["last_run_summary"] = self._build_last_run_summary_payload(
                last_assistant_message,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=(conversation.metadata_ or {}).get(
                    "interaction_mode_downgrade_reason"
                ),
            )
        else:
            result["context_diagnostics"] = {
                "estimated_tokens": None,
                "context_compacted": False,
                "compact_summary_present": bool((compaction_snapshot or {}).get("summary")),
                "memory_recalled": False,
                "memory_flush_triggered": False,
                "prune_stats": None,
                "rag_source_kinds": [],
                "last_interrupted": bool((conversation_last_error or {}).get("partial")),
                "interaction_mode_effective": interaction_mode_effective,
                "turn_outcome": "failed"
                if conversation_last_error
                else None,
                "termination_reason": "stream_execution_error"
                if conversation_last_error
                else None,
                "failure_kind": (conversation_last_error or {}).get("error_type"),
                "persistence_error": bool(conversation_last_error),
                "last_error": conversation_last_error,
            }
            result["last_run_summary"] = {
                "completion_reason": "stream_execution_error"
                if conversation_last_error
                else None,
                "created_at": (conversation_last_error or {}).get("timestamp"),
                "downgrade_reason": (conversation.metadata_ or {}).get(
                    "interaction_mode_downgrade_reason"
                ),
                "interaction_mode_effective": interaction_mode_effective,
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
            }
        if conversation_last_error:
            result["last_error"] = conversation_last_error

        return result

    async def delete_accessible_conversation(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> None:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        await self.delete(conversation_id)

    async def update_conversation_title(
        self,
        conversation_id: int,
        title: str,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> AgentConversation:
        """更新对话标题 / Update conversation title."""
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        s = (title or "").strip()
        conversation.title = s[:200] if s else None
        await self.db.flush()
        return conversation

    async def update_last_assistant_interaction_state(
        self,
        conversation_id: int,
        updates: list[dict[str, Any]],
        user_id: int | None = None,
        owner_type: str | None = None,
        interaction_mode_requested: str | None = None,
        interaction_mode_effective: str | None = None,
        interaction_mode_downgrade_reason: str | None = None,
    ) -> int:
        """Persist client interaction state onto the latest matching assistant message / 将客户端交互状态持久化到最近匹配的 assistant 消息。"""
        if not updates:
            return 0

        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=50,
        )
        assistant_messages = [
            msg
            for msg in reversed(messages)
            if msg.role == MessageRoleEnum.ASSISTANT.value
        ]
        if not assistant_messages:
            return 0

        updated = 0
        seen_ids: set[int] = set()
        decision_service = ExecutionDecisionService(
            self.db,
            self._get_memory_tenant_id(),
        )

        def _match_action_buttons(
            metadata: dict[str, Any],
            value: str | None,
        ) -> bool:
            buttons = metadata.get("action_buttons")
            if not isinstance(buttons, list) or not value:
                return False
            return any(
                isinstance(item, dict) and item.get("value") == value
                for item in buttons
            )

        def _match_pending_confirmation(
            metadata: dict[str, Any],
            tool_calls: list | None,
            action: str | None,
            table: str | None,
        ) -> bool:
            pending = metadata.get("pending_confirmation")
            if isinstance(pending, dict):
                if action and pending.get("action") not in (None, action):
                    return False
                return not (table and pending.get("table") not in (None, table))
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_confirmation")
                    if not isinstance(nested, dict):
                        continue
                    if action and nested.get("action") not in (None, action):
                        continue
                    if table and nested.get("table") not in (None, table):
                        continue
                    return True
            return False

        def _find_pending_confirmation_evidence(
            metadata: dict[str, Any],
            tool_calls: list | None,
            action: str | None,
            table: str | None,
        ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            pending = metadata.get("pending_confirmation")
            if isinstance(pending, dict):
                if action and pending.get("action") not in (None, action):
                    return None, None
                if table and pending.get("table") not in (None, table):
                    return None, None
                return dict(pending), None
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_confirmation")
                    if not isinstance(nested, dict):
                        continue
                    if action and nested.get("action") not in (None, action):
                        continue
                    if table and nested.get("table") not in (None, table):
                        continue
                    return dict(nested), dict(tc)
            return None, None

        def _match_pending_consent(
            metadata: dict[str, Any],
            tool_calls: list | None,
            tool_name: str | None,
        ) -> bool:
            pending = metadata.get("pending_consent")
            if isinstance(pending, dict):
                return not (
                    tool_name and pending.get("tool_name") not in (None, tool_name)
                )
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_consent")
                    if not isinstance(nested, dict):
                        continue
                    if tool_name and nested.get("tool_name") not in (None, tool_name):
                        continue
                    return True
            return False

        def _find_pending_consent_evidence(
            metadata: dict[str, Any],
            tool_calls: list | None,
            tool_name: str | None,
        ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            pending = metadata.get("pending_consent")
            if isinstance(pending, dict):
                if tool_name and pending.get("tool_name") not in (None, tool_name):
                    return None, None
                return dict(pending), None
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_consent")
                    if not isinstance(nested, dict):
                        continue
                    if tool_name and nested.get("tool_name") not in (None, tool_name):
                        continue
                    return dict(nested), dict(tc)
            return None, None

        for raw_update in updates:
            kind = str(raw_update.get("kind") or "")
            if not kind:
                continue
            for msg in assistant_messages:
                metadata = dict(msg.metadata_ or {})
                tool_calls = [
                    dict(tc) for tc in (msg.tool_calls or []) if isinstance(tc, dict)
                ]
                decision_payload: dict[str, Any] | None = None

                matched = False
                if kind == "action_buttons":
                    matched = _match_action_buttons(metadata, raw_update.get("value"))
                    if matched:
                        metadata["action_buttons_used"] = True
                elif kind == "pending_confirmation":
                    pending_evidence, matched_tool_call = (
                        _find_pending_confirmation_evidence(
                            metadata,
                            tool_calls,
                            raw_update.get("action"),
                            raw_update.get("table"),
                        )
                    )
                    matched = _match_pending_confirmation(
                        metadata,
                        tool_calls,
                        raw_update.get("action"),
                        raw_update.get("table"),
                    )
                    if matched:
                        pending = dict(metadata.get("pending_confirmation") or {})
                        pending["resolved"] = True
                        pending["rejected"] = bool(raw_update.get("rejected"))
                        metadata["pending_confirmation"] = pending
                        for tc in tool_calls:
                            nested = tc.get("pending_confirmation")
                            if isinstance(nested, dict):
                                next_nested = dict(nested)
                                next_nested["resolved"] = True
                                next_nested["rejected"] = bool(
                                    raw_update.get("rejected")
                                )
                                tc["pending_confirmation"] = next_nested
                        action_name = str(
                            raw_update.get("action") or pending.get("action") or ""
                        ).strip()
                        table_name = str(
                            raw_update.get("table") or pending.get("table") or ""
                        ).strip()
                        tool_call_id = (
                            str((matched_tool_call or {}).get("id") or "").strip()
                            or None
                        )
                        tool_name = (
                            str(
                                ((matched_tool_call or {}).get("function") or {}).get(
                                    "name"
                                )
                                or ""
                            ).strip()
                            or None
                        )
                        rejected = bool(raw_update.get("rejected"))
                        extra_evidence = {
                            "interaction_mode_effective": raw_update.get(
                                "interaction_mode_effective"
                            ),
                            "downgraded_from": raw_update.get("downgraded_from"),
                            "downgrade_reason": raw_update.get("downgrade_reason"),
                            "auto_approve_source": raw_update.get(
                                "auto_approve_source"
                            ),
                        }
                        decision_payload = {
                            "tenant_id": self._get_memory_tenant_id(),
                            "conversation_id": conversation_id,
                            "agent_id": conversation.agent_id,
                            "operator_id": user_id,
                            "operator_type": owner_type,
                            "decision_type": ExecutionDecisionTypeEnum.CONFIRMATION.value,
                            "subject_type": ExecutionDecisionSubjectEnum.DATA_ACTION.value,
                            "status": (
                                ExecutionDecisionStatusEnum.REJECTED.value
                                if rejected
                                else ExecutionDecisionStatusEnum.APPROVED.value
                            ),
                            "decision_scope": ExecutionDecisionScopeEnum.ONCE.value,
                            "risk_level": resolve_action_level(
                                action_name,
                                default=ActionLevelEnum.SAFE_WRITE.value,
                            ),
                            "auto_approved": False,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "action_name": action_name or None,
                            "table_name": table_name or None,
                            "correlation_key": (
                                f"confirmation:{conversation_id}:{msg.id}:{tool_call_id or action_name or table_name}:"
                                f"{'rejected' if rejected else 'approved'}"
                            ),
                            "reason": "user_confirmation",
                            "evidence": {
                                **(pending_evidence or {}),
                                **{
                                    key: value
                                    for key, value in extra_evidence.items()
                                    if value is not None
                                },
                            },
                        }
                elif kind == "pending_consent":
                    pending_evidence, matched_tool_call = (
                        _find_pending_consent_evidence(
                            metadata,
                            tool_calls,
                            raw_update.get("tool_name"),
                        )
                    )
                    matched = _match_pending_consent(
                        metadata,
                        tool_calls,
                        raw_update.get("tool_name"),
                    )
                    if matched:
                        pending = dict(metadata.get("pending_consent") or {})
                        pending["resolved"] = True
                        pending["rejected"] = bool(raw_update.get("rejected"))
                        pending["auto_approved"] = bool(raw_update.get("auto_approved"))
                        metadata["pending_consent"] = pending
                        for tc in tool_calls:
                            nested = tc.get("pending_consent")
                            if isinstance(nested, dict):
                                next_nested = dict(nested)
                                next_nested["resolved"] = True
                                next_nested["rejected"] = bool(
                                    raw_update.get("rejected")
                                )
                                next_nested["auto_approved"] = bool(
                                    raw_update.get("auto_approved")
                                )
                                tc["pending_consent"] = next_nested
                        tool_name = str(
                            raw_update.get("tool_name")
                            or pending.get("tool_name")
                            or (
                                ((matched_tool_call or {}).get("function") or {}).get(
                                    "name"
                                )
                            )
                            or ""
                        ).strip()
                        tool_call_id = (
                            str((matched_tool_call or {}).get("id") or "").strip()
                            or None
                        )
                        auto_approved = bool(raw_update.get("auto_approved"))
                        rejected = bool(raw_update.get("rejected"))
                        extra_evidence = {
                            "interaction_mode_effective": raw_update.get(
                                "interaction_mode_effective"
                            ),
                            "downgraded_from": raw_update.get("downgraded_from"),
                            "downgrade_reason": raw_update.get("downgrade_reason"),
                            "auto_approve_source": raw_update.get(
                                "auto_approve_source"
                            ),
                        }
                        decision_payload = {
                            "tenant_id": self._get_memory_tenant_id(),
                            "conversation_id": conversation_id,
                            "agent_id": conversation.agent_id,
                            "operator_id": user_id,
                            "operator_type": owner_type,
                            "decision_type": ExecutionDecisionTypeEnum.CONSENT.value,
                            "subject_type": ExecutionDecisionSubjectEnum.TOOL_CALL.value,
                            "status": (
                                ExecutionDecisionStatusEnum.AUTO_APPROVED.value
                                if auto_approved
                                else (
                                    ExecutionDecisionStatusEnum.REJECTED.value
                                    if rejected
                                    else ExecutionDecisionStatusEnum.APPROVED.value
                                )
                            ),
                            "decision_scope": (
                                ExecutionDecisionScopeEnum.CONVERSATION.value
                                if auto_approved
                                else ExecutionDecisionScopeEnum.ONCE.value
                            ),
                            "risk_level": ExecutionTrustPolicyService.tool_risk_level(
                                tool_name=tool_name,
                                tool_family=ExecutionTrustPolicyService.tool_family_for_name(
                                    tool_name
                                ),
                            ),
                            "auto_approved": auto_approved,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name or None,
                            "action_name": None,
                            "table_name": None,
                            "correlation_key": (
                                f"consent:{conversation_id}:{msg.id}:{tool_call_id or tool_name}:"
                                f"{'auto' if auto_approved else ('rejected' if rejected else 'approved')}"
                            ),
                            "reason": "tool_consent",
                            "evidence": {
                                **(pending_evidence or {}),
                                **{
                                    key: value
                                    for key, value in extra_evidence.items()
                                    if value is not None
                                },
                            },
                        }

                if not matched:
                    continue

                normalized_metadata = self._normalize_json_safe_dict(metadata) or {}
                normalized_tool_calls_raw = self._normalize_json_safe(
                    tool_calls or msg.tool_calls
                )
                normalized_tool_calls = (
                    normalized_tool_calls_raw
                    if isinstance(normalized_tool_calls_raw, list)
                    else (tool_calls or msg.tool_calls)
                )
                await self.message_repo.update(
                    msg.id,
                    {
                        "metadata_": normalized_metadata,
                        "tool_calls": normalized_tool_calls,
                    },
                )
                msg.metadata_ = normalized_metadata
                msg.tool_calls = normalized_tool_calls
                if msg.id not in seen_ids:
                    updated += 1
                    seen_ids.add(msg.id)
                should_record_decision = (
                    decision_payload is not None
                    and user_id is not None
                    and bool(owner_type)
                )
                if should_record_decision:
                    try:
                        interaction_context: dict[str, Any] = {}
                        planner_context = None
                        context_diagnostics = metadata.get("context_diagnostics")
                        if isinstance(context_diagnostics, dict) and isinstance(
                            context_diagnostics.get("tool_planner"), dict
                        ):
                            planner_context = dict(
                                context_diagnostics.get("tool_planner") or {}
                            )
                        elif isinstance(
                            metadata.get("last_run_summary"), dict
                        ) and isinstance(
                            metadata.get("last_run_summary", {}).get("tool_planner"),
                            dict,
                        ):
                            planner_context = dict(
                                metadata.get("last_run_summary", {}).get("tool_planner")
                                or {}
                            )
                        if interaction_mode_requested:
                            interaction_context["interaction_mode_requested"] = (
                                interaction_mode_requested
                            )
                        if interaction_mode_effective:
                            interaction_context["interaction_mode_effective"] = (
                                interaction_mode_effective
                            )
                        if interaction_mode_downgrade_reason:
                            interaction_context["interaction_mode_downgrade_reason"] = (
                                interaction_mode_downgrade_reason
                            )
                        if planner_context:
                            interaction_context["tool_planner"] = planner_context
                        if interaction_context:
                            evidence_payload = dict(
                                decision_payload.get("evidence") or {}
                            )
                            evidence_payload.update(interaction_context)
                            decision_payload["evidence"] = evidence_payload
                        mode_tag = f"interaction_mode={interaction_mode_effective or 'confirm'}"
                        reason = str(decision_payload.get("reason") or "").strip()
                        decision_payload["reason"] = (
                            f"{reason}|{mode_tag}" if reason else mode_tag
                        )
                        decision = await decision_service.record_decision(
                            decision_payload
                        )
                        await write_ai_action_log(
                            self.db,
                            tenant_id=self._get_memory_tenant_id(),
                            agent_id=conversation.agent_id,
                            conversation_id=conversation_id,
                            execution_decision_id=getattr(decision, "id", None),
                            tool_call_id=decision_payload.get("tool_call_id"),
                            operator_id=user_id,
                            operator_type=owner_type,
                            action_name=(
                                decision_payload.get("tool_name")
                                or decision_payload.get("action_name")
                                or kind
                            ),
                            action_type="confirm",
                            action_level=decision_payload.get("risk_level")
                            or ActionLevelEnum.SAFE_WRITE.value,
                            status=(
                                "rejected"
                                if decision_payload.get("status")
                                == ExecutionDecisionStatusEnum.REJECTED.value
                                else "success"
                            ),
                            request_data={
                                "decision_id": getattr(decision, "id", None),
                                "decision_type": decision_payload.get("decision_type"),
                                "decision_scope": decision_payload.get(
                                    "decision_scope"
                                ),
                                "subject_type": decision_payload.get("subject_type"),
                                "tool_call_id": decision_payload.get("tool_call_id"),
                                "tool_name": decision_payload.get("tool_name"),
                                "action_name": decision_payload.get("action_name"),
                                "table_name": decision_payload.get("table_name"),
                                "evidence": decision_payload.get("evidence"),
                            },
                            response_data={
                                "decision_status": decision_payload.get("status"),
                                "auto_approved": bool(
                                    decision_payload.get("auto_approved")
                                ),
                                "correlation_key": decision_payload.get(
                                    "correlation_key"
                                ),
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "Record execution decision degraded: tenant={} conversation={} message={} kind={} err={}",
                            self._get_memory_tenant_id(),
                            conversation_id,
                            msg.id,
                            kind,
                            str(exc),
                        )
                break

        return updated

    def _get_memory_tenant_id(self) -> int:
        return self.tenant_id if self.tenant_id is not None else PLATFORM_TENANT_ID

    @staticmethod
    def _build_context_diagnostics_payload(
        last_assistant_message: dict[str, Any] | None,
        *,
        compaction_snapshot: dict[str, Any] | None,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        metadata = (
            dict(last_assistant_message.get("metadata") or {})
            if isinstance(last_assistant_message, dict)
            else {}
        )
        turn_meta = ConversationService._extract_turn_diagnostics_from_metadata(
            metadata
        )
        rag_sources = metadata.get("rag_sources")
        rag_sources = rag_sources if isinstance(rag_sources, list) else []
        last_interrupted = bool(metadata.get("interrupted")) or (
            turn_meta.get("termination_reason") == "interrupted"
        )
        return {
            "estimated_tokens": (
                last_assistant_message.get("token_count")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "context_compacted": bool(metadata.get("context_compacted")),
            "compact_summary_present": bool((compaction_snapshot or {}).get("summary")),
            "memory_recalled": bool(metadata.get("memory_recalled")),
            "memory_flush_triggered": bool(metadata.get("memory_flush_triggered")),
            "prune_stats": metadata.get("prune_stats"),
            "rag_source_kinds": list(metadata.get("rag_source_kinds") or []),
            "last_interrupted": last_interrupted,
            "interaction_mode_effective": interaction_mode_effective,
            "turn_outcome": turn_meta.get("turn_outcome"),
            "termination_reason": turn_meta.get("termination_reason"),
            "protocol_path": turn_meta.get("protocol_path"),
            "tool_planner": turn_meta.get("tool_planner"),
            "selected_tool_names": turn_meta.get("selected_tool_names") or [],
            "selected_skill_names": turn_meta.get("selected_skill_names") or [],
            "context_sources": turn_meta.get("context_sources") or [],
            "execution_path": turn_meta.get("execution_path"),
            "active_intent_id": turn_meta.get("active_intent_id"),
            "continuation_source": turn_meta.get("continuation_source"),
            "conversation_outcome": turn_meta.get("conversation_outcome"),
            "intent_plan": turn_meta.get("intent_plan") or [],
            "budget": turn_meta.get("budget"),
            "budget_status": turn_meta.get("budget_status"),
            "budget_exit_reason": turn_meta.get("budget_exit_reason"),
            "candidate_tool_names": turn_meta.get("candidate_tool_names") or [],
            "retry_events": turn_meta.get("retry_events") or [],
            "partial_exit_reason": turn_meta.get("partial_exit_reason"),
            "failure_kind": turn_meta.get("failure_kind"),
            "provider_events": turn_meta.get("provider_events") or [],
            "contract_breach_type": turn_meta.get("contract_breach_type"),
            "tool_leak_detected": bool(turn_meta.get("tool_leak_detected")),
            "assistant_claimed_tool_call_without_tool_event": bool(
                turn_meta.get("assistant_claimed_tool_call_without_tool_event")
            ),
            "unfinished_intents": turn_meta.get("unfinished_intents") or [],
            "leaked_tool_names": turn_meta.get("leaked_tool_names") or [],
            "recovered_via_retry": turn_meta.get("recovered_via_retry"),
            "last_tool_name": turn_meta.get("last_tool_name"),
            "last_page_key": turn_meta.get("last_page_key"),
            "last_page_op": turn_meta.get("last_page_op"),
            "interrupted_stage": turn_meta.get("interrupted_stage"),
            "tool_loop_progress": turn_meta.get("tool_loop_progress") or {},
            "sync_rescue": turn_meta.get("sync_rescue"),
            "should_record_call_log": turn_meta.get("should_record_call_log"),
        }

    @staticmethod
    def _build_last_run_summary_payload(
        last_assistant_message: dict[str, Any] | None,
        *,
        interaction_mode_effective: str,
        downgrade_reason: Any,
    ) -> dict[str, Any]:
        metadata = (
            dict(last_assistant_message.get("metadata") or {})
            if isinstance(last_assistant_message, dict)
            else {}
        )
        turn_meta = ConversationService._extract_turn_diagnostics_from_metadata(
            metadata
        )
        completion_reason = turn_meta.get("termination_reason") or metadata.get(
            "completion_reason"
        )
        interrupted = bool(metadata.get("interrupted")) or (
            completion_reason == "interrupted"
        )
        return {
            "completion_reason": completion_reason,
            "created_at": (
                last_assistant_message.get("created_at")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "downgrade_reason": downgrade_reason,
            "interaction_mode_effective": interaction_mode_effective,
            "interrupted": interrupted,
            "provider_name": (
                last_assistant_message.get("provider_name")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "runtime_model_name": (
                last_assistant_message.get("model_name")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "turn_outcome": turn_meta.get("turn_outcome"),
            "termination_reason": turn_meta.get("termination_reason"),
            "protocol_path": turn_meta.get("protocol_path"),
            "tool_planner": turn_meta.get("tool_planner"),
            "selected_tool_names": turn_meta.get("selected_tool_names") or [],
            "selected_skill_names": turn_meta.get("selected_skill_names") or [],
            "context_sources": turn_meta.get("context_sources") or [],
            "execution_path": turn_meta.get("execution_path"),
            "active_intent_id": turn_meta.get("active_intent_id"),
            "continuation_source": turn_meta.get("continuation_source"),
            "conversation_outcome": turn_meta.get("conversation_outcome"),
            "intent_plan": turn_meta.get("intent_plan") or [],
            "budget": turn_meta.get("budget"),
            "budget_status": turn_meta.get("budget_status"),
            "budget_exit_reason": turn_meta.get("budget_exit_reason"),
            "candidate_tool_names": turn_meta.get("candidate_tool_names") or [],
            "retry_events": turn_meta.get("retry_events") or [],
            "partial_exit_reason": turn_meta.get("partial_exit_reason"),
            "failure_kind": turn_meta.get("failure_kind"),
            "provider_events": turn_meta.get("provider_events") or [],
            "contract_breach_type": turn_meta.get("contract_breach_type"),
            "tool_leak_detected": bool(turn_meta.get("tool_leak_detected")),
            "assistant_claimed_tool_call_without_tool_event": bool(
                turn_meta.get("assistant_claimed_tool_call_without_tool_event")
            ),
            "unfinished_intents": turn_meta.get("unfinished_intents") or [],
            "leaked_tool_names": turn_meta.get("leaked_tool_names") or [],
            "recovered_via_retry": turn_meta.get("recovered_via_retry"),
            "last_tool_name": turn_meta.get("last_tool_name"),
            "last_page_key": turn_meta.get("last_page_key"),
            "last_page_op": turn_meta.get("last_page_op"),
            "interrupted_stage": turn_meta.get("interrupted_stage"),
            "tool_loop_progress": turn_meta.get("tool_loop_progress") or {},
            "sync_rescue": turn_meta.get("sync_rescue"),
            "should_record_call_log": turn_meta.get("should_record_call_log"),
        }

    async def rebuild_context_compaction_snapshot(
        self,
        conversation_id: int,
        *,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any] | None:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        context_config = (
            getattr(getattr(conversation, "agent", None), "context_config", None) or {}
        )
        max_chars = int(context_config.get("compact_max_summary_chars", 1600) or 1600)
        total_messages = await self.message_repo.count_by_conversation(conversation_id)
        messages = await self.load_chat_history(
            conversation_id=conversation_id,
            max_messages=max(total_messages, 1),
            max_tokens=0,
        )
        if not messages:
            return None

        from app.ai.context.engine import ConversationContextEngine

        summary = ConversationContextEngine._build_compact_summary(
            messages,
            max_chars=max_chars,
        )
        if not summary:
            return None
        source_messages = [
            message for message in messages if message.role in {"user", "assistant"}
        ]
        return await self.upsert_context_compaction_snapshot(
            conversation_id,
            summary=summary,
            source_message_count=len(source_messages),
            source_token_estimate=sum(
                estimate_tokens(message.content or "") for message in source_messages
            ),
        )

    async def get_conversation_timeline(
        self,
        conversation_id: int,
        *,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        messages = await self.message_repo.get_by_conversation(
            conversation_id=conversation_id,
            skip=0,
            limit=500,
        )
        interaction_mode_effective = str(
            (conversation.metadata_ or {}).get("interaction_mode") or "confirm"
        )

        items: list[dict[str, Any]] = []
        for message in messages:
            metadata = dict(message.metadata_ or {})
            items.append(
                {
                    "type": f"message:{message.role}",
                    "occurred_at": self._format_dt(message.created_at) or "",
                    "status": "completed",
                    "title": f"message.{message.role}",
                    "summary": (message.content or "")[:300] or None,
                    "tool_name": message.tool_name,
                    "risk_level": None,
                    "auto_approved": None,
                    "interaction_mode_effective": interaction_mode_effective,
                    "correlation_key": None,
                    "trace_id": None,
                    "detail_payload": {
                        "message_id": message.id,
                        "metadata": metadata or None,
                        "tool_call_id": message.tool_call_id,
                    },
                }
            )

        decisions = (
            (
                await self.db.execute(
                    select(ExecutionDecision)
                    .where(
                        ExecutionDecision.tenant_id == self._get_memory_tenant_id(),
                        ExecutionDecision.conversation_id == conversation_id,
                        ExecutionDecision.is_deleted.is_(False),
                    )
                    .order_by(ExecutionDecision.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for decision in decisions:
            evidence = dict(decision.evidence or {})
            items.append(
                {
                    "type": "execution_decision",
                    "occurred_at": self._format_dt(decision.created_at) or "",
                    "status": decision.status,
                    "title": decision.decision_type,
                    "summary": decision.reason,
                    "tool_name": decision.tool_name,
                    "risk_level": decision.risk_level,
                    "auto_approved": bool(decision.auto_approved),
                    "interaction_mode_effective": (
                        evidence.get("interaction_mode_effective")
                        or interaction_mode_effective
                    ),
                    "correlation_key": decision.correlation_key,
                    "trace_id": None,
                    "detail_payload": decision.to_dict(),
                }
            )

        action_logs = (
            (
                await self.db.execute(
                    select(AIActionLog)
                    .where(
                        AIActionLog.tenant_id == self._get_memory_tenant_id(),
                        AIActionLog.conversation_id == conversation_id,
                        AIActionLog.is_deleted.is_(False),
                    )
                    .order_by(AIActionLog.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for action_log in action_logs:
            items.append(
                {
                    "type": "action_log",
                    "occurred_at": self._format_dt(action_log.created_at) or "",
                    "status": action_log.status,
                    "title": action_log.action_name,
                    "summary": action_log.error_message or None,
                    "tool_name": action_log.action_name,
                    "risk_level": action_log.action_level,
                    "auto_approved": None,
                    "interaction_mode_effective": interaction_mode_effective,
                    "correlation_key": None,
                    "trace_id": action_log.trace_id,
                    "detail_payload": action_log.to_dict(),
                }
            )

        call_logs = (
            (
                await self.db.execute(
                    select(AICallLog)
                    .where(
                        AICallLog.tenant_id == self._get_memory_tenant_id(),
                        AICallLog.conversation_id == conversation_id,
                        AICallLog.is_deleted.is_(False),
                    )
                    .order_by(AICallLog.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for call_log in call_logs:
            items.append(
                {
                    "type": "call_log",
                    "occurred_at": self._format_dt(call_log.created_at) or "",
                    "status": call_log.status,
                    "title": call_log.request_type,
                    "summary": call_log.error_message or None,
                    "tool_name": None,
                    "risk_level": None,
                    "auto_approved": None,
                    "interaction_mode_effective": interaction_mode_effective,
                    "correlation_key": None,
                    "trace_id": call_log.trace_id,
                    "detail_payload": call_log.to_dict(),
                }
            )

        call_log_summary = await self._build_call_log_summary(conversation_id)
        if call_log_summary:
            items.append(
                {
                    "type": "call_log_summary",
                    "occurred_at": self._format_dt(call_log_summary.get("last_call_at"))
                    or "",
                    "status": "summary",
                    "title": "call_log_summary",
                    "summary": f"{call_log_summary['call_count']} calls, {call_log_summary['total_tokens']} tokens",
                    "tool_name": None,
                    "risk_level": None,
                    "auto_approved": None,
                    "interaction_mode_effective": interaction_mode_effective,
                    "correlation_key": None,
                    "trace_id": None,
                    "detail_payload": call_log_summary,
                }
            )

        items.sort(key=lambda item: item.get("occurred_at") or "")
        return items

    async def _build_call_log_summary(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        """
        聚合 per-conversation call log stats / Aggregate per-conversation call log stats.
        """
        stmt = select(
            func.count(AICallLog.id).label("call_count"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.max(AICallLog.created_at).label("last_call_at"),
        ).where(
            AICallLog.tenant_id == self._get_memory_tenant_id(),
            AICallLog.conversation_id == conversation_id,
            AICallLog.is_deleted.is_(False),
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if not row or (row.call_count or 0) == 0:
            return None
        return {
            "call_count": row.call_count or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "last_call_at": row.last_call_at,
        }

    async def get_conversation_memory_state(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> dict[str, Any]:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        memory_svc = SessionMemoryService(self._get_memory_tenant_id())
        return await memory_svc.get_conversation_memory_state(conversation_id)

    async def clear_conversation_memory_state(
        self,
        conversation_id: int,
        user_id: int | None = None,
        owner_type: str | None = None,
    ) -> int:
        await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        memory_svc = SessionMemoryService(self._get_memory_tenant_id())
        return await memory_svc.clear_conversation_memory(conversation_id)

    # ========================================
    # 搜索 / Search
    # ========================================

    async def search_messages(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        跨对话全文搜索消息内容 / Full-text search messages across conversations.

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            搜索结果字典
        """
        if not keyword or not keyword.strip():
            raise BusinessException(
                message=_("conversation.search_keyword_required"),
            )

        skip = (page - 1) * page_size
        messages, total = await self.message_repo.search_by_content(
            keyword=keyword.strip(),
            skip=skip,
            limit=page_size,
        )

        items: list[dict[str, Any]] = []
        for msg in messages:
            msg_dict = msg.to_dict()
            runtime_meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            hydrated_attachments = await self._hydrate_chat_attachments(
                runtime_meta.get("attachments")
            )
            if runtime_meta or hydrated_attachments is not None:
                metadata_payload = dict(msg_dict.get("metadata") or {})
                metadata_payload.update(runtime_meta)
                if hydrated_attachments is not None:
                    metadata_payload["attachments"] = hydrated_attachments
                msg_dict["metadata"] = metadata_payload
            items.append(msg_dict)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ========================================
    # 归档 / Archive
    # ========================================

    async def archive_conversation(self, conversation_id: int) -> AgentConversation:
        """
        归档单个对话 / Archive single conversation.

        Args:
            conversation_id: 对话 ID

        Returns:
            更新后的 AgentConversation
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(message=_("conversation.not_found"))

        if conversation.status == ConversationStatusEnum.ARCHIVED.value:
            raise BusinessException(
                message=_("conversation.already_archived"),
            )

        updated = await self.repo.update(
            conversation_id,
            {
                "status": ConversationStatusEnum.ARCHIVED.value,
            },
        )

        # Proactively clear session memory (immediate cleanup beyond TTL) / 主动清理会话记忆（TTL 外的即时清理）
        memory_svc = SessionMemoryService(self._get_memory_tenant_id())
        try:
            await memory_svc.clear_conversation_memory(conversation_id)
        except Exception as exc:
            logger.warning(
                "Archive conversation memory cleanup failed: conversation={} tenant={} err={}",
                conversation_id,
                self.tenant_id,
                str(exc),
            )

        logger.info(
            "Conversation archived: conversation_id={} tenant_id={}",
            conversation_id,
            self.tenant_id,
        )

        return updated

    async def _after_delete(self, id: int) -> None:
        """
        对话删除后清理会话记忆（失败降级，不影响删除主流程）/ Clear session memory after delete (best-effort, does not block delete).
        """
        await super()._after_delete(id)
        memory_svc = SessionMemoryService(self._get_memory_tenant_id())
        try:
            await memory_svc.clear_conversation_memory(id)
        except Exception as exc:
            logger.warning(
                "Delete conversation memory cleanup failed: conversation={} tenant={} err={}",
                id,
                self.tenant_id,
                str(exc),
            )

    # ========================================
    # 导出 / Export
    # ========================================

    async def export_conversation(
        self,
        conversation_id: int,
        export_format: str = "json",
    ) -> dict[str, Any]:
        """
        导出对话数据 / Export conversation data.

        使用分批加载获取全部消息，避免静默截断。

        Args:
            conversation_id: 对话 ID
            export_format: 导出格式 (json / markdown)

        Returns:
            包含 content、filename、total_message_count 的字典
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(message=_("conversation.not_found"))

        # 分批加载所有消息 / Load all messages in batches
        messages: list = []
        batch_size = 1000
        skip = 0
        while True:
            batch = await self.message_repo.get_by_conversation(
                conversation_id=conversation_id,
                skip=skip,
                limit=batch_size,
            )
            messages.extend(batch)
            if len(batch) < batch_size:
                break
            skip += batch_size

        total_message_count = await self.message_repo.count_by_conversation(
            conversation_id,
        )

        title = conversation.title or f"conversation_{conversation_id}"

        def _safe_attr(obj: Any, key: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if hasattr(obj, "__dict__") and key in vars(obj):
                return vars(obj).get(key, default)
            value = getattr(obj, key, default)
            return default if isinstance(value, Mock) else value

        serialized_messages = []
        for msg in messages:
            metadata_payload = (
                dict(_safe_attr(msg, "metadata_"))
                if isinstance(_safe_attr(msg, "metadata_"), dict)
                else None
            )
            hydrated_attachments = await self._hydrate_chat_attachments(
                metadata_payload.get("attachments") if metadata_payload else None
            )
            if hydrated_attachments is not None:
                metadata_payload = metadata_payload or {}
                metadata_payload["attachments"] = hydrated_attachments
            agent_obj = _safe_attr(msg, "agent")
            serialized_messages.append(
                {
                    "role": _safe_attr(msg, "role"),
                    "content": _safe_attr(msg, "content"),
                    "token_count": _safe_attr(msg, "token_count"),
                    "tool_calls": _safe_attr(msg, "tool_calls"),
                    "tool_call_id": _safe_attr(msg, "tool_call_id"),
                    "tool_name": _safe_attr(msg, "tool_name"),
                    "agent_id": _safe_attr(msg, "agent_id"),
                    "agent_name": _safe_attr(agent_obj, "name"),
                    "agent_avatar": _safe_attr(agent_obj, "avatar"),
                    "created_at": ConversationService._format_dt(
                        _safe_attr(msg, "created_at")
                    ),
                    "metadata": metadata_payload,
                }
            )

        if export_format == "markdown":
            content = self._to_markdown(conversation, serialized_messages)
            filename = f"{title}.md"
        else:
            content = self._to_json(conversation, serialized_messages)
            filename = f"{title}.json"

        return {
            "content": content,
            "filename": filename,
            "format": export_format,
            "total_message_count": total_message_count,
        }

    @staticmethod
    def _to_json(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        """将对话转换为 JSON 字符串 / Convert conversation to JSON string."""

        def _msg_get(message: Any, key: str, default: Any = None) -> Any:
            if isinstance(message, dict):
                return message.get(key, default)
            if hasattr(message, "__dict__") and key in vars(message):
                return vars(message).get(key, default)
            value = getattr(message, key, default)
            return default if isinstance(value, Mock) else value

        def _related_attr(message: Any, relation: str, key: str) -> Any:
            if isinstance(message, dict):
                return None
            relation_obj = _msg_get(message, relation)
            if relation_obj is None:
                return None
            if hasattr(relation_obj, "__dict__") and key in vars(relation_obj):
                return vars(relation_obj).get(key)
            value = getattr(relation_obj, key, None)
            return None if isinstance(value, Mock) else value

        data = {
            "id": conversation.id,
            "title": conversation.title,
            "status": conversation.status,
            "token_count": conversation.token_count,
            "created_at": ConversationService._format_dt(conversation.created_at),
            "messages": [
                {
                    "role": _msg_get(msg, "role"),
                    "content": _msg_get(msg, "content"),
                    "token_count": _msg_get(msg, "token_count"),
                    "tool_calls": _msg_get(msg, "tool_calls"),
                    "tool_call_id": _msg_get(msg, "tool_call_id"),
                    "agent_id": _msg_get(msg, "agent_id"),
                    "agent_name": _msg_get(
                        msg,
                        "agent_name",
                        _related_attr(msg, "agent", "name"),
                    ),
                    "agent_avatar": _msg_get(
                        msg,
                        "agent_avatar",
                        _related_attr(msg, "agent", "avatar"),
                    ),
                    "created_at": _msg_get(
                        msg,
                        "created_at",
                        ConversationService._format_dt(_msg_get(msg, "created_at")),
                    ),
                    "metadata": _msg_get(
                        msg,
                        "metadata",
                        _msg_get(msg, "metadata_"),
                    ),
                }
                for msg in messages
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def _to_markdown(
        conversation: AgentConversation,
        messages: list,
    ) -> str:
        """将对话转换为 Markdown 字符串 / Convert conversation to Markdown string."""

        def _msg_get(message: Any, key: str, default: Any = None) -> Any:
            if isinstance(message, dict):
                return message.get(key, default)
            if hasattr(message, "__dict__") and key in vars(message):
                return vars(message).get(key, default)
            value = getattr(message, key, default)
            return default if isinstance(value, Mock) else value

        def _related_attr(message: Any, relation: str, key: str) -> Any:
            if isinstance(message, dict):
                return None
            relation_obj = _msg_get(message, relation)
            if relation_obj is None:
                return None
            if hasattr(relation_obj, "__dict__") and key in vars(relation_obj):
                return vars(relation_obj).get(key)
            value = getattr(relation_obj, key, None)
            return None if isinstance(value, Mock) else value

        role_labels = {
            MessageRoleEnum.SYSTEM.value: _("conversation.export.role.system"),
            MessageRoleEnum.USER.value: _("conversation.export.role.user"),
            MessageRoleEnum.ASSISTANT.value: _("conversation.export.role.assistant"),
            MessageRoleEnum.TOOL.value: _("conversation.export.role.tool"),
        }

        title = conversation.title or f"Conversation #{conversation.id}"
        lines = [f"# {title}", ""]

        for msg in messages:
            role = _msg_get(msg, "role", "")
            label = role_labels.get(role, role)
            agent_name = _msg_get(
                msg,
                "agent_name",
                _related_attr(msg, "agent", "name"),
            )
            if agent_name:
                lines.append(f"## {label} ({agent_name})")
            elif _msg_get(msg, "agent_id"):
                lines.append(f"## {label} (#{_msg_get(msg, 'agent_id')})")
            else:
                lines.append(f"## {label}")
            lines.append("")
            lines.append(_msg_get(msg, "content") or "")
            lines.append("")

            # 工具调用信息 / Tool-call info
            tool_calls = _msg_get(msg, "tool_calls")
            if tool_calls:
                lines.append("**Tool Calls:**")
                lines.append(
                    f"```json\n{json.dumps(tool_calls, indent=2, ensure_ascii=False)}\n```"
                )
                lines.append("")

            metadata = _msg_get(msg, "metadata", _msg_get(msg, "metadata_"))
            attachments = (
                metadata.get("attachments") if isinstance(metadata, dict) else None
            )
            if isinstance(attachments, list) and attachments:
                lines.append("**Attachments:**")
                for item in attachments:
                    if not isinstance(item, dict):
                        continue
                    att_type = str(item.get("type") or "file")
                    name = str(item.get("name") or item.get("url") or "-")
                    attachment_id = item.get("attachment_id")
                    url = str(item.get("url") or "").strip()
                    suffix = f" (#{attachment_id})" if attachment_id else ""
                    if url:
                        lines.append(f"- `{att_type}` {name}{suffix} `{url}`")
                    else:
                        lines.append(f"- `{att_type}` {name}{suffix}")
                lines.append("")

        return "\n".join(lines)

    # ========================================
    # Chat execution helpers (from AgentChatService) / 对话执行辅助（从 AgentChatService 提取）
    # ========================================

    # Max history messages to load (fallback default) / 历史消息最大条数（兜底默认）
    MAX_HISTORY_MESSAGES = 50
    # Max history tokens (0 = unlimited) / 历史消息最大 Token（0=不限制）
    MAX_HISTORY_TOKENS = 0
    # 对话标题最大长度 / Max conversation title length
    MAX_TITLE_LENGTH = 100

    async def get_or_create_for_chat(
        self,
        agent_id: int,
        conversation_id: int | None,
        user_id: int | None,
        owner_type: str,
        first_message: str,
    ) -> AgentConversation:
        """
        获取或创建对话（用于对话执行）/ Get or create conversation (for chat execution).

        Args:
            agent_id: 智能体 ID
            conversation_id: 已有对话 ID（续接时传入）
            user_id: 用户 ID
            first_message: 首条消息（用于生成标题）

        Returns:
            AgentConversation 实例

        Raises:
            NotFoundException: 对话不存在
            BusinessException: 对话已归档
        """
        if conversation_id:
            # 续接已有对话 / Resume existing conversation
            conversation = await self.get_accessible_conversation(
                conversation_id,
                user_id=(user_id if self.tenant_id != PLATFORM_TENANT_ID else None),
                owner_type=owner_type,
            )

            if conversation.status == ConversationStatusEnum.ARCHIVED.value:
                raise BusinessException(
                    message=_("agent_chat.error.conversation_archived"),
                )

            if conversation.agent_id != agent_id:
                raise BusinessException(
                    message=_("agent_chat.error.conversation_agent_mismatch"),
                )

            return conversation

        # 创建新对话 / Create new conversation
        title = first_message[: self.MAX_TITLE_LENGTH].strip()
        conversation = await self.repo.create(
            {
                "tenant_id": self.tenant_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "owner_type": owner_type,
                "title": title,
                "status": ConversationStatusEnum.ACTIVE.value,
                "token_count": 0,
                "cost": 0,
            }
        )

        logger.info(
            f"Conversation created: id={conversation.id} agent={agent_id} tenant={self.tenant_id}"
        )

        return conversation

    async def load_chat_history(
        self,
        conversation_id: int,
        max_messages: int = 0,
        max_tokens: int = 0,
    ) -> list[ChatMessage]:
        """
        从 ConversationMessage 加载历史消息并转换为 ChatMessage / Load history from ConversationMessage and convert to ChatMessage.

        支持两级截断：
        1. max_messages: 最多保留最近 N 条消息
        2. max_tokens: 历史消息总 token 不超过 N（从最旧开始移除）

        Args:
            conversation_id: 对话 ID
            max_messages: 最大消息条数（0 = 使用默认值）
            max_tokens: 最大 token 数（0 = 不限制）

        Returns:
            ChatMessage 列表（不含 system 消息，由引擎构建）
        """
        effective_limit = (
            max_messages if max_messages > 0 else self.MAX_HISTORY_MESSAGES
        )
        db_messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=effective_limit,
        )

        chat_messages: list[ChatMessage] = []
        for msg in db_messages:
            # Skip system messages (rebuilt by engine) / 跳过 system（由引擎重建）
            if msg.role == MessageRoleEnum.SYSTEM.value:
                continue

            # Restore attachments from metadata (multimodal history) / 从 metadata 恢复附件（多模态历史）
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
                # Tool-round thinking is in metadata; do not replay as assistant content / 工具轮思考在 metadata，勿当 assistant 正文回灌
                msg_content = ""

            chat_messages.append(
                ChatMessage(
                    role=msg.role,
                    content=msg_content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    attachments=msg_attachments,
                    reasoning_content=msg_reasoning_content,
                    metadata=self._copy_metadata(msg.metadata_),
                ),
            )

        # Token budget: remove oldest until under max_tokens / Token 截断：从最旧消息删起直至不超上限
        if max_tokens > 0 and chat_messages:
            total = sum(estimate_tokens(m.content or "") for m in chat_messages)
            while total > max_tokens and len(chat_messages) > 1:
                removed = chat_messages.pop(0)
                total -= estimate_tokens(removed.content or "")

        # Drop orphan tool messages (no matching assistant tool_calls) / 清理孤立 tool 消息
        chat_messages = self.sanitize_tool_messages(chat_messages)

        return chat_messages

    @staticmethod
    def sanitize_tool_messages(
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        """按 assistant-tool round 原子保留/丢弃，禁止半截 tool_calls 混入历史。

        Atomic round rule: keep assistant(tool_calls) only if ALL its tool_call_ids
        have matching tool replies; otherwise drop the entire round (assistant + associated tools).
        Orphan tool messages (no preceding assistant round) are dropped.
        """
        if not messages:
            return messages

        result: list[ChatMessage] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.role == "tool":
                # Orphan tool: drop (no matching assistant round) / 孤立工具轮次丢弃 / drop orphan tool round
                i += 1
                continue
            if msg.role != "assistant" or not msg.tool_calls:
                result.append(msg)
                i += 1
                continue

            tc_ids_expected = {
                tc.get("id", "") for tc in msg.tool_calls if tc.get("id")
            }
            if not tc_ids_expected:
                result.append(msg)
                i += 1
                continue

            collected_tool_ids: set[str] = set()
            round_msgs: list[ChatMessage] = [msg]
            j = i + 1
            while j < len(messages):
                next_msg = messages[j]
                if next_msg.role == "tool" and next_msg.tool_call_id:
                    if next_msg.tool_call_id in tc_ids_expected:
                        collected_tool_ids.add(next_msg.tool_call_id)
                        round_msgs.append(next_msg)
                    j += 1
                    continue
                if next_msg.role in ("assistant", "user", "system"):
                    break
                j += 1

            if collected_tool_ids == tc_ids_expected:
                result.extend(round_msgs)
            i = j

        return result

    @staticmethod
    def _copy_metadata(raw: Any) -> dict[str, Any] | None:
        return ConversationService._normalize_json_safe_dict(raw)

    @staticmethod
    def _normalize_json_safe(value: Any) -> Any:
        return normalize_json_safe(value)

    @staticmethod
    def _normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
        return normalize_json_safe_dict(raw)

    @staticmethod
    def _normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
        """Normalize runtime turn_record into JSON-safe dict / 将运行时 turn_record 规范化为可落库字典。"""
        return ConversationService._normalize_json_safe_dict(turn_record)

    @staticmethod
    def _to_non_empty_str(value: Any) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.lower() in {"none", "null", "undefined"}:
            return None
        return text

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _normalize_context_sources(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            source_name = ConversationService._to_non_empty_str(item.get("name"))
            source_kind = ConversationService._to_non_empty_str(item.get("kind"))
            if not source_name and not source_kind:
                continue
            normalized.append(
                {
                    "kind": source_kind,
                    "name": source_name,
                    "active": bool(item.get("active", True)),
                    "metadata": dict(item.get("metadata") or {}),
                }
            )
        return normalized

    @staticmethod
    def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {
            str(key): value[key]
            for key in value
            if isinstance(key, str) or key is not None
        }

    @classmethod
    def _normalize_intent_plan(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            payload = cls._normalize_json_dict(item)
            if not payload:
                continue
            normalized.append(
                {
                    "intent_id": cls._to_non_empty_str(payload.get("intent_id")),
                    "kind": cls._to_non_empty_str(payload.get("kind")),
                    "family": cls._to_non_empty_str(payload.get("family")),
                    "order": int(payload.get("order") or 0) or None,
                    "user_visible_label": cls._to_non_empty_str(
                        payload.get("user_visible_label")
                    ),
                    "status": cls._to_non_empty_str(payload.get("status")),
                    "allowed_tool_names": cls._normalize_string_list(
                        payload.get("allowed_tool_names")
                    ),
                    "completed_by_tool_names": cls._normalize_string_list(
                        payload.get("completed_by_tool_names")
                    ),
                    "failure_reason": cls._to_non_empty_str(
                        payload.get("failure_reason")
                    ),
                }
            )
        return normalized

    @classmethod
    def _normalize_retry_events(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            payload = cls._normalize_json_dict(item)
            if not payload:
                continue
            normalized.append(
                {
                    "action": cls._to_non_empty_str(payload.get("action")),
                    "target_intent_id": cls._to_non_empty_str(
                        payload.get("target_intent_id")
                    ),
                    "retry_family": cls._to_non_empty_str(payload.get("retry_family")),
                    "allowed_tool_names": cls._normalize_string_list(
                        payload.get("allowed_tool_names")
                    ),
                    "completed_intent_ids": cls._normalize_string_list(
                        payload.get("completed_intent_ids")
                    ),
                    "unfinished_intent_ids": cls._normalize_string_list(
                        payload.get("unfinished_intent_ids")
                    ),
                    "reason": cls._to_non_empty_str(payload.get("reason")),
                    "provider_failure_kind": cls._to_non_empty_str(
                        payload.get("provider_failure_kind")
                    ),
                    "metadata": dict(payload.get("metadata") or {}),
                }
            )
        return normalized

    @classmethod
    def _normalize_provider_events(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            payload = cls._normalize_json_dict(item)
            if not payload:
                continue
            normalized.append(dict(payload))
        return normalized

    @classmethod
    def _extract_turn_diagnostics_from_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        turn_record = cls._normalize_turn_record_payload(metadata.get("turn_record"))
        turn_record_metadata = (
            dict((turn_record or {}).get("metadata") or {})
            if isinstance((turn_record or {}).get("metadata"), dict)
            else {}
        )
        turn_record_diagnostics = (
            dict(turn_record_metadata.get("turn_diagnostics") or {})
            if isinstance(turn_record_metadata.get("turn_diagnostics"), dict)
            else {}
        )
        context_diagnostics = (
            dict(metadata.get("context_diagnostics") or {})
            if isinstance(metadata.get("context_diagnostics"), dict)
            else {}
        )
        last_run_summary = (
            dict(metadata.get("last_run_summary") or {})
            if isinstance(metadata.get("last_run_summary"), dict)
            else {}
        )
        turn_outcome = cls._to_non_empty_str(
            (turn_record or {}).get("turn_outcome")
            or metadata.get("turn_outcome")
            or turn_record_diagnostics.get("turn_outcome")
            or context_diagnostics.get("turn_outcome")
            or last_run_summary.get("turn_outcome")
        )
        termination_reason = cls._to_non_empty_str(
            (turn_record or {}).get("termination_reason")
            or metadata.get("termination_reason")
            or metadata.get("completion_reason")
            or turn_record_diagnostics.get("termination_reason")
            or context_diagnostics.get("termination_reason")
            or last_run_summary.get("termination_reason")
            or last_run_summary.get("completion_reason")
        )
        if not turn_outcome:
            if (
                bool(metadata.get("partial"))
                or bool(metadata.get("interrupted"))
                or termination_reason == "interrupted"
            ):
                turn_outcome = "partial"
            elif termination_reason in {
                "error",
                "failed",
                "tool_error",
                "tool_round_failed",
            }:
                turn_outcome = "failed"
        protocol_path = cls._to_non_empty_str(
            (turn_record or {}).get("protocol_path")
            or metadata.get("protocol_path")
            or turn_record_diagnostics.get("protocol_path")
            or context_diagnostics.get("protocol_path")
            or last_run_summary.get("protocol_path")
        )
        selected_tool_names = cls._normalize_string_list(
            (turn_record or {}).get("selected_tool_names")
            or metadata.get("selected_tool_names")
            or turn_record_diagnostics.get("selected_tool_names")
            or context_diagnostics.get("selected_tool_names")
            or last_run_summary.get("selected_tool_names")
        )
        selected_skill_names = cls._normalize_string_list(
            (turn_record or {}).get("selected_skill_names")
            or metadata.get("selected_skill_names")
            or turn_record_diagnostics.get("selected_skill_names")
            or context_diagnostics.get("selected_skill_names")
            or last_run_summary.get("selected_skill_names")
        )
        context_sources = cls._normalize_context_sources(
            (turn_record or {}).get("context_sources")
            or metadata.get("context_sources")
            or turn_record_diagnostics.get("context_sources")
            or context_diagnostics.get("context_sources")
            or last_run_summary.get("context_sources")
        )
        contract_breach_type = cls._to_non_empty_str(
            turn_record_metadata.get("contract_breach_type")
            or metadata.get("contract_breach_type")
            or turn_record_diagnostics.get("contract_breach_type")
            or context_diagnostics.get("contract_breach_type")
            or last_run_summary.get("contract_breach_type")
        )
        tool_planner = cls._normalize_json_dict(
            (turn_record or {}).get("tool_planner")
            or metadata.get("tool_planner")
            or turn_record_diagnostics.get("tool_planner")
            or context_diagnostics.get("tool_planner")
            or last_run_summary.get("tool_planner")
        )
        tool_leak_detected = bool(
            turn_record_metadata.get("tool_leak_detected")
            or metadata.get("tool_leak_detected")
            or turn_record_diagnostics.get("tool_leak_detected")
            or context_diagnostics.get("tool_leak_detected")
            or last_run_summary.get("tool_leak_detected")
        )
        assistant_claimed_tool_call_without_tool_event = bool(
            turn_record_metadata.get("assistant_claimed_tool_call_without_tool_event")
            or (turn_record or {}).get(
                "assistant_claimed_tool_call_without_tool_event"
            )
            or metadata.get("assistant_claimed_tool_call_without_tool_event")
            or turn_record_diagnostics.get(
                "assistant_claimed_tool_call_without_tool_event"
            )
            or context_diagnostics.get(
                "assistant_claimed_tool_call_without_tool_event"
            )
            or last_run_summary.get(
                "assistant_claimed_tool_call_without_tool_event"
            )
        )
        unfinished_intents = cls._normalize_string_list(
            turn_record_metadata.get("unfinished_intents")
            or metadata.get("unfinished_intents")
            or turn_record_diagnostics.get("unfinished_intents")
            or context_diagnostics.get("unfinished_intents")
            or last_run_summary.get("unfinished_intents")
        )
        leaked_tool_names = cls._normalize_string_list(
            turn_record_metadata.get("leaked_tool_names")
            or metadata.get("leaked_tool_names")
            or turn_record_diagnostics.get("leaked_tool_names")
            or context_diagnostics.get("leaked_tool_names")
            or last_run_summary.get("leaked_tool_names")
        )
        recovered_via_retry_raw = (
            turn_record_metadata.get("recovered_via_retry")
            if "recovered_via_retry" in turn_record_metadata
            else (
                metadata.get("recovered_via_retry")
                if "recovered_via_retry" in metadata
                else (
                    turn_record_diagnostics.get("recovered_via_retry")
                    if "recovered_via_retry" in turn_record_diagnostics
                    else (
                        context_diagnostics.get("recovered_via_retry")
                        if "recovered_via_retry" in context_diagnostics
                        else last_run_summary.get("recovered_via_retry")
                    )
                )
            )
        )
        recovered_via_retry = (
            bool(recovered_via_retry_raw)
            if recovered_via_retry_raw is not None
            else None
        )
        last_tool_name = cls._to_non_empty_str(
            (turn_record or {}).get("last_tool_name")
            or metadata.get("last_tool_name")
            or turn_record_diagnostics.get("last_tool_name")
            or context_diagnostics.get("last_tool_name")
            or last_run_summary.get("last_tool_name")
        )
        last_page_key = cls._to_non_empty_str(
            (turn_record or {}).get("last_page_key")
            or metadata.get("last_page_key")
            or turn_record_diagnostics.get("last_page_key")
            or context_diagnostics.get("last_page_key")
            or last_run_summary.get("last_page_key")
        )
        last_page_op = cls._to_non_empty_str(
            (turn_record or {}).get("last_page_op")
            or metadata.get("last_page_op")
            or turn_record_diagnostics.get("last_page_op")
            or context_diagnostics.get("last_page_op")
            or last_run_summary.get("last_page_op")
        )
        interrupted_stage = cls._to_non_empty_str(
            (turn_record or {}).get("interrupted_stage")
            or metadata.get("interrupted_stage")
            or turn_record_diagnostics.get("interrupted_stage")
            or context_diagnostics.get("interrupted_stage")
            or last_run_summary.get("interrupted_stage")
        )
        tool_loop_progress = (
            dict((turn_record or {}).get("tool_loop_progress") or {})
            if isinstance((turn_record or {}).get("tool_loop_progress"), dict)
            else (
                dict(turn_record_diagnostics.get("tool_loop_progress") or {})
                if isinstance(turn_record_diagnostics.get("tool_loop_progress"), dict)
                else {}
            )
        )
        if not tool_loop_progress and isinstance(
            metadata.get("tool_loop_progress"), dict
        ):
            tool_loop_progress = dict(metadata.get("tool_loop_progress") or {})
        if not tool_loop_progress and isinstance(
            context_diagnostics.get("tool_loop_progress"), dict
        ):
            tool_loop_progress = dict(
                context_diagnostics.get("tool_loop_progress") or {}
            )
        if not tool_loop_progress and isinstance(
            last_run_summary.get("tool_loop_progress"), dict
        ):
            tool_loop_progress = dict(last_run_summary.get("tool_loop_progress") or {})

        execution_path = cls._to_non_empty_str(
            (turn_record or {}).get("execution_path")
            or metadata.get("execution_path")
            or turn_record_diagnostics.get("execution_path")
            or context_diagnostics.get("execution_path")
            or last_run_summary.get("execution_path")
        )
        active_intent_id = cls._to_non_empty_str(
            (turn_record or {}).get("active_intent_id")
            or metadata.get("active_intent_id")
            or turn_record_diagnostics.get("active_intent_id")
            or context_diagnostics.get("active_intent_id")
            or last_run_summary.get("active_intent_id")
        )
        continuation_source = cls._to_non_empty_str(
            (turn_record or {}).get("continuation_source")
            or metadata.get("continuation_source")
            or turn_record_diagnostics.get("continuation_source")
            or context_diagnostics.get("continuation_source")
            or last_run_summary.get("continuation_source")
        )
        conversation_outcome = cls._to_non_empty_str(
            (turn_record or {}).get("conversation_outcome")
            or metadata.get("conversation_outcome")
            or turn_record_diagnostics.get("conversation_outcome")
            or context_diagnostics.get("conversation_outcome")
            or last_run_summary.get("conversation_outcome")
            or turn_outcome
        )
        intent_plan = cls._normalize_intent_plan(
            (turn_record or {}).get("intent_plan")
            or metadata.get("intent_plan")
            or turn_record_diagnostics.get("intent_plan")
            or context_diagnostics.get("intent_plan")
            or last_run_summary.get("intent_plan")
        )
        budget = cls._normalize_json_dict(
            (turn_record or {}).get("budget")
            or metadata.get("budget")
            or turn_record_diagnostics.get("budget")
            or context_diagnostics.get("budget")
            or last_run_summary.get("budget")
        )
        routing = (
            cls._normalize_json_dict(
                metadata.get("routing")
                or turn_record_diagnostics.get("routing")
                or context_diagnostics.get("routing")
                or last_run_summary.get("routing")
            )
            or {}
        )
        candidate_tool_names = cls._normalize_string_list(
            routing.get("candidate_tool_names")
            or metadata.get("candidate_tool_names")
            or turn_record_diagnostics.get("candidate_tool_names")
            or context_diagnostics.get("candidate_tool_names")
            or last_run_summary.get("candidate_tool_names")
        )
        recovery = (
            cls._normalize_json_dict(
                metadata.get("recovery")
                or turn_record_diagnostics.get("recovery")
                or context_diagnostics.get("recovery")
                or last_run_summary.get("recovery")
            )
            or {}
        )
        retry_events = cls._normalize_retry_events(
            recovery.get("retry_events")
            or metadata.get("retry_events")
            or turn_record_diagnostics.get("retry_events")
            or context_diagnostics.get("retry_events")
            or last_run_summary.get("retry_events")
        )
        partial_exit_reason = cls._to_non_empty_str(
            recovery.get("partial_exit_reason")
            or metadata.get("partial_exit_reason")
            or turn_record_diagnostics.get("partial_exit_reason")
            or context_diagnostics.get("partial_exit_reason")
            or last_run_summary.get("partial_exit_reason")
        )
        failure_kind = cls._to_non_empty_str(
            metadata.get("failure_kind")
            or turn_record_diagnostics.get("failure_kind")
            or (cls._normalize_json_dict(metadata.get("failures")) or {}).get(
                "failure_kind"
            )
            or (
                cls._normalize_json_dict(turn_record_diagnostics.get("failures")) or {}
            ).get("failure_kind")
            or context_diagnostics.get("failure_kind")
            or last_run_summary.get("failure_kind")
        )
        provider_events = cls._normalize_provider_events(
            metadata.get("provider_events")
            or (cls._normalize_json_dict(metadata.get("failures")) or {}).get(
                "provider_events"
            )
            or turn_record_diagnostics.get("provider_events")
            or (
                cls._normalize_json_dict(turn_record_diagnostics.get("failures")) or {}
            ).get("provider_events")
            or context_diagnostics.get("provider_events")
            or last_run_summary.get("provider_events")
        )
        sync_rescue_raw = (
            turn_record_metadata.get("sync_rescue")
            if "sync_rescue" in turn_record_metadata
            else (
                metadata.get("sync_rescue")
                if "sync_rescue" in metadata
                else (
                    turn_record_diagnostics.get("sync_rescue")
                    if "sync_rescue" in turn_record_diagnostics
                    else (
                        context_diagnostics.get("sync_rescue")
                        if "sync_rescue" in context_diagnostics
                        else last_run_summary.get("sync_rescue")
                    )
                )
            )
        )
        sync_rescue = bool(sync_rescue_raw) if sync_rescue_raw is not None else None
        should_record_call_log_raw = (
            turn_record_metadata.get("should_record_call_log")
            if "should_record_call_log" in turn_record_metadata
            else (
                metadata.get("should_record_call_log")
                if "should_record_call_log" in metadata
                else (
                    turn_record_diagnostics.get("should_record_call_log")
                    if "should_record_call_log" in turn_record_diagnostics
                    else (
                        context_diagnostics.get("should_record_call_log")
                        if "should_record_call_log" in context_diagnostics
                        else last_run_summary.get("should_record_call_log")
                    )
                )
            )
        )
        should_record_call_log = (
            bool(should_record_call_log_raw)
            if should_record_call_log_raw is not None
            else None
        )
        budget_status = cls._to_non_empty_str(
            (budget or {}).get("status")
            or metadata.get("budget_status")
            or context_diagnostics.get("budget_status")
            or last_run_summary.get("budget_status")
        )
        budget_exit_reason = cls._to_non_empty_str(
            (budget or {}).get("exit_reason")
            or metadata.get("budget_exit_reason")
            or context_diagnostics.get("budget_exit_reason")
            or last_run_summary.get("budget_exit_reason")
        )
        return {
            "turn_record": turn_record,
            "turn_outcome": turn_outcome,
            "termination_reason": termination_reason,
            "protocol_path": protocol_path,
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "context_sources": context_sources,
            "tool_planner": tool_planner,
            "contract_breach_type": contract_breach_type,
            "tool_leak_detected": tool_leak_detected,
            "assistant_claimed_tool_call_without_tool_event": (
                assistant_claimed_tool_call_without_tool_event
            ),
            "unfinished_intents": unfinished_intents,
            "leaked_tool_names": leaked_tool_names,
            "recovered_via_retry": recovered_via_retry,
            "execution_path": execution_path,
            "active_intent_id": active_intent_id,
            "continuation_source": continuation_source,
            "conversation_outcome": conversation_outcome,
            "intent_plan": intent_plan,
            "budget": budget,
            "budget_status": budget_status,
            "budget_exit_reason": budget_exit_reason,
            "candidate_tool_names": candidate_tool_names,
            "retry_events": retry_events,
            "partial_exit_reason": partial_exit_reason,
            "failure_kind": failure_kind,
            "provider_events": provider_events,
            "last_tool_name": last_tool_name,
            "last_page_key": last_page_key,
            "last_page_op": last_page_op,
            "interrupted_stage": interrupted_stage,
            "tool_loop_progress": tool_loop_progress,
            "sync_rescue": sync_rescue,
            "should_record_call_log": should_record_call_log,
        }

    @classmethod
    def _has_pending_state(
        cls,
        *,
        tool_calls: list[dict[str, Any]] | None,
        metadata: dict[str, Any] | None,
    ) -> bool:
        if isinstance(metadata, dict) and (
            isinstance(metadata.get("pending_confirmation"), dict)
            or isinstance(metadata.get("pending_consent"), dict)
        ):
            return True

        for tc in tool_calls or []:
            if not isinstance(tc, dict):
                continue
            if isinstance(tc.get("pending_confirmation"), dict) or isinstance(
                tc.get("pending_consent"),
                dict,
            ):
                return True
        return False

    @classmethod
    def _assistant_has_content_or_signal(
        cls,
        message: dict[str, Any],
    ) -> bool:
        content = str(message.get("content") or "").strip()
        tool_calls = message.get("tool_calls")
        metadata = (
            dict(message.get("metadata") or {})
            if isinstance(message.get("metadata"), dict)
            else None
        )
        if content:
            return True
        if isinstance(tool_calls, list) and tool_calls:
            return True
        if cls._has_pending_state(tool_calls=tool_calls, metadata=metadata):
            return True
        if isinstance(metadata, dict) and isinstance(
            metadata.get("action_buttons"), list
        ):
            return len(metadata.get("action_buttons") or []) > 0
        return False

    @staticmethod
    def _enrich_tool_calls_for_persistence(
        tool_calls: list[dict[str, Any]] | None,
        tool_result_map: dict[str, ToolResult],
    ) -> list[dict[str, Any]] | None:
        if not tool_calls:
            return tool_calls

        enriched: list[dict[str, Any]] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue

            next_tc = dict(tc)
            tc_id = str(next_tc.get("id") or "")
            tr = tool_result_map.get(tc_id) if tc_id else None
            if tr:
                if tr.display_name and not next_tc.get("display_name"):
                    next_tc["display_name"] = tr.display_name
                if tr.summary and not next_tc.get("summary"):
                    next_tc["summary"] = tr.summary
                if tr.summary_payload:
                    existing_payload = (
                        next_tc.get("summary_payload")
                        if isinstance(next_tc.get("summary_payload"), dict)
                        else {}
                    )
                    next_tc["summary_payload"] = {
                        **existing_payload,
                        **tr.summary_payload,
                    }
                if tr.result_link and not next_tc.get("result_link"):
                    next_tc["result_link"] = tr.result_link
                if tr.error_type and not next_tc.get("error_type"):
                    next_tc["error_type"] = tr.error_type
                if tr.duration_ms and not next_tc.get("duration_ms"):
                    next_tc["duration_ms"] = tr.duration_ms
                next_tc["success"] = tr.success

            enriched.append(next_tc)

        return enriched

    async def persist_chat_messages(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        history_count: int,
        agent_id: int | None = None,
        route_source: str | None = None,
        *,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        将执行过程中产生的新消息持久化为 ConversationMessage / Persist new messages from execution as ConversationMessage.

        ExecutionResult.messages 结构:
        [system, ...history..., new_user, (assistant+tool_calls, tool, ...,)* final_assistant]

        持久化 new_user 及之后的所有消息（跳过 system 和 history）。

        Args:
            conversation: 对话实例
            result: 执行结果
            history_count: 历史消息数量（用于计算新消息起始位置）
            agent_id: 智能体 ID（写入 assistant/tool 消息，支持多智能体对话追溯）
            route_source: 前端路由来源标记（如 mention）

        Returns:
            收集到的 tool_calls 与实际持久化的消息数量（用于响应和错误兜底判断）
            / Collected tool_calls plus the number of messages actually persisted.
        """
        # Count leading system messages dynamically (not hard-coded as 1) / 动态统计前缀 system 条数
        system_count = 0
        for msg_dict in result.messages:
            if msg_dict.get("role") == "system":
                system_count += 1
            else:
                break
        new_start = system_count + history_count
        new_messages_raw = result.messages[new_start:]

        if not new_messages_raw:
            return [], 0

        # Sanitize: persist complete tool rounds only; drop orphan tool_calls / 仅持久化完整 tool 轮，丢弃孤立 tool_calls
        chat_msgs = [
            ChatMessage(
                role=m.get("role", ""),
                content=m.get("content", "") or "",
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
                attachments=m.get("attachments"),
                reasoning_content=m.get("reasoning_content"),
                metadata=self._copy_metadata(m.get("metadata")),
                internal_only=bool(m.get("internal_only", False)),
            )
            for m in new_messages_raw
        ]
        chat_msgs = self.sanitize_tool_messages(chat_msgs)
        new_messages = [
            {
                "role": m.role,
                "content": m.content or "",
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
                "attachments": m.attachments,
                "reasoning_content": m.reasoning_content,
                "metadata": self._copy_metadata(m.metadata),
            }
            for m in chat_msgs
            if not m.internal_only
        ]
        if not new_messages:
            return [], 0

        # tool_call_id -> ToolResult lookup / 构建 tool_call_id 到 ToolResult 映射
        tool_result_map: dict[str, ToolResult] = {}
        if result.tool_results:
            for tr in result.tool_results:
                if tr.tool_call_id:
                    tool_result_map[tr.tool_call_id] = tr

        # Next message sequence / 获取下一 message sequence
        next_seq = await self.message_repo.get_next_sequence(conversation.id)
        tool_calls_collected: list[dict[str, Any]] = []
        persisted_count = 0
        route_source_marked = False

        rag_sources = getattr(result, "rag_sources", None)
        turn_meta = self._extract_turn_diagnostics_from_metadata(
            {
                "turn_record": getattr(result, "turn_record", None),
                "completion_reason": getattr(result, "completion_reason", None),
                "partial": bool(getattr(result, "partial", False)),
                "interrupted": bool(getattr(result, "interrupted", False)),
            }
        )
        turn_record_payload = turn_meta.get("turn_record")
        turn_outcome = turn_meta.get("turn_outcome")
        turn_termination_reason = turn_meta.get("termination_reason")
        turn_protocol_path = turn_meta.get("protocol_path")
        turn_selected_tools = turn_meta.get("selected_tool_names") or []
        turn_selected_skills = turn_meta.get("selected_skill_names") or []
        turn_context_sources = turn_meta.get("context_sources") or []

        effective_context_diagnostics = (
            dict(context_diagnostics) if isinstance(context_diagnostics, dict) else {}
        )
        if turn_outcome:
            effective_context_diagnostics["turn_outcome"] = turn_outcome
        if turn_termination_reason:
            effective_context_diagnostics["termination_reason"] = (
                turn_termination_reason
            )
        if turn_protocol_path:
            effective_context_diagnostics["protocol_path"] = turn_protocol_path
        if turn_meta.get("tool_planner"):
            effective_context_diagnostics["tool_planner"] = turn_meta["tool_planner"]
        if turn_selected_tools:
            effective_context_diagnostics["selected_tool_names"] = turn_selected_tools
        if turn_selected_skills:
            effective_context_diagnostics["selected_skill_names"] = turn_selected_skills
        if turn_context_sources:
            effective_context_diagnostics["context_sources"] = turn_context_sources
        if turn_meta.get("execution_path"):
            effective_context_diagnostics["execution_path"] = turn_meta[
                "execution_path"
            ]
        if turn_meta.get("active_intent_id"):
            effective_context_diagnostics["active_intent_id"] = turn_meta[
                "active_intent_id"
            ]
        if turn_meta.get("continuation_source"):
            effective_context_diagnostics["continuation_source"] = turn_meta[
                "continuation_source"
            ]
        if turn_meta.get("conversation_outcome"):
            effective_context_diagnostics["conversation_outcome"] = turn_meta[
                "conversation_outcome"
            ]
        if turn_meta.get("intent_plan"):
            effective_context_diagnostics["intent_plan"] = turn_meta["intent_plan"]
        if turn_meta.get("budget"):
            effective_context_diagnostics["budget"] = turn_meta["budget"]
        if turn_meta.get("budget_status"):
            effective_context_diagnostics["budget_status"] = turn_meta["budget_status"]
        if turn_meta.get("budget_exit_reason"):
            effective_context_diagnostics["budget_exit_reason"] = turn_meta[
                "budget_exit_reason"
            ]
        if turn_meta.get("candidate_tool_names"):
            effective_context_diagnostics["candidate_tool_names"] = turn_meta[
                "candidate_tool_names"
            ]
        if turn_meta.get("retry_events"):
            effective_context_diagnostics["retry_events"] = turn_meta["retry_events"]
        if turn_meta.get("partial_exit_reason"):
            effective_context_diagnostics["partial_exit_reason"] = turn_meta[
                "partial_exit_reason"
            ]
        if turn_meta.get("failure_kind"):
            effective_context_diagnostics["failure_kind"] = turn_meta["failure_kind"]
        if turn_meta.get("provider_events"):
            effective_context_diagnostics["provider_events"] = turn_meta[
                "provider_events"
            ]
        if turn_meta.get("contract_breach_type"):
            effective_context_diagnostics["contract_breach_type"] = turn_meta[
                "contract_breach_type"
            ]
        if turn_meta.get("tool_leak_detected"):
            effective_context_diagnostics["tool_leak_detected"] = True
        if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
            effective_context_diagnostics[
                "assistant_claimed_tool_call_without_tool_event"
            ] = True
        if turn_meta.get("unfinished_intents"):
            effective_context_diagnostics["unfinished_intents"] = turn_meta[
                "unfinished_intents"
            ]
        if turn_meta.get("leaked_tool_names"):
            effective_context_diagnostics["leaked_tool_names"] = turn_meta[
                "leaked_tool_names"
            ]
        if turn_meta.get("recovered_via_retry") is not None:
            effective_context_diagnostics["recovered_via_retry"] = turn_meta[
                "recovered_via_retry"
            ]
        if turn_meta.get("last_tool_name"):
            effective_context_diagnostics["last_tool_name"] = turn_meta[
                "last_tool_name"
            ]
        if turn_meta.get("last_page_key"):
            effective_context_diagnostics["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            effective_context_diagnostics["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            effective_context_diagnostics["interrupted_stage"] = turn_meta[
                "interrupted_stage"
            ]
        if turn_meta.get("tool_loop_progress"):
            effective_context_diagnostics["tool_loop_progress"] = turn_meta[
                "tool_loop_progress"
            ]
        if turn_meta.get("sync_rescue") is not None:
            effective_context_diagnostics["sync_rescue"] = turn_meta["sync_rescue"]
        if turn_meta.get("should_record_call_log") is not None:
            effective_context_diagnostics["should_record_call_log"] = turn_meta[
                "should_record_call_log"
            ]
        effective_context_diagnostics.setdefault(
            "last_interrupted",
            bool(getattr(result, "interrupted", False))
            or turn_termination_reason == "interrupted",
        )

        effective_last_run_summary = (
            dict(last_run_summary) if isinstance(last_run_summary, dict) else {}
        )
        if turn_outcome:
            effective_last_run_summary["turn_outcome"] = turn_outcome
        if turn_termination_reason:
            effective_last_run_summary["termination_reason"] = turn_termination_reason
            effective_last_run_summary.setdefault(
                "completion_reason", turn_termination_reason
            )
        if turn_protocol_path:
            effective_last_run_summary["protocol_path"] = turn_protocol_path
        if turn_meta.get("tool_planner"):
            effective_last_run_summary["tool_planner"] = turn_meta["tool_planner"]
        if turn_selected_tools:
            effective_last_run_summary["selected_tool_names"] = turn_selected_tools
        if turn_selected_skills:
            effective_last_run_summary["selected_skill_names"] = turn_selected_skills
        if turn_context_sources:
            effective_last_run_summary["context_sources"] = turn_context_sources
        if turn_meta.get("execution_path"):
            effective_last_run_summary["execution_path"] = turn_meta["execution_path"]
        if turn_meta.get("active_intent_id"):
            effective_last_run_summary["active_intent_id"] = turn_meta[
                "active_intent_id"
            ]
        if turn_meta.get("continuation_source"):
            effective_last_run_summary["continuation_source"] = turn_meta[
                "continuation_source"
            ]
        if turn_meta.get("conversation_outcome"):
            effective_last_run_summary["conversation_outcome"] = turn_meta[
                "conversation_outcome"
            ]
        if turn_meta.get("intent_plan"):
            effective_last_run_summary["intent_plan"] = turn_meta["intent_plan"]
        if turn_meta.get("budget"):
            effective_last_run_summary["budget"] = turn_meta["budget"]
        if turn_meta.get("budget_status"):
            effective_last_run_summary["budget_status"] = turn_meta["budget_status"]
        if turn_meta.get("budget_exit_reason"):
            effective_last_run_summary["budget_exit_reason"] = turn_meta[
                "budget_exit_reason"
            ]
        if turn_meta.get("candidate_tool_names"):
            effective_last_run_summary["candidate_tool_names"] = turn_meta[
                "candidate_tool_names"
            ]
        if turn_meta.get("retry_events"):
            effective_last_run_summary["retry_events"] = turn_meta["retry_events"]
        if turn_meta.get("partial_exit_reason"):
            effective_last_run_summary["partial_exit_reason"] = turn_meta[
                "partial_exit_reason"
            ]
        if turn_meta.get("failure_kind"):
            effective_last_run_summary["failure_kind"] = turn_meta["failure_kind"]
        if turn_meta.get("provider_events"):
            effective_last_run_summary["provider_events"] = turn_meta["provider_events"]
        if turn_meta.get("contract_breach_type"):
            effective_last_run_summary["contract_breach_type"] = turn_meta[
                "contract_breach_type"
            ]
        if turn_meta.get("tool_leak_detected"):
            effective_last_run_summary["tool_leak_detected"] = True
        if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
            effective_last_run_summary[
                "assistant_claimed_tool_call_without_tool_event"
            ] = True
        if turn_meta.get("unfinished_intents"):
            effective_last_run_summary["unfinished_intents"] = turn_meta[
                "unfinished_intents"
            ]
        if turn_meta.get("leaked_tool_names"):
            effective_last_run_summary["leaked_tool_names"] = turn_meta[
                "leaked_tool_names"
            ]
        if turn_meta.get("recovered_via_retry") is not None:
            effective_last_run_summary["recovered_via_retry"] = turn_meta[
                "recovered_via_retry"
            ]
        if turn_meta.get("last_tool_name"):
            effective_last_run_summary["last_tool_name"] = turn_meta["last_tool_name"]
        if turn_meta.get("last_page_key"):
            effective_last_run_summary["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            effective_last_run_summary["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            effective_last_run_summary["interrupted_stage"] = turn_meta[
                "interrupted_stage"
            ]
        if turn_meta.get("tool_loop_progress"):
            effective_last_run_summary["tool_loop_progress"] = turn_meta[
                "tool_loop_progress"
            ]
        if turn_meta.get("sync_rescue") is not None:
            effective_last_run_summary["sync_rescue"] = turn_meta["sync_rescue"]
        if turn_meta.get("should_record_call_log") is not None:
            effective_last_run_summary["should_record_call_log"] = turn_meta[
                "should_record_call_log"
            ]
        if (
            bool(getattr(result, "interrupted", False))
            or turn_termination_reason == "interrupted"
        ):
            effective_last_run_summary["interrupted"] = True

        last_assistant_idx: int | None = None
        last_plain_assistant_idx: int | None = None
        last_assistant_with_signal_idx: int | None = None
        for j, m in enumerate(new_messages):
            if m.get("role") != "assistant":
                continue
            last_assistant_idx = j
            if self._assistant_has_content_or_signal(m):
                last_assistant_with_signal_idx = j
            if not m.get("tool_calls"):
                last_plain_assistant_idx = j

        turn_target_assistant_idx = (
            last_plain_assistant_idx
            if last_plain_assistant_idx is not None
            else (
                last_assistant_with_signal_idx
                if last_assistant_with_signal_idx is not None
                else last_assistant_idx
            )
        )

        for i, msg_dict in enumerate(new_messages):
            role = msg_dict.get("role", "")
            content = msg_dict.get("content", "")
            tool_calls = msg_dict.get("tool_calls")
            tool_call_id = msg_dict.get("tool_call_id")
            attachments = msg_dict.get("attachments")
            reasoning_content = msg_dict.get("reasoning_content")
            persisted_metadata = self._copy_metadata(msg_dict.get("metadata"))
            tool_calls = self._enrich_tool_calls_for_persistence(
                tool_calls,
                tool_result_map,
            )

            # Collect tool_calls for response payload / 收集 tool_calls 供响应拼装
            if tool_calls:
                tool_calls_collected.extend(tool_calls)

            # Skip empty assistant success unless pending confirm/consent or partial/interrupted / 空 assistant 成功轮不落库，除非待确认或中断语义
            should_skip_empty_assistant_success = (
                role == "assistant"
                and bool(getattr(result, "success", False))
                and not bool(getattr(result, "partial", False))
                and not bool(getattr(result, "interrupted", False))
                and not str(content or "").strip()
                and not bool(tool_calls)
                and not self._has_pending_state(
                    tool_calls=tool_calls,
                    metadata=persisted_metadata,
                )
                and not isinstance(
                    (persisted_metadata or {}).get("action_buttons"), list
                )
            )
            if should_skip_empty_assistant_success:
                continue

            # Token estimate for accounting / 估算 token 用量
            token_estimate = estimate_tokens(content) if content else 0

            # Persist attachments under metadata / 附件写入 metadata
            metadata = self._normalize_json_safe_dict(persisted_metadata)
            if attachments:
                metadata = metadata or {}
                metadata["attachments"] = self._normalize_json_safe(attachments)
            # assistant 消息的思考内容（chain-of-thought 模型）存入 metadata / Store reasoning for history display
            if role == "assistant" and reasoning_content and reasoning_content.strip():
                metadata = metadata or {}
                metadata["thinking_content"] = reasoning_content.strip()
            if (
                role == "assistant"
                and persisted_metadata
                and "action_buttons_used" in persisted_metadata
            ):
                metadata = metadata or {}
                metadata["action_buttons_used"] = persisted_metadata.get(
                    "action_buttons_used",
                )

            # tool 角色消息：存储工具执行状态
            if role == "tool" and tool_call_id and tool_call_id in tool_result_map:
                tr = tool_result_map[tool_call_id]
                metadata = metadata or {}
                metadata["tool_success"] = tr.success
                if not tr.success and tr.error:
                    metadata["tool_error"] = tr.error
                if tr.display_name:
                    metadata["tool_display_name"] = tr.display_name
                if tr.summary:
                    metadata["tool_summary"] = tr.summary
                if tr.summary_payload:
                    metadata["tool_summary_payload"] = tr.summary_payload
                if tr.result_link:
                    metadata["tool_result_link"] = tr.result_link
                if tr.error_type:
                    metadata["tool_error_type"] = tr.error_type
                if tr.duration_ms:
                    metadata["tool_duration_ms"] = tr.duration_ms

            # partial/interrupted: mark turn target assistant (works with or without final plain reply)
            # / 中断语义标记落到轮次目标 assistant（兼容无最终 plain assistant 的情况）
            should_mark_partial_semantics = (
                role == "assistant"
                and (
                    getattr(result, "partial", False)
                    or getattr(result, "interrupted", False)
                )
                and i == turn_target_assistant_idx
            )
            if should_mark_partial_semantics:
                metadata = metadata or {}
                metadata["partial"] = bool(
                    getattr(result, "partial", False)
                    or getattr(result, "interrupted", False)
                )
                metadata["interrupted"] = getattr(result, "interrupted", False)
                completion_reason = self._to_non_empty_str(
                    getattr(result, "completion_reason", None)
                )
                if completion_reason:
                    metadata["completion_reason"] = completion_reason

            if route_source and role == "assistant" and not route_source_marked:
                metadata = metadata or {}
                metadata["route_source"] = route_source
                route_source_marked = True

            if role == "assistant":
                if result.runtime_model_name:
                    metadata = metadata or {}
                    metadata["model_name"] = result.runtime_model_name
                if result.runtime_provider_id is not None:
                    metadata = metadata or {}
                    metadata["provider_id"] = result.runtime_provider_id
                if result.runtime_provider_name:
                    metadata = metadata or {}
                    metadata["provider_name"] = result.runtime_provider_name

            if (
                rag_sources
                and role == "assistant"
                and not tool_calls
                and i == last_plain_assistant_idx
            ):
                metadata = metadata or {}
                metadata["rag_sources"] = rag_sources
                if getattr(result, "rag_source_kinds", None):
                    metadata["rag_source_kinds"] = result.rag_source_kinds

            if (
                role == "assistant"
                and not tool_calls
                and i == turn_target_assistant_idx
            ):
                if getattr(result, "prune_stats", None):
                    metadata = metadata or {}
                    metadata["prune_stats"] = result.prune_stats
                if getattr(result, "context_compacted", False):
                    metadata = metadata or {}
                    metadata["context_compacted"] = True
                if getattr(result, "memory_flush_triggered", False):
                    metadata = metadata or {}
                    metadata["memory_flush_triggered"] = True
                if getattr(result, "memory_recalled", False):
                    metadata = metadata or {}
                    metadata["memory_recalled"] = True
                if effective_context_diagnostics:
                    metadata = metadata or {}
                    metadata["context_diagnostics"] = self._normalize_json_safe(
                        effective_context_diagnostics
                    )
                if effective_last_run_summary:
                    metadata = metadata or {}
                    metadata["last_run_summary"] = self._normalize_json_safe(
                        effective_last_run_summary
                    )

            if role == "assistant" and i == turn_target_assistant_idx:
                metadata = metadata or {}
                if effective_context_diagnostics:
                    metadata["context_diagnostics"] = self._normalize_json_safe(
                        effective_context_diagnostics
                    )
                if effective_last_run_summary:
                    metadata["last_run_summary"] = self._normalize_json_safe(
                        effective_last_run_summary
                    )
                if turn_record_payload:
                    metadata["turn_record"] = self._normalize_json_safe(
                        turn_record_payload
                    )
                if turn_outcome:
                    metadata["turn_outcome"] = turn_outcome
                if turn_termination_reason:
                    metadata["termination_reason"] = turn_termination_reason
                    metadata.setdefault("completion_reason", turn_termination_reason)
                if turn_protocol_path:
                    metadata["protocol_path"] = turn_protocol_path
                if turn_selected_tools:
                    metadata["selected_tool_names"] = self._normalize_json_safe(
                        turn_selected_tools
                    )
                if turn_selected_skills:
                    metadata["selected_skill_names"] = self._normalize_json_safe(
                        turn_selected_skills
                    )
                if turn_context_sources:
                    metadata["context_sources"] = self._normalize_json_safe(
                        turn_context_sources
                    )

            metadata = self._normalize_json_safe_dict(metadata)

            # assistant/tool 消息关联 agent_id（user/system 不关联）
            msg_agent_id = agent_id if role in ("assistant", "tool") else None
            msg_model_id = result.runtime_model_id if role == "assistant" else None

            await self.message_repo.create(
                {
                    "tenant_id": self.tenant_id,
                    "conversation_id": conversation.id,
                    "role": role,
                    "content": content,
                    "sequence": next_seq + persisted_count,
                    "token_count": token_estimate,
                    "tool_calls": tool_calls,
                    "tool_call_id": tool_call_id,
                    "agent_id": msg_agent_id,
                    "model_id": msg_model_id,
                    "metadata_": metadata,
                }
            )
            persisted_count += 1

        # 递增 message_count 冗余计数
        new_message_count = (conversation.message_count or 0) + persisted_count
        await self.repo.update(
            conversation.id,
            {"message_count": new_message_count},
        )

        return tool_calls_collected, persisted_count

    async def persist_user_messages(
        self,
        *,
        conversation: AgentConversation,
        messages: list[ChatMessage],
    ) -> int:
        """Persist pre-stream user messages so failed turns still keep user input."""

        user_messages = [
            message
            for message in (messages or [])
            if message.role == "user"
            and (
                bool(str(message.content or "").strip())
                or bool(message.attachments)
            )
        ]
        if not user_messages:
            return 0

        next_seq = await self.message_repo.get_next_sequence(conversation.id)
        persisted_count = 0

        for message in user_messages:
            metadata = None
            if message.attachments:
                metadata = {
                    "attachments": self._normalize_json_safe(message.attachments),
                    "stream_seeded": True,
                }
            else:
                metadata = {"stream_seeded": True}
            metadata = self._normalize_json_safe_dict(metadata)

            content = str(message.content or "")
            await self.message_repo.create(
                {
                    "tenant_id": self.tenant_id,
                    "conversation_id": conversation.id,
                    "role": MessageRoleEnum.USER.value,
                    "content": content,
                    "sequence": next_seq + persisted_count,
                    "token_count": estimate_tokens(content) if content else 0,
                    "agent_id": None,
                    "model_id": None,
                    "metadata_": metadata,
                }
            )
            persisted_count += 1

        if persisted_count:
            conversation.message_count = int(conversation.message_count or 0) + int(
                persisted_count
            )
            await self.repo.update(
                conversation.id,
                {"message_count": conversation.message_count},
            )

        return persisted_count

    async def mark_memory_updated(self, conversation_id: int) -> None:
        """
        标记最后一条 assistant 消息的 metadata 中 memory_updated = true / Mark last assistant message memory_updated in metadata.

        在 _persist_session_memory 成功后调用，用于前端加载历史时恢复记忆标记。
        """
        messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=1,
        )
        if not messages:
            return
        last_msg = messages[-1]
        if last_msg.role != MessageRoleEnum.ASSISTANT.value:
            return
        metadata = self._normalize_json_safe_dict(last_msg.metadata_) or {}
        metadata["memory_updated"] = True
        await self.message_repo.update(
            last_msg.id,
            {"metadata_": self._normalize_json_safe_dict(metadata) or metadata},
        )

    async def get_context_compaction_snapshot(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        """Read sidecar context compaction snapshot / 读取对话级上下文压缩快照。"""
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            return None
        metadata = (
            conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
        )
        snapshot = metadata.get(_CONTEXT_COMPACTION_METADATA_KEY)
        return snapshot if isinstance(snapshot, dict) else None

    async def upsert_context_compaction_snapshot(
        self,
        conversation_id: int,
        *,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any] | None:
        """Persist sidecar context compaction snapshot into conversation metadata / 将上下文压缩快照写入 conversation metadata。"""
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            return None
        metadata = dict(conversation.metadata_ or {})
        snapshot = {
            "summary": summary,
            "source_message_count": source_message_count,
            "source_token_estimate": source_token_estimate,
            "generated_at": self._format_dt(utc_now()),
        }
        metadata[_CONTEXT_COMPACTION_METADATA_KEY] = snapshot
        conversation.metadata_ = metadata
        await self.db.flush()
        return snapshot

    async def update_stats(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        current_agent: Agent | None = None,
    ) -> None:
        """
        更新对话统计信息，并尝试提取输出变量 / Update conversation stats and try to extract output variables.

        Args:
            conversation: 对话实例
            result: 执行结果
        """
        new_token_count = (conversation.token_count or 0) + result.total_tokens
        new_total_tokens = (conversation.total_tokens or 0) + result.total_tokens

        update_data: dict[str, Any] = {
            "token_count": new_token_count,
            "total_tokens": new_total_tokens,
        }

        # 尝试提取输出变量 / Try extract output variables
        agent = current_agent or conversation.agent
        if agent and agent.output_schema and result.output:
            extracted = parse_output(result.output, agent.output_schema)
            if extracted:
                metadata = dict(conversation.metadata_ or {})
                metadata["output_variables"] = extracted
                update_data["metadata_"] = metadata

        await self.repo.update(
            conversation.id,
            update_data,
        )


__all__ = ["ConversationService"]
