"""插件 license 选择与上下文查询稳定性的回归测试。 / Plugin license selection regression tests."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.base_model import utc_now
from app.plugins.context import PluginContext
from app.plugins.license import get_preferred_license_record
from app.plugins.manifest import PluginManifest


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.mark.asyncio
async def test_preferred_license_record_prefers_paid_active_over_trial(
) -> None:
    now = utc_now()
    trial = SimpleNamespace(
        id=10,
        license_type="trial",
        is_valid=True,
        activated_at=now,
        created_at=now,
        issued_at=now,
        expires_at=None,
        trial_expires_at=now + timedelta(days=5),
    )
    perpetual = SimpleNamespace(
        id=11,
        license_type="perpetual",
        is_valid=True,
        activated_at=now - timedelta(days=1),
        created_at=now - timedelta(days=1),
        issued_at=now - timedelta(days=1),
        expires_at=None,
        trial_expires_at=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([trial, perpetual]))

    record = await get_preferred_license_record(1, db)

    assert record is perpetual


@pytest.mark.asyncio
async def test_preferred_license_record_prefers_active_over_newer_expired(
) -> None:
    now = utc_now()
    expired_fixed = SimpleNamespace(
        id=20,
        license_type="fixed_term",
        is_valid=True,
        activated_at=now,
        created_at=now,
        issued_at=now,
        expires_at=now - timedelta(hours=1),
        trial_expires_at=None,
    )
    active_perpetual = SimpleNamespace(
        id=21,
        license_type="perpetual",
        is_valid=True,
        activated_at=now - timedelta(days=3),
        created_at=now - timedelta(days=3),
        issued_at=now - timedelta(days=3),
        expires_at=None,
        trial_expires_at=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([expired_fixed, active_perpetual]))

    record = await get_preferred_license_record(1, db)

    assert record is active_perpetual


@pytest.mark.asyncio
async def test_plugin_context_license_query_delegates_to_unified_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = PluginManifest(
        name="demo-plugin",
        version="1.0.0",
        display_name={"en": "Demo Plugin"},
        scope="all_tenants",
    )

    ctx = PluginContext(
        plugin_name="demo-plugin",
        manifest=manifest,
        db=AsyncMock(),
        granted_capabilities=[],
    )

    monkeypatch.setattr(
        "app.plugins.license.get_license_status_by_name",
        AsyncMock(return_value={"status": "active", "is_valid": True}),
    )

    status = await ctx.get_own_license_status()

    assert status == {"status": "active", "is_valid": True}
