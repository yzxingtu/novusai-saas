"""
文件分享记录模型
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.base_model import TenantModel, utc_now
from app.enums.base import LabeledStrEnum


class SharePermissionEnum(LabeledStrEnum):
    READ     = "read",     "只读"
    DOWNLOAD = "download", "可下载"


class Share(TenantModel):
    __tablename__ = "px_netdisk_shares"

    __filterable__ = ["is_active", "created_at", "expires_at", "node_id"]
    __sortable__   = ["created_at", "access_count", "expires_at"]
    __selectable__ = [
        "id", "node_id", "share_token", "permission",
        "expires_at", "access_count", "is_active",
        "created_by", "created_at",
    ]

    node_id = Column(
        Integer,
        ForeignKey("px_netdisk_nodes.id", name="fk_netdisk_shares_node", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    share_token   = Column(String(64), nullable=False, unique=True)   # secrets.token_urlsafe(32)
    password_hash = Column(String(128), nullable=True)                # bcrypt hash，None=无密码
    permission    = Column(String(20), nullable=False, default=SharePermissionEnum.DOWNLOAD.value)
    expires_at    = Column(DateTime(timezone=True), nullable=True)    # None=永不过期
    access_count  = Column(Integer, default=0, nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False, index=True)
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    node = relationship("FileNode", back_populates="shares", lazy="noload")

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at

    def increment_access(self) -> None:
        self.access_count = (self.access_count or 0) + 1
