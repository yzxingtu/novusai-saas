from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.tenant.tenant_role_option_service import TenantAdminReadModelService


def _tenant_model(tenant_id: int, code: str) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=tenant_id,
        code=code,
        name=f"Tenant-{tenant_id}",
        contact_name=None,
        contact_phone=None,
        contact_email=None,
        is_active=True,
        plan_id=None,
        plan=None,
        quota=None,
        expires_at=None,
        remark=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_build_tenant_list_page_attaches_storage_stats_only_when_available(
    mock_db,
):
    service = TenantAdminReadModelService(mock_db)
    service._storage_quota_service.get_tenant_storage_stats_batch = AsyncMock(
        return_value={
            1: {
                "used_bytes": 128,
                "limit_bytes": 1024,
                "limit_gb": 1,
                "usage_percent": 12.5,
                "file_count": 4,
                "unlimited": False,
            },
            2: {},
        }
    )

    page = await service.build_tenant_list_page(
        items=[_tenant_model(1, "t-1"), _tenant_model(2, "t-2")],
        total=2,
        page=1,
        page_size=20,
    )

    assert page.total == 2
    assert page.page == 1
    assert page.page_size == 20
    assert page.items[0].storage_stats is not None
    assert page.items[0].storage_stats.used_bytes == 128
    assert page.items[1].storage_stats is None


@pytest.mark.asyncio
async def test_build_tenant_detail_always_attaches_storage_stats_payload(mock_db):
    service = TenantAdminReadModelService(mock_db)
    service._storage_quota_service.get_tenant_storage_stats = AsyncMock(return_value={})

    data = await service.build_tenant_detail(_tenant_model(9, "t-9"))

    assert data.id == 9
    assert data.storage_stats is not None
    assert data.storage_stats.used_bytes == 0
    assert data.storage_stats.file_count == 0
