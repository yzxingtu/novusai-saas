"""NovusDoc tag models / NovusDoc 标签模型"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NovusdocTag(BaseModel):
    __tablename__ = "px_novusdoc_tags"
    __data_permission__ = True

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="0=platform/admin space, N=tenant N's space",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


class NovusdocDocumentTag(BaseModel):
    __tablename__ = "px_novusdoc_document_tags"

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
