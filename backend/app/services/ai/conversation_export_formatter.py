"""
Conversation export formatting helpers.
"""

from __future__ import annotations

from typing import Any

from app.models.ai.agent_conversation import AgentConversation
from app.services.ai.conversation_export_service import ConversationExportService


def to_json(conversation: AgentConversation, messages: list[Any]) -> str:
    return ConversationExportService.to_json(conversation, messages)


def to_markdown(conversation: AgentConversation, messages: list[Any]) -> str:
    return ConversationExportService.to_markdown(conversation, messages)
