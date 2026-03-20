"""PeriodicTaskService：统一作用域字段约束 / owner_tenant_id strict-zero."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import BusinessException
from app.services.system.periodic_task_service import PeriodicTaskService


@pytest.mark.asyncio
async def test_before_create_rejects_deprecated_tenant_id() -> None:
    db = AsyncMock()
    svc = PeriodicTaskService(db)
    svc.repo.get_by_name = AsyncMock(return_value=None)

    with pytest.raises(BusinessException) as exc:
        await svc._before_create(
            {
                "name": "pt_scope_test_create",
                "tenant_id": 99,
                "scope": "global_shared",
            }
        )
    msg = str(exc.value.message).lower()
    assert "tenant_id" in msg or "owner_tenant_id" in msg


@pytest.mark.asyncio
async def test_before_update_rejects_deprecated_tenant_id() -> None:
    db = AsyncMock()
    svc = PeriodicTaskService(db)
    svc.get_by_id = AsyncMock(
        return_value=MagicMock(is_editable=True, is_locked=False)
    )

    with pytest.raises(BusinessException):
        await svc._before_update(1, {"tenant_id": 5})
