"""
租户存储配额模型
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    UniqueConstraint,
)

from app.core.base_model import TenantModel, utc_now


class Quota(TenantModel):
    __tablename__ = "px_netdisk_quotas"

    __filterable__ = ["tenant_id", "updated_at"]
    __sortable__   = ["quota_bytes", "used_bytes", "updated_at"]
    __selectable__ = ["id", "tenant_id", "quota_bytes", "used_bytes", "updated_at"]

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_netdisk_quotas_tenant"),
    )

    quota_bytes = Column(BigInteger, nullable=False, default=10 * 1024 ** 3)  # 默认 10 GB
    used_bytes  = Column(BigInteger, nullable=False, default=0)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    @property
    def free_bytes(self) -> int:
        return max(0, self.quota_bytes - self.used_bytes)

    @property
    def used_percent(self) -> float:
        if self.quota_bytes == 0:
            return 100.0
        return round(self.used_bytes / self.quota_bytes * 100, 2)

    def check_capacity(self, upload_size: int) -> bool:
        """返回 True 表示有足够空间"""
        return self.used_bytes + upload_size <= self.quota_bytes
