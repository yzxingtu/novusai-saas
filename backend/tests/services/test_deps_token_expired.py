"""Tests for deps.py token_expired vs token_invalid differentiation.

Verifies that expired tokens raise TokenExpiredException (code=4011)
while other invalid tokens raise HTTPException (code=4010 via handler).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import TokenExpiredError
from app.exceptions.base import TokenExpiredException


@pytest.fixture()
def _fake_db():
    """Minimal async DB session stub."""
    db = AsyncMock()
    result = AsyncMock()
    admin = SimpleNamespace(id=1, is_active=True, is_super=False, is_deleted=False)
    result.scalar_one_or_none.return_value = admin
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_get_current_admin_raises_token_expired(_fake_db):
    """Expired token should raise TokenExpiredException (code 4011)."""
    from app.core.deps import get_current_admin

    with patch(
        "app.core.deps.verify_token_with_scope",
        new_callable=AsyncMock,
        side_effect=TokenExpiredError(),
    ):
        with pytest.raises(TokenExpiredException) as exc_info:
            await get_current_admin(db=_fake_db, token="expired-jwt")
        assert exc_info.value.code == 4011
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_admin_raises_http_on_invalid(_fake_db):
    """Invalid (non-expired) token should raise HTTPException (401)."""
    from fastapi import HTTPException

    from app.core.deps import get_current_admin

    with patch(
        "app.core.deps.verify_token_with_scope",
        new_callable=AsyncMock,
        return_value=(None, None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(db=_fake_db, token="bad-jwt")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_admin_missing_token(_fake_db):
    """Missing token should raise HTTPException (401)."""
    from fastapi import HTTPException

    from app.core.deps import get_current_admin

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(db=_fake_db, token=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_tenant_admin_raises_token_expired(_fake_db):
    """Expired token on tenant admin endpoint → TokenExpiredException."""
    from app.core.deps import get_current_tenant_admin

    with patch(
        "app.core.deps.verify_token_with_scope",
        new_callable=AsyncMock,
        side_effect=TokenExpiredError(),
    ):
        with pytest.raises(TokenExpiredException) as exc_info:
            await get_current_tenant_admin(db=_fake_db, token="expired-jwt")
        assert exc_info.value.code == 4011


@pytest.mark.asyncio
async def test_get_current_tenant_user_raises_token_expired(_fake_db):
    """Expired token on tenant user endpoint → TokenExpiredException."""
    from app.core.deps import get_current_tenant_user

    with patch(
        "app.core.deps.verify_token_with_scope",
        new_callable=AsyncMock,
        side_effect=TokenExpiredError(),
    ):
        with pytest.raises(TokenExpiredException) as exc_info:
            await get_current_tenant_user(db=_fake_db, token="expired-jwt")
        assert exc_info.value.code == 4011
