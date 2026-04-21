from __future__ import annotations

import re
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_load_and_parse_document_blocks_audio_before_placeholder_describer_use(
    monkeypatch,
) -> None:
    from app.ai.rag.processor_document_support import load_and_parse_document
    from app.core.i18n import _

    def _unexpected_audio_describer(*args, **kwargs):
        raise AssertionError("AudioDescriber should not be instantiated")

    monkeypatch.setattr(
        "app.ai.rag.audio_describer.AudioDescriber",
        _unexpected_audio_describer,
    )

    doc = SimpleNamespace(
        file_type="audio",
        metadata_extra="transcript placeholder",
        attachment_id=None,
        file_name="voice-note.mp3",
    )

    with pytest.raises(
        ValueError,
        match=re.escape(_("knowledge_base.document.error.audio_text_unavailable")),
    ):
        await load_and_parse_document(None, doc, tenant_id=7, kb=None)


@pytest.mark.asyncio
async def test_load_and_parse_document_blocks_video_before_placeholder_describer_use(
    monkeypatch,
) -> None:
    from app.ai.rag.processor_document_support import load_and_parse_document
    from app.core.i18n import _

    def _unexpected_video_describer(*args, **kwargs):
        raise AssertionError("VideoDescriber should not be instantiated")

    monkeypatch.setattr(
        "app.ai.rag.video_describer.VideoDescriber",
        _unexpected_video_describer,
    )

    doc = SimpleNamespace(
        file_type="video",
        metadata_extra="video placeholder",
        attachment_id=None,
        file_name="demo.mp4",
    )

    with pytest.raises(
        ValueError,
        match=re.escape(_("knowledge_base.document.error.video_text_unavailable")),
    ):
        await load_and_parse_document(None, doc, tenant_id=7, kb=None)
