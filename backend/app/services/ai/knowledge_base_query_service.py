"""
Knowledge base query helpers.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.exceptions import NotFoundException
from app.services.ai.knowledge_base_projector import build_kb_detail


class KnowledgeBaseQueryService:
    """Read-focused queries extracted from KnowledgeBaseService."""

    def __init__(self, repo) -> None:
        self.repo = repo

    async def get_kb_detail(self, kb_id: int) -> dict[str, Any]:
        kb = await self.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))
        return build_kb_detail(kb)


__all__ = ["KnowledgeBaseQueryService"]
