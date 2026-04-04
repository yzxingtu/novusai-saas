"""Shared API helper regression tests. / 共享 API 辅助。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.shared._attachment_helpers import (
    normalize_attachment_hash,
    resolve_attachment_upload_rules,
)
from app.api.shared._kb_helpers import (
    build_content_hash,
    build_document_progress_payload,
    build_qa_content,
    create_url_import_documents,
    resolve_document_type,
)


def test_normalize_attachment_hash_strips_sha256_prefix() -> None:
    assert normalize_attachment_hash("sha256:abcd") == "abcd"
    assert normalize_attachment_hash("plain") == "plain"


@pytest.mark.asyncio
async def test_resolve_attachment_upload_rules_falls_back_to_platform() -> None:
    config_service = AsyncMock()
    config_service.get_tenant_config = AsyncMock(side_effect=["", ""])
    config_service.get_platform_config = AsyncMock(
        side_effect=[".png,.jpg", ".exe", 64],
    )

    rules = await resolve_attachment_upload_rules(config_service, tenant_id=7)

    assert rules == {
        "allowed_extensions": ".png,.jpg",
        "denied_extensions": ".exe",
        "max_file_size_mb": 64,
    }


def test_kb_helper_pure_builders() -> None:
    assert resolve_document_type("report.PDF") == "pdf"
    assert build_content_hash("hello") == build_content_hash(b"hello")
    assert build_qa_content("Q1", "A1") == "Q: Q1\nA: A1"
    payload = build_document_progress_payload(
        SimpleNamespace(status="pending", chunk_count=3),
        None,
    )
    assert payload == {
        "stage": "pending",
        "progress": 0,
        "total_chunks": 3,
        "processed_chunks": 0,
    }


@pytest.mark.asyncio
async def test_create_url_import_documents_skips_invalid_and_duplicate_urls() -> None:
    created_docs: list[dict[str, object]] = []

    class _DocService:
        async def get_by_kb_and_hash(self, kb_id: int, file_hash: str):
            _ = kb_id
            return file_hash == build_content_hash("https://duplicate.example")

        async def create(self, payload: dict[str, object]):
            created_docs.append(payload)
            return SimpleNamespace(to_dict=lambda: {"id": len(created_docs), **payload})

    docs = await create_url_import_documents(
        doc_service=_DocService(),
        kb_id=5,
        urls=[
            "   ",
            "ftp://invalid.example",
            "https://duplicate.example",
            "https://valid.example",
        ],
    )

    assert len(docs) == 1
    assert docs[0]["source_url"] == "https://valid.example"

