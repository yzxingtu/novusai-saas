"""Test type: structural
Scope: admin plugin contract helpers.
Real dependencies: PluginRuntimeAuditService import surface.
Mocked dependencies: audit report service return values.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.admin.plugin_admin_contracts import (
    build_plugin_runtime_audit_payload,
    resolve_plugin_audit_service,
)
from app.exceptions import NotFoundException
from app.services.system.plugin_runtime_audit_service import PluginRuntimeAuditService


class _Report:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self) -> dict:
        return dict(self._payload)


def test_resolve_plugin_audit_service_uses_runtime_audit_service() -> None:
    service = resolve_plugin_audit_service(AsyncMock())

    assert isinstance(service, PluginRuntimeAuditService)


@pytest.mark.asyncio
async def test_build_plugin_runtime_audit_payload_lists_runtime_reports() -> None:
    service = SimpleNamespace(
        list_plugin_audit_reports=AsyncMock(
            return_value=[
                _Report({"plugin_name": "alpha"}),
                _Report({"plugin_name": "beta"}),
            ]
        )
    )

    payload = await build_plugin_runtime_audit_payload(service, tenant_id=42)

    assert payload == {
        "items": [{"plugin_name": "alpha"}, {"plugin_name": "beta"}],
        "total": 2,
    }
    service.list_plugin_audit_reports.assert_awaited_once_with(
        plugin_id=None,
        tenant_id=42,
        limit=50,
    )


@pytest.mark.asyncio
async def test_build_plugin_runtime_audit_payload_fails_closed_for_missing_plugin() -> (
    None
):
    service = SimpleNamespace(list_plugin_audit_reports=AsyncMock(return_value=[]))

    with pytest.raises(NotFoundException):
        await build_plugin_runtime_audit_payload(service, plugin_id=7)

    service.list_plugin_audit_reports.assert_awaited_once_with(
        plugin_id=7,
        tenant_id=None,
        limit=1,
    )
