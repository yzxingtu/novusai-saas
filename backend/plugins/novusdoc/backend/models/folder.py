"""NovusDoc folder model / NovusDoc 文件夹模型"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NovusdocFolder(BaseModel):
    __tablename__ = "px_novusdoc_folders"
    __data_permission__ = True

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="0=platform/admin space, N=tenant N's space",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
