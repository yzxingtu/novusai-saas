from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class AttachmentAccessUrlResponse(BaseSchema):
    """附件访问 URL 响应"""
    attachment_id: int = Field(..., description="附件 ID")
    url: str = Field(..., description="访问 URL")
    expires_in: int = Field(..., description="有效期（秒）")
    preview: bool = Field(False, description="是否预览链接")


class AttachmentResponse(BaseSchema):
    """附件详情响应"""
    id: int = Field(..., description="附件 ID")
    tenant_id: int = Field(..., description="租户 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    path: str = Field(..., description="存储路径")
    size: int = Field(..., description="文件大小(字节)")
    hash: str | None = Field(None, description="文件哈希")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    driver: str = Field(..., description="存储驱动")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    uploader_id: int | None = Field(None, description="上传者 ID")
    business_type: str | None = Field(None, description="业务类型")
    business_id: int | None = Field(None, description="业务 ID")
    meta: dict | None = Field(None, description="扩展元数据")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class AttachmentListItem(BaseSchema):
    """附件列表项响应（精简字段）"""
    id: int = Field(..., description="附件 ID")
    tenant_id: int = Field(..., description="租户 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    size: int = Field(..., description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    driver: str = Field(..., description="存储驱动")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    created_at: datetime = Field(..., description="创建时间")


class TenantStorageQuotaResponse(BaseSchema):
    """租户存储配额响应"""
    used_bytes: int = Field(..., description="已使用存储空间（字节）")
    limit_bytes: int = Field(..., description="存储限制（字节），0 表示无限制")
    limit_gb: int = Field(..., description="存储限制（GB），0 表示无限制")
    remaining_bytes: int = Field(..., description="剩余存储空间（字节）")
    usage_percent: float = Field(..., description="使用率百分比")
    total_count: int = Field(..., description="附件总数")
    max_file_size_mb: int = Field(..., description="单文件大小限制（MB），0 表示无限制")
    unlimited: bool = Field(..., description="是否无限制")


__all__ = [
    "AttachmentAccessUrlResponse",
    "AttachmentResponse",
    "AttachmentListItem",
    "TenantStorageQuotaResponse",
]
