"""
附件模型 / Attachment Model

存储上传文件的元信息，支持多存储驱动和秒传
Stores uploaded file metadata, supports multiple storage drivers and instant upload.
"""

from sqlalchemy import JSON, Column, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy


class Attachment(TenantModel):
    __tablename__ = "attachments"

    __ai_policy__ = {
        "label": "附件",
        "keywords": ["文件", "附件", "file"],
        "allow_read": True,
        "blocked_columns": ["path"],
    }

    __delete_deps__ = [
        DeletionDep("KnowledgeDocument", "attachment_id", DeletionStrategy.BLOCK,
                    label_field="file_name", i18n_key="knowledge_document"),
    ]

    # 覆盖 TenantModel 的 tenant_id：允许 NULL（全局/管理端 KB 附件无企业归属） /
    # Override tenant_id: NULL for global/admin KB attachments without tenant
    tenant_id = Column(Integer, nullable=True, index=True, comment="企业ID / Tenant id")

    # 支持过滤字段 / Filterable fields
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "name": "name",
        "original_name": "original_name",
        "path": "path",
        "hash": "hash",
        "mime_type": "mime_type",
        "extension": "extension",
        "visibility": "visibility",
        "status": "status",
        "driver": "driver",
        "base_url": "base_url",
        "source": "source",
        "uploader_id": "uploader_id",
        "business_type": "business_type",
        "business_id": "business_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = ["id", "name", "original_name", "mime_type", "extension", "status", "driver", "source", "created_at", "updated_at"]

    # 支持远程下拉配置 / Remote select config
    __selectable__ = {
        "label": "original_name",      # 显示名称：原始文件名 / Label: original file name
        "value": "id",                 # 值：ID / Value: primary key
        "search": ["name", "original_name"],  # 搜索字段 / Search fields
        "extra": ["mime_type", "extension", "size"],  # 额外信息 / Extra fields
    }

    # 索引 / Indexes
    __table_args__ = (
        Index("ix_attachments_path", "path", unique=True),
        Index("ix_attachments_tenant_hash", "tenant_id", "hash"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        comment="文件名 / Stored file name",
    )
    original_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="原始文件名 / Original upload name",
    )
    path: Mapped[str] = mapped_column(
        String(500),
        comment="存储路径 / Storage path",
    )
    size: Mapped[int] = mapped_column(
        Integer,
        comment="文件大小(字节) / Size in bytes",
    )
    hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="文件哈希 / Content hash",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME 类型 / MIME type",
    )
    extension: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="文件扩展名 / Extension",
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        comment="可见性 / Visibility",
    )
    driver: Mapped[str] = mapped_column(
        String(50),
        comment="存储驱动 / Storage driver",
    )
    base_url: Mapped[str] = mapped_column(
        String(500),
        comment="文件访问基础URL / Base URL for access",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        comment="状态 / Status",
    )
    source: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="上传来源 / Upload source",
    )
    uploader_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="上传者 ID / Uploader id",
    )
    business_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="业务类型 / Business type",
    )
    business_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="业务 ID / Business id",
    )
    meta: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="扩展元数据 / Extra metadata",
    )


__all__ = ["Attachment"]
