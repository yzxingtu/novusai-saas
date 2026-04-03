from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class AttachmentAccessUrlResponse(BaseSchema):
    """附件访问 URL 响应 / Attachment access URL response"""

    attachment_id: int = Field(..., description="附件 ID")
    url: str = Field(..., description="访问 URL")
    expires_in: int = Field(..., description="有效期（秒）")
    preview: bool = Field(False, description="是否预览链接")


class AttachmentResponse(BaseSchema):
    """附件详情响应（管理端完整版，含内部存储字段） / Attachment detail response (admin full, with internal storage fields)"""

    id: int = Field(..., description="附件 ID")
    tenant_id: int = Field(..., description="企业 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    path: str = Field(..., description="存储路径")
    size: int = Field(..., description="文件大小(字节)")
    hash: str | None = Field(None, description="文件哈希")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    driver: str = Field(..., description="存储驱动")
    base_url: str = Field(..., description="文件访问基础URL")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    uploader_id: int | None = Field(None, description="上传者 ID")
    business_type: str | None = Field(None, description="业务类型")
    business_id: int | None = Field(None, description="业务 ID")
    meta: dict | None = Field(None, description="扩展元数据")
    preview_url: str | None = Field(None, description="带签名的预览 URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class AttachmentSafeResponse(BaseSchema):
    """附件安全响应（企业端/用户端，隐藏内部存储细节） / Attachment safe response (tenant/user, hides internal storage)"""

    id: int = Field(..., description="附件 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    size: int = Field(..., description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    uploader_id: int | None = Field(None, description="上传者 ID")
    business_type: str | None = Field(None, description="业务类型")
    business_id: int | None = Field(None, description="业务 ID")
    preview_url: str | None = Field(None, description="带签名的预览 URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class AttachmentListItem(BaseSchema):
    """附件列表项响应（管理端完整版） / Attachment list item (admin full)"""

    id: int = Field(..., description="附件 ID")
    tenant_id: int | None = Field(None, description="企业 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    path: str = Field(..., description="存储路径")
    size: int = Field(..., description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    driver: str = Field(..., description="存储驱动")
    base_url: str = Field(..., description="文件访问基础URL")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    preview_url: str | None = Field(None, description="带签名的预览 URL")
    created_at: datetime = Field(..., description="创建时间")


class AttachmentSafeListItem(BaseSchema):
    """附件列表项安全响应（企业端/用户端，隐藏内部存储细节） / Attachment list item safe (tenant/user, hides internal storage)"""

    id: int = Field(..., description="附件 ID")
    name: str = Field(..., description="文件名")
    original_name: str | None = Field(None, description="原始文件名")
    size: int = Field(..., description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME 类型")
    extension: str | None = Field(None, description="文件扩展名")
    visibility: str = Field(..., description="可见性")
    status: str = Field(..., description="状态")
    source: str | None = Field(None, description="上传来源")
    preview_url: str | None = Field(None, description="带签名的预览 URL")
    created_at: datetime = Field(..., description="创建时间")


class TenantStorageQuotaResponse(BaseSchema):
    """企业存储配额响应 / Tenant storage quota response"""

    used_bytes: int = Field(..., description="已使用存储空间（字节）")
    limit_bytes: int = Field(..., description="存储限制（字节），0 表示无限制")
    limit_gb: int = Field(..., description="存储限制（GB），0 表示无限制")
    remaining_bytes: int = Field(..., description="剩余存储空间（字节）")
    usage_percent: float = Field(..., description="使用率百分比")
    total_count: int = Field(..., description="附件总数")
    max_file_size_mb: int = Field(..., description="单文件大小限制（MB），0 表示无限制")
    unlimited: bool = Field(..., description="是否无限制")


# ==================== 上传相关 Schema / Upload-related Schemas ====================


class AttachmentUploadResponse(BaseSchema):
    """附件上传响应（管理端完整版） / Attachment upload response (admin full)"""

    attachment: AttachmentResponse = Field(..., description="附件信息")
    url: str = Field(..., description="访问 URL")
    used_bytes: int = Field(..., description="已使用存储空间（字节）")


class AttachmentSafeUploadResponse(BaseSchema):
    """附件上传响应（企业端安全版，隐藏内部存储细节） / Attachment upload response (tenant safe)"""

    attachment: AttachmentSafeResponse = Field(..., description="附件信息")
    url: str = Field(..., description="访问 URL")
    used_bytes: int = Field(..., description="已使用存储空间（字节）")


class ChunkUploadInitRequest(BaseSchema):
    """分片上传初始化请求 / Chunk upload init request"""

    filename: str = Field(..., min_length=1, max_length=255, description="文件名")
    total_size: int = Field(..., gt=0, description="文件总大小（字节）")
    chunk_size: int = Field(
        5 * 1024 * 1024, gt=0, description="分片大小（字节），默认 5MB"
    )
    mime_type: str | None = Field(None, description="MIME 类型")
    visibility: str = Field("private", description="可见性 (private/public)")
    business_type: str | None = Field(None, description="业务类型")
    business_id: int | None = Field(None, description="业务 ID")


class ChunkUploadInitResponse(BaseSchema):
    """分片上传初始化响应 / Chunk upload init response"""

    upload_id: str = Field(..., description="上传会话 ID")
    filename: str = Field(..., description="文件名")
    total_size: int = Field(..., description="文件总大小")
    chunk_size: int = Field(..., description="分片大小")
    chunk_count: int = Field(..., description="分片数量")
    uploaded_chunks: list[int] = Field(
        default_factory=list, description="已上传分片索引"
    )
    uploaded_bytes: int = Field(0, description="已上传字节数")
    progress: int = Field(0, description="上传进度百分比")


class ChunkUploadProgressResponse(BaseSchema):
    """分片上传进度响应 / Chunk upload progress response"""

    upload_id: str = Field(..., description="上传会话 ID")
    filename: str = Field(..., description="文件名")
    total_size: int = Field(..., description="文件总大小")
    chunk_size: int = Field(..., description="分片大小")
    chunk_count: int = Field(..., description="分片数量")
    uploaded_chunks: list[int] = Field(..., description="已上传分片索引")
    uploaded_bytes: int = Field(..., description="已上传字节数")
    progress: int = Field(..., description="上传进度百分比")


class AdminChunkUploadInitRequest(BaseSchema):
    """平台端分片上传初始化请求 / Admin chunk upload init request"""

    tenant_id: int = Field(0, ge=0, description="目标企业 ID，0 表示平台附件")
    filename: str = Field(..., min_length=1, max_length=255, description="文件名")
    total_size: int = Field(..., gt=0, description="文件总大小（字节）")
    chunk_size: int = Field(
        5 * 1024 * 1024, gt=0, description="分片大小（字节），默认 5MB"
    )
    mime_type: str | None = Field(None, description="MIME 类型")
    visibility: str = Field("private", description="可见性 (private/public)")
    business_type: str | None = Field(None, description="业务类型")
    business_id: int | None = Field(None, description="业务 ID")


class AttachmentPreflightRequest(BaseSchema):
    """附件预检请求（秒传检查） / Attachment preflight request (instant upload check)"""

    hash: str = Field(
        ...,
        min_length=10,
        max_length=128,
        description="文件哈希，格式: sha256:{hex_digest}",
    )
    filename: str = Field(..., min_length=1, max_length=255, description="文件名")
    size: int = Field(..., gt=0, description="文件大小（字节）")
    visibility: str = Field("private", description="可见性 (private/public)")


class AttachmentPreflightResponse(BaseSchema):
    """附件预检响应（管理端完整版） / Attachment preflight response (admin full)"""

    exists: bool = Field(..., description="文件是否已存在")
    attachment: AttachmentResponse | None = Field(None, description="已存在的附件信息")
    url: str | None = Field(None, description="已存在附件的访问 URL")
    used_bytes: int | None = Field(None, description="已使用存储空间（字节）")


class AttachmentSafePreflightResponse(BaseSchema):
    """附件预检响应（企业端安全版） / Attachment preflight response (tenant safe)"""

    exists: bool = Field(..., description="文件是否已存在")
    attachment: AttachmentSafeResponse | None = Field(
        None, description="已存在的附件信息"
    )
    url: str | None = Field(None, description="已存在附件的访问 URL")
    used_bytes: int | None = Field(None, description="已使用存储空间（字节）")


class BatchUploadItem(BaseSchema):
    """批量上传单文件结果（管理端完整版） / Batch upload single item (admin full)"""

    filename: str = Field(..., description="原始文件名")
    success: bool = Field(..., description="是否上传成功")
    attachment: AttachmentResponse | None = Field(
        None, description="附件信息（成功时）"
    )
    url: str | None = Field(None, description="访问 URL（成功时）")
    error: str | None = Field(None, description="错误信息（失败时）")


class BatchSafeUploadItem(BaseSchema):
    """批量上传单文件结果（企业端安全版） / Batch upload single item (tenant safe)"""

    filename: str = Field(..., description="原始文件名")
    success: bool = Field(..., description="是否上传成功")
    attachment: AttachmentSafeResponse | None = Field(
        None, description="附件信息（成功时）"
    )
    url: str | None = Field(None, description="访问 URL（成功时）")
    error: str | None = Field(None, description="错误信息（失败时）")


class BatchUploadResponse(BaseSchema):
    """批量上传响应（管理端完整版） / Batch upload response (admin full)"""

    items: list[BatchUploadItem] = Field(..., description="每个文件的上传结果")
    success_count: int = Field(..., description="成功数量")
    failure_count: int = Field(..., description="失败数量")
    used_bytes: int = Field(0, description="已使用存储空间（字节），企业端有效")


class BatchSafeUploadResponse(BaseSchema):
    """批量上传响应（企业端安全版） / Batch upload response (tenant safe)"""

    items: list[BatchSafeUploadItem] = Field(..., description="每个文件的上传结果")
    success_count: int = Field(..., description="成功数量")
    failure_count: int = Field(..., description="失败数量")
    used_bytes: int = Field(0, description="已使用存储空间（字节）")


__all__ = [
    "AttachmentAccessUrlResponse",
    "AttachmentResponse",
    "AttachmentSafeResponse",
    "AttachmentListItem",
    "AttachmentSafeListItem",
    "TenantStorageQuotaResponse",
    # 上传相关 / Upload
    "AttachmentPreflightRequest",
    "AttachmentPreflightResponse",
    "AttachmentSafePreflightResponse",
    "AttachmentUploadResponse",
    "AttachmentSafeUploadResponse",
    "BatchUploadItem",
    "BatchSafeUploadItem",
    "BatchUploadResponse",
    "BatchSafeUploadResponse",
    "ChunkUploadInitRequest",
    "ChunkUploadInitResponse",
    "ChunkUploadProgressResponse",
    "AdminChunkUploadInitRequest",
]
