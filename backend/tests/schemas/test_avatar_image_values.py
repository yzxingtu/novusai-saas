import pytest
from pydantic import ValidationError

from app.schemas.system.admin import AdminUpdateProfileRequest, AdminUpdateRequest
from app.schemas.tenant.admin import (
    TenantAdminUpdateProfileRequest,
    TenantAdminUpdateRequest,
)
from app.schemas.tenant.user import (
    TenantUserProfileUpdateRequest,
    TenantUserUpdateRequest,
)


@pytest.mark.parametrize(
    "schema_cls",
    [
        AdminUpdateRequest,
        AdminUpdateProfileRequest,
        TenantAdminUpdateRequest,
        TenantAdminUpdateProfileRequest,
        TenantUserUpdateRequest,
        TenantUserProfileUpdateRequest,
    ],
)
def test_avatar_write_schemas_accept_canonical_attachment_ids(schema_cls) -> None:
    payload = schema_cls(avatar=" 42 ")
    assert payload.avatar == "42"

    payload_from_int = schema_cls(avatar=42)
    assert payload_from_int.avatar == "42"

    cleared = schema_cls(avatar="")
    assert cleared.avatar == ""


@pytest.mark.parametrize(
    "schema_cls",
    [
        AdminUpdateRequest,
        AdminUpdateProfileRequest,
        TenantAdminUpdateRequest,
        TenantAdminUpdateProfileRequest,
        TenantUserUpdateRequest,
        TenantUserProfileUpdateRequest,
    ],
)
@pytest.mark.parametrize(
    "avatar",
    [
        True,
        "0",
        "0042",
        "42.5",
        "/uploads/legacy-avatar.png",
        "/api/public/attachments/42/image",
        "https://cdn.example.test/avatar.png",
    ],
)
def test_avatar_write_schemas_reject_legacy_urls_and_noncanonical_ids(
    schema_cls,
    avatar,
) -> None:
    with pytest.raises(ValidationError, match="positive attachment ID"):
        schema_cls(avatar=avatar)
