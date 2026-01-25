from fastapi import Query
from fastapi.responses import RedirectResponse

from app.core.deps import DbSession
from app.rbac.decorators import public
from app.services.tenant.attachment_download_service import AttachmentDownloadService

from fastapi import APIRouter

router = APIRouter(prefix="/attachments", tags=["公开附件"])


@router.get("/{attachment_id}/access", summary="访问附件")
@public
async def access_attachment(
    attachment_id: int,
    db: DbSession,
    token: str | None = None,
    preview: bool = Query(False),
):
    service = AttachmentDownloadService(db)
    attachment = await service.get_attachment(attachment_id)
    await service.validate_access(attachment, token)
    if attachment.driver == "local":
        await service.record_download(attachment)
        return await service.get_download_response(attachment, preview=preview)
    url = await service.get_redirect_url(attachment, expires=3600, preview=preview)
    return RedirectResponse(url=url)


__all__ = ["router"]
