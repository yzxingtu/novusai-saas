from pydantic import Field

from app.core.base_schema import BaseSchema


class AttachmentAccessUrlResponse(BaseSchema):
    attachment_id: int = Field(..., description="附件 ID")
    url: str = Field(..., description="访问 URL")
    expires_in: int = Field(..., description="有效期（秒）")
    preview: bool = Field(False, description="是否预览链接")


__all__ = ["AttachmentAccessUrlResponse"]
