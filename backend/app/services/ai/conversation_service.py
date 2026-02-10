"""
对话数据生命周期管理 Service

提供对话列表、详情、搜索、归档、批量归档、删除和导出
"""

import json
from datetime import date, timedelta
from typing import Any

from app.repositories.ai.agent_conversation_repository import AgentConversationRepository
from app.repositories.ai.conversation_message_repository import ConversationMessageRepository
from app.models.ai.agent_conversation import AgentConversation
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ConversationStatusEnum, MessageRoleEnum
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("ai.conversation_service")


class ConversationService(TenantService[AgentConversation, AgentConversationRepository]):
    """
    对话数据生命周期管理 Service

    提供对话列表、详情、搜索、归档、批量归档、删除和导出
    """

    model = AgentConversation
    repository_class = AgentConversationRepository

    @property
    def message_repo(self) -> ConversationMessageRepository:
        """获取消息 Repository（延迟创建）"""
        if not hasattr(self, "_message_repo"):
            self._message_repo = ConversationMessageRepository(
                self.db, self.tenant_id,
            )
        return self._message_repo

    # ========================================
    # 详情
    # ========================================

    async def get_conversation_detail(
        self,
        conversation_id: int,
        message_skip: int = 0,
        message_limit: int = 50,
    ) -> dict[str, Any]:
        """
        获取对话详情（含分页消息列表）

        Args:
            conversation_id: 对话 ID
            message_skip: 消息跳过数量
            message_limit: 消息返回数量

        Returns:
            对话详情字典，含 messages 和 message_count
        """
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundException(message=_("conversation.not_found"))

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
        result["message_list"] = [msg.to_dict() for msg in messages]
        result["message_count"] = message_count

        # 提取关联智能体名称
        result["agent_name"] = None
        try:
            agent_obj = getattr(conversation, "agent", None)
            if agent_obj is not None:
                result["agent_name"] = agent_obj.name
        except (AttributeError, Exception):
            pass

        return result

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
        跨对话全文搜索消息内容

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

        return {
            "items": [msg.to_dict() for msg in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ========================================
    # 归档
    # ========================================

    async def archive_conversation(self, conversation_id: int) -> AgentConversation:
        """
        归档单个对话

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

        updated = await self.repo.update(conversation_id, {
            "status": ConversationStatusEnum.ARCHIVED.value,
        })

        logger.info(
            _("conversation.log.archived"),
            conversation_id=conversation_id,
            tenant_id=self.tenant_id,
        )

        return updated

    async def batch_archive(
        self,
        agent_id: int | None = None,
        before_days: int = 90,
    ) -> int:
        """
        批量归档 N 天前的对话

        使用 ID-only 查询 + 分批处理，避免大数据量时全量加载 ORM 对象导致 OOM。

        Args:
            agent_id: 可选，按智能体过滤
            before_days: 天数（归档 N 天前的 active 对话）

        Returns:
            归档的对话数量
        """
        before_date = date.today() - timedelta(days=before_days)
        total_count = 0
        batch_size = 1000

        while True:
            ids = await self.repo.get_conversation_ids_before(
                before_date=before_date,
                agent_id=agent_id,
                batch_size=batch_size,
            )
            if not ids:
                break

            count = await self.repo.batch_update_status(
                ids=ids,
                status=ConversationStatusEnum.ARCHIVED.value,
            )
            total_count += count

            # 如果本批实际归档数 < 查询数，说明已处理完毕
            if len(ids) < batch_size:
                break

        if total_count > 0:
            logger.info(
                _("conversation.log.batch_archived"),
                count=total_count,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                before_days=before_days,
            )

        return total_count

    # ========================================
    # 导出
    # ========================================

    async def export_conversation(
        self,
        conversation_id: int,
        export_format: str = "json",
    ) -> dict[str, Any]:
        """
        导出对话数据

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

        if export_format == "markdown":
            content = self._to_markdown(conversation, messages)
            filename = f"{title}.md"
        else:
            content = self._to_json(conversation, messages)
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
        """将对话转换为 JSON 字符串"""
        data = {
            "id": conversation.id,
            "title": conversation.title,
            "status": conversation.status,
            "token_count": conversation.token_count,
            "created_at": str(conversation.created_at) if conversation.created_at else None,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "token_count": msg.token_count,
                    "tool_calls": msg.tool_calls,
                    "tool_call_id": msg.tool_call_id,
                    "created_at": str(msg.created_at) if msg.created_at else None,
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
        """将对话转换为 Markdown 字符串"""
        role_labels = {
            MessageRoleEnum.SYSTEM.value: _("conversation.export.role.system"),
            MessageRoleEnum.USER.value: _("conversation.export.role.user"),
            MessageRoleEnum.ASSISTANT.value: _("conversation.export.role.assistant"),
            MessageRoleEnum.TOOL.value: _("conversation.export.role.tool"),
        }

        title = conversation.title or f"Conversation #{conversation.id}"
        lines = [f"# {title}", ""]

        for msg in messages:
            label = role_labels.get(msg.role, msg.role)
            lines.append(f"## {label}")
            lines.append("")
            lines.append(msg.content or "")
            lines.append("")

            # 工具调用信息
            if msg.tool_calls:
                lines.append("**Tool Calls:**")
                lines.append(f"```json\n{json.dumps(msg.tool_calls, indent=2, ensure_ascii=False)}\n```")
                lines.append("")

        return "\n".join(lines)


__all__ = ["ConversationService"]
