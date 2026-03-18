"""
CRUD 代码生成配置版本历史模型 / Codegen Config Version History Model

每次保存配置时创建一条版本记录，用于版本历史与恢复
Each config save creates a version record for history and restore.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class CodegenConfigVersion(BaseModel):
    """
    CRUD 代码生成配置版本 / Codegen config version snapshot.

    关联 CodegenConfig，存储 config_json 快照。
    """

    __tablename__ = "codegen_config_versions"

    __filterable__ = {"id": "id", "config_id": "config_id", "created_at": "created_at"}
    __sortable__ = ["id", "config_id", "created_at"]

    config_id: Mapped[int] = mapped_column(
        ForeignKey("codegen_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="配置 ID / Config ID",
    )
    config_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="配置快照 JSON / Config snapshot JSON",
    )
    note: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="版本备注 / Version note",
    )

    config = relationship(
        "CodegenConfig",
        back_populates="versions",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<CodegenConfigVersion(id={self.id}, config_id={self.config_id})>"


__all__ = ["CodegenConfigVersion"]
