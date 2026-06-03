from types import SimpleNamespace

from app.api.user.attachments import _can_user_access_attachment


def _attachment(**overrides):
    defaults = {
        "source": "tenant_user",
        "uploader_id": 7,
        "visibility": "private",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _user(**overrides):
    defaults = {
        "id": 7,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_user_attachment_access_allows_public_attachment():
    assert _can_user_access_attachment(
        _attachment(visibility="public", source="tenant_admin", uploader_id=99),
        _user(id=7),
    )


def test_user_attachment_access_allows_own_private_upload():
    assert _can_user_access_attachment(
        _attachment(source="tenant_user", uploader_id=7, visibility="private"),
        _user(id=7),
    )


def test_user_attachment_access_rejects_other_user_private_upload():
    assert not _can_user_access_attachment(
        _attachment(source="tenant_user", uploader_id=8, visibility="private"),
        _user(id=7),
    )


def test_user_attachment_access_rejects_tenant_admin_private_attachment():
    assert not _can_user_access_attachment(
        _attachment(source="tenant_admin", uploader_id=7, visibility="private"),
        _user(id=7),
    )
