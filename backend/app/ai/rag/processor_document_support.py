"""Document loading and parsing helpers for the RAG processor task."""

from __future__ import annotations

import io

from sqlalchemy import select

from app.core.i18n import _
from app.enums.knowledge_base import DocumentTypeEnum
from app.models.tenant.attachment import Attachment

from .parser import QaPairParser, get_parser

IMAGE_DOC_TYPES: frozenset[str] = frozenset(
    {"image", "jpg", "jpeg", "png", "webp", "gif"}
)
AUDIO_DOC_TYPES: frozenset[str] = frozenset(
    {"audio", "mp3", "wav", "m4a", "flac", "aac"}
)
VIDEO_DOC_TYPES: frozenset[str] = frozenset(
    {"video", "mp4", "webm", "mov", "avi", "mkv"}
)


async def load_and_parse_document(db, doc, tenant_id, kb=None) -> list:
    """
    Load and parse document content, return non-empty ParsedPage list. / 加载并解析文档内容，返回非空 ParsedPage 列表。

    Unified handling of QA-type and file-type document loading logic,
    avoiding duplicate code in parse/chunk/embed stages.
    统一处理 QA 类型和文件类型的文档加载逻辑，
    避免在解析/分块/嵌入阶段重复相同代码。

    Automatically instantiates VisionDescriber and injects into parser when kb.extract_images=True.
    Empty ParsedPage (content='') are filtered out and won't enter the chunking stage.
    当 kb.extract_images=True 时自动实例化 VisionDescriber 并注入解析器。
    空内容的 ParsedPage（content=''）会被过滤，不进入分块阶段。
    """
    from app.ai.rag.vision_describer import VisionDescriber
    from app.configs.service import ConfigService
    from app.storage import LOCAL_STORAGE_ROOT, storage_manager
    from app.storage.base import StorageConfig

    if doc.file_type == DocumentTypeEnum.QA.value:
        import json

        qa_data = json.loads(doc.metadata_extra or "{}")
        qa_parser = QaPairParser()
        return await qa_parser.parse_qa(
            question=qa_data.get("question", ""),
            answer=qa_data.get("answer", ""),
            file_name=doc.file_name,
        )

    if doc.file_type in AUDIO_DOC_TYPES:
        raise ValueError(_("knowledge_base.document.error.audio_text_unavailable"))
    if doc.file_type in VIDEO_DOC_TYPES:
        raise ValueError(_("knowledge_base.document.error.video_text_unavailable"))

    needs_vision = (
        kb is not None and getattr(kb, "extract_images", False)
    ) or doc.file_type in IMAGE_DOC_TYPES

    vision_describer = VisionDescriber(db, tenant_id) if needs_vision else None

    if not doc.attachment_id and doc.metadata_extra:
        parser = get_parser(
            doc.file_type,
            vision_describer=vision_describer,
            knowledge_base=kb,
        )
        pages = await parser.parse(
            io.BytesIO(doc.metadata_extra.encode("utf-8")),
            doc.file_name,
        )
        return [page for page in pages if page.content.strip()]

    if not doc.attachment_id:
        raise ValueError("Document has no attachment")

    attachment_stmt = select(Attachment).where(
        Attachment.id == doc.attachment_id,
        Attachment.is_deleted.is_(False),
    )
    attachment = (await db.execute(attachment_stmt)).scalar_one_or_none()
    if not attachment:
        raise ValueError("Attachment not found")

    config_service = ConfigService(db)
    driver_name = await config_service.get_platform_config(
        "platform_storage_driver", default="local"
    )
    if str(driver_name) == "local":
        root_path = str(LOCAL_STORAGE_ROOT)
    else:
        root_path = await config_service.get_platform_config(
            "platform_storage_root_path", default=""
        )
    base_url = await config_service.get_platform_config(
        "platform_storage_base_url", default=None
    )
    options = await config_service.get_platform_config(
        "platform_storage_options", default={}
    )
    storage_config = StorageConfig(
        driver=str(driver_name),
        root_path=str(root_path),
        base_url=base_url,
        options=options or {},
    )
    driver = storage_manager.get_driver(storage_config)
    file_content = await driver.get(attachment.path)

    parser = get_parser(
        doc.file_type,
        vision_describer=vision_describer,
        knowledge_base=kb,
    )
    pages = await parser.parse(file_content, doc.file_name)
    parsed_pages = [page for page in pages if page.content.strip()]
    if parsed_pages:
        return parsed_pages
    return parsed_pages


__all__ = ["load_and_parse_document"]
