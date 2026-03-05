"""
文件/文件夹节点模型
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.base_model import TenantModel, utc_now
from app.enums.base import LabeledStrEnum


class NodeTypeEnum(LabeledStrEnum):
    FILE   = "file",   "文件"
    FOLDER = "folder", "文件夹"


class FileNode(TenantModel):
    __tablename__ = "px_netdisk_nodes"

    # JSON:API 过滤/排序白名单
    __filterable__ = ["name", "node_type", "is_deleted", "parent_id", "mime_type", "created_at", "updated_at"]
    __sortable__   = ["name", "size_bytes", "created_at", "updated_at"]
    __selectable__ = [
        "id", "name", "node_type", "size_bytes", "mime_type",
        "parent_id", "is_deleted", "deleted_at", "storage_key",
        "created_by", "updated_by", "created_at", "updated_at",
    ]

    # 被 px_netdisk_shares 外键引用，必须声明删除依赖
    __delete_deps__ = [
        ("px_netdisk_shares", "node_id", "CASCADE_DELETE"),
    ]

    parent_id = Column(
        Integer,
        ForeignKey("px_netdisk_nodes.id", name="fk_netdisk_nodes_parent", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name        = Column(String(255), nullable=False)
    node_type   = Column(String(10), nullable=False)  # file | folder
    storage_key = Column(String(500), nullable=True)    # 仅 file: netdisk/{tenant_id}/{node_id}/{filename}
    size_bytes  = Column(BigInteger, default=0, nullable=False)
    mime_type   = Column(String(128), nullable=True)
    is_deleted  = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at  = Column(DateTime(timezone=True), nullable=True)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # 自引用关系
    children = relationship("FileNode", foreign_keys=[parent_id], lazy="noload")
    shares   = relationship("Share",    back_populates="node", lazy="noload", cascade="all, delete-orphan")

    def soft_delete(self) -> None:
        """软删除 — 移入回收站"""
        self.is_deleted = True
        self.deleted_at = utc_now()

    def restore(self) -> None:
        """从回收站还原"""
        self.is_deleted = False
        self.deleted_at = None

    @property
    def is_folder(self) -> bool:
        return self.node_type == NodeTypeEnum.FOLDER.value

    @property
    def is_file(self) -> bool:
        return self.node_type == NodeTypeEnum.FILE.value
