"""
对话数据生命周期管理 Service / Conversation Lifecycle Service

提供对话列表、详情、搜索、归档、删除和导出
Provides conversation list, detail, search, archive, delete and export.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine.output_parser import parse_output
from app.ai.engine.types import ExecutionResult
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    ConversationOwnerTypeEnum,
    ConversationStatusEnum,
    MessageRoleEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.tenant.attachment import Attachment
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.session_memory_service import SessionMemoryService
from app.services.tenant.attachment_download_service import AttachmentDownloadService

logger = LogManager.get_logger("ai.conversation_service")
_ATTACHMENT_URL_RE = re.compile(
    r"/api/public/attachments/(\d+)/(?:access|image)",
    re.IGNORECASE,
)


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
        text = str(raw_url or "").strip()
        if not text:
            return None
        match = _ATTACHMENT_URL_RE.search(text)
        if not match:
            return None
        return int(match.group(1))

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
    # 详情
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

        # 获取分页消息
        messages = await self.message_repo.get_by_conversation(
            conversation_id=conversation_id,
            skip=message_skip,
            limit=message_limit,
        )
        message_count = await self.message_repo.count_by_conversation(
            conversation_id,
        )

        result = conversation.to_dict()
        # Enrich messages with agent info for multi-agent avatar display
        message_list = []
        for msg in messages:
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
            message_list.append(msg_dict)
        result["message_list"] = message_list
        result["message_count"] = message_count

        # 提取关联智能体名称
        result["agent_name"] = None
        try:
            agent_obj = getattr(conversation, "agent", None)
            if agent_obj is not None:
                result["agent_name"] = agent_obj.name
        except AttributeError:
            pass

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

    def _get_memory_tenant_id(self) -> int:
        return self.tenant_id if self.tenant_id is not None else PLATFORM_TENANT_ID

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
    # 搜索
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
    # 归档
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

        # 主动清理会话记忆（兜底 TTL 之外的即时清理）
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
    # 导出
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

        # 分批加载所有消息
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

            # 工具调用信息
            tool_calls = _msg_get(msg, "tool_calls")
            if tool_calls:
                lines.append("**Tool Calls:**")
                lines.append(
                    f"```json\n{json.dumps(tool_calls, indent=2, ensure_ascii=False)}\n```"
                )
                lines.append("")

            metadata = _msg_get(msg, "metadata", _msg_get(msg, "metadata_"))
            attachments = (
                metadata.get("attachments")
                if isinstance(metadata, dict)
                else None
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
    # 对话执行辅助（从 AgentChatService 提取）
    # ========================================

    # 历史消息最大加载条数（兜底默认值）
    MAX_HISTORY_MESSAGES = 50
    # 历史消息最大 Token 数（兜底默认值，0=不限制）
    MAX_HISTORY_TOKENS = 0
    # 对话标题最大长度
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
            # 续接已有对话
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

        # 创建新对话
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
            "Conversation created: id={} agent={} tenant={} owner_type={}",
            conversation.id,
            agent_id,
            self.tenant_id,
            owner_type,
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
            # 跳过 system 消息（由引擎重新构建）
            if msg.role == MessageRoleEnum.SYSTEM.value:
                continue

            # 从 metadata 恢复附件（用于多模态历史消息）
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
                # Tool-round thinking is persisted separately in metadata; do not
                # feed the same text back as assistant content in future rounds.
                # 工具轮思考已单独存入 metadata，后续续聊时不要再把同文案当成 assistant 正文回灌给模型。
                msg_content = ""

            chat_messages.append(
                ChatMessage(
                    role=msg.role,
                    content=msg_content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    attachments=msg_attachments,
                    reasoning_content=msg_reasoning_content,
                ),
            )

        # Token 截断：从最旧消息开始移除，直到总 token 不超过 max_tokens
        if max_tokens > 0 and chat_messages:
            total = sum(estimate_tokens(m.content or "") for m in chat_messages)
            while total > max_tokens and len(chat_messages) > 1:
                removed = chat_messages.pop(0)
                total -= estimate_tokens(removed.content or "")

        # 清理孤立的 tool 消息（前面没有 tool_calls 的 assistant 消息）
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
                # Orphan tool: drop (no matching assistant round)
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

    async def persist_chat_messages(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        history_count: int,
        agent_id: int | None = None,
        route_source: str | None = None,
    ) -> list[dict[str, Any]]:
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
            收集到的 tool_calls（用于响应）
        """
        # 动态计算前缀 system 消息数（而非硬编码 1）
        system_count = 0
        for msg_dict in result.messages:
            if msg_dict.get("role") == "system":
                system_count += 1
            else:
                break
        new_start = system_count + history_count
        new_messages_raw = result.messages[new_start:]

        if not new_messages_raw:
            return []

        # Sanitize: only persist complete tool rounds and plain assistant; drop orphan tool_calls
        # 仅持久化完整 tool round 与普通 assistant，避免半截 tool skeleton
        chat_msgs = [
            ChatMessage(
                role=m.get("role", ""),
                content=m.get("content", "") or "",
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
                attachments=m.get("attachments"),
                reasoning_content=m.get("reasoning_content"),
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
            }
            for m in chat_msgs
            if not m.internal_only
        ]

        # 构建 tool_call_id → ToolResult 的查找表
        tool_result_map: dict[str, ToolResult] = {}
        if result.tool_results:
            for tr in result.tool_results:
                if tr.tool_call_id:
                    tool_result_map[tr.tool_call_id] = tr

        # 获取下一个 sequence
        next_seq = await self.message_repo.get_next_sequence(conversation.id)
        tool_calls_collected: list[dict[str, Any]] = []
        route_source_marked = False

        rag_sources = getattr(result, "rag_sources", None)
        last_plain_assistant_idx: int | None = None
        for j, m in enumerate(new_messages):
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                last_plain_assistant_idx = j

        for i, msg_dict in enumerate(new_messages):
            role = msg_dict.get("role", "")
            content = msg_dict.get("content", "")
            tool_calls = msg_dict.get("tool_calls")
            tool_call_id = msg_dict.get("tool_call_id")
            attachments = msg_dict.get("attachments")
            reasoning_content = msg_dict.get("reasoning_content")

            # 收集 tool_calls 用于响应
            if tool_calls:
                tool_calls_collected.extend(tool_calls)

            # 估算 token 数
            token_estimate = estimate_tokens(content) if content else 0

            # 附件存入 metadata
            metadata = None
            if attachments:
                metadata = {"attachments": attachments}
            # assistant 消息的思考内容（chain-of-thought 模型）存入 metadata / Store reasoning for history display
            if role == "assistant" and reasoning_content and reasoning_content.strip():
                metadata = metadata or {}
                metadata["thinking_content"] = reasoning_content.strip()

            # tool 角色消息：存储工具执行状态
            if role == "tool" and tool_call_id and tool_call_id in tool_result_map:
                tr = tool_result_map[tool_call_id]
                metadata = metadata or {}
                metadata["tool_success"] = tr.success
                if not tr.success and tr.error:
                    metadata["tool_error"] = tr.error

            # partial/interrupted: mark last plain assistant message / 中断时标记最后一条普通 assistant
            is_last_assistant = (
                role == "assistant"
                and not tool_calls
                and (
                    getattr(result, "partial", False)
                    or getattr(result, "interrupted", False)
                )
                and i == len(new_messages) - 1
            )
            if is_last_assistant:
                metadata = metadata or {}
                metadata["partial"] = getattr(result, "partial", False)
                metadata["interrupted"] = getattr(result, "interrupted", False)
                if getattr(result, "completion_reason", ""):
                    metadata["completion_reason"] = result.completion_reason

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

            # assistant/tool 消息关联 agent_id（user/system 不关联）
            msg_agent_id = agent_id if role in ("assistant", "tool") else None
            msg_model_id = result.runtime_model_id if role == "assistant" else None

            await self.message_repo.create(
                {
                    "tenant_id": self.tenant_id,
                    "conversation_id": conversation.id,
                    "role": role,
                    "content": content,
                    "sequence": next_seq + i,
                    "token_count": token_estimate,
                    "tool_calls": tool_calls,
                    "tool_call_id": tool_call_id,
                    "agent_id": msg_agent_id,
                    "model_id": msg_model_id,
                    "metadata_": metadata,
                }
            )

        # 递增 message_count 冗余计数
        new_message_count = (conversation.message_count or 0) + len(new_messages)
        await self.repo.update(
            conversation.id,
            {"message_count": new_message_count},
        )

        return tool_calls_collected

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
        metadata = dict(last_msg.metadata_ or {})
        metadata["memory_updated"] = True
        await self.message_repo.update(last_msg.id, {"metadata_": metadata})

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

        # 尝试提取输出变量
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
