from sqlalchemy import Integer, String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class Attachment(TenantModel):
    __tablename__ = "attachments"
    
    # 支持过滤字段
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
    
    # 支持远程下拉配置
    __selectable__ = {
        "label": "original_name",      # 显示名称：原始文件名
        "value": "id",                 # 值：ID
        "search": ["name", "original_name"],  # 搜索字段
        "extra": ["mime_type", "extension", "size"],  # 额外信息
    }
    
    # 索引
    __table_args__ = (
        Index("ix_attachments_tenant_path", "tenant_id", "path", unique=True),
        Index("ix_attachments_tenant_hash", "tenant_id", "hash"),
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        comment="文件名",
    )
    original_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="原始文件名",
    )
    path: Mapped[str] = mapped_column(
        String(500),
        comment="存储路径",
    )
    size: Mapped[int] = mapped_column(
        Integer,
        comment="文件大小(字节)",
    )
    hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="文件哈希",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME 类型",
    )
    extension: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="文件扩展名",
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        comment="可见性",
    )
    driver: Mapped[str] = mapped_column(
        String(50),
        comment="存储驱动",
    )
    base_url: Mapped[str] = mapped_column(
        String(500),
        comment="文件访问基础URL",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        comment="状态",
    )
    source: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="上传来源",
    )
    uploader_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="上传者 ID",
    )
    business_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="业务类型",
    )
    business_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="业务 ID",
    )
    meta: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="扩展元数据",
    )


__all__ = ["Attachment"]
