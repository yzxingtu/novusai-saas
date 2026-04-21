"""Fail-closed audio describer placeholder for KB ingest."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _

if TYPE_CHECKING:
    from app.models.ai.knowledge_base import KnowledgeBase


class AudioDescriber:
    """Reserved seam for future audio-to-text support."""

    def __init__(self, db: AsyncSession, tenant_id: int | None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def describe_audio(
        self,
        _audio_bytes: bytes,
        _mime_type: str,
        _knowledge_base: KnowledgeBase | None = None,
    ) -> str:
        raise ValueError(_("knowledge_base.document.error.audio_text_unavailable"))


__all__ = ["AudioDescriber"]
