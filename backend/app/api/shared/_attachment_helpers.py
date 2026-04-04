"""Shared attachment API helpers. / 附件 API 共享辅助。"""

from __future__ import annotations

from typing import Any, Protocol

from fastapi.responses import RedirectResponse, Response

from app.configs.service import PLATFORM_TENANT_ID, ConfigService
from app.services.tenant.attachment_download_service import AttachmentDownloadService


class AttachmentAccessService(Protocol):
    async def build_access_url(
        self,
        attachment: Any,
        *,
        expires: int,
        preview: bool,
    ) -> dict[str, Any]: ...

    async def get_attachment(self, attachment_id: int) -> Any: ...
    async def get_download_response(
        self, attachment: Any, *, preview: bool
    ) -> Response: ...
    async def get_redirect_url(
        self,
        attachment: Any,
        *,
        expires: int,
        preview: bool,
    ) -> str: ...
    async def record_download(self, attachment: Any) -> None: ...


def normalize_attachment_hash(raw_hash: str) -> str:
    """Normalize sha256-prefixed hashes received from preflight clients."""
    return raw_hash[7:] if raw_hash.startswith("sha256:") else raw_hash


async def resolve_attachment_default_visibility(config_service: ConfigService) -> str:
    """Resolve the platform-level default visibility for attachment uploads."""
    visibility = await config_service.get_platform_config(
        "platform_storage_default_visibility",
        default="private",
    )
    return str(visibility or "private")


async def resolve_attachment_upload_rules(
    config_service: ConfigService,
    *,
    tenant_id: int | None = None,
) -> dict[str, int | str]:
    """Resolve upload rules with tenant fallback to platform defaults."""
    allowed = ""
    denied = ""
    if tenant_id is not None:
        allowed = await config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_allowed_extensions",
            default="",
        )
        denied = await config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_denied_extensions",
            default="",
        )

    if not allowed:
        allowed = await config_service.get_platform_config(
            "platform_storage_allowed_extensions",
            default="",
        )
    if not denied:
        denied = await config_service.get_platform_config(
            "platform_storage_denied_extensions",
            default="",
        )

    max_size = await config_service.get_platform_config(
        "platform_storage_max_file_size_mb",
        default=100,
    )

    return {
        "allowed_extensions": str(allowed) if allowed else "",
        "denied_extensions": str(denied) if denied else "",
        "max_file_size_mb": int(max_size) if max_size else 100,
    }


def with_attachment_preview_url(
    data: dict[str, Any],
    *,
    tenant_id: int | None,
) -> dict[str, Any]:
    """Inject preview_url into serialized attachment payloads."""
    resolved_tenant_id = (
        tenant_id
        if tenant_id is not None
        else data.get("tenant_id", PLATFORM_TENANT_ID)
    )
    data["preview_url"] = AttachmentDownloadService.build_preview_url(
        attachment_id=data["id"],
        tenant_id=resolved_tenant_id,
        visibility=data.get("visibility", "private"),
    )
    return data


async def build_attachment_access_payload(
    service: AttachmentAccessService,
    *,
    attachment_id: int,
    expires: int,
    preview: bool,
) -> dict[str, Any]:
    """Build signed preview/download URL payload for attachment access endpoints."""
    attachment = await service.get_attachment(attachment_id)
    return await service.build_access_url(
        attachment,
        expires=expires,
        preview=preview,
    )


async def build_attachment_delivery_response(
    service: AttachmentAccessService,
    *,
    attachment_id: int,
    expires: int,
    preview: bool,
) -> RedirectResponse | Response:
    """Return either a local-stream response or a redirect for attachment delivery."""
    attachment = await service.get_attachment(attachment_id)
    if attachment.driver == "local":
        await service.record_download(attachment)
        return await service.get_download_response(attachment, preview=preview)
    url = await service.get_redirect_url(
        attachment,
        expires=expires,
        preview=preview,
    )
    return RedirectResponse(url=url)
