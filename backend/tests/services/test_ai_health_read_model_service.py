"""Test type: behavioral
Scope: Admin AI health monitoring read model enrichment.
Mocked dependencies: fake DB execute result and monkeypatched Redis-backed failover read.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai.health_read_model_service import AIHealthReadModelService


class _FakeRowResult:
    def all(self):
        return [
            SimpleNamespace(id=10, icon="icon-a.png"),
            SimpleNamespace(id=20, icon=None),
        ]


class _FakeDB:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, _stmt):
        self.execute_calls += 1
        return _FakeRowResult()


@pytest.mark.asyncio
async def test_ai_health_read_model_enriches_provider_icons(monkeypatch) -> None:
    async def _fake_health_statuses():
        return [
            {"provider_id": 10, "provider_name": "Primary"},
            {"provider_id": 20, "provider_name": "Fallback"},
        ]

    monkeypatch.setattr(
        "app.services.ai.health_read_model_service.FailoverService.get_all_provider_health",
        _fake_health_statuses,
    )
    db = _FakeDB()

    statuses = await AIHealthReadModelService(db).list_provider_health_statuses()

    assert db.execute_calls == 1
    assert statuses == [
        {
            "provider_id": 10,
            "provider_name": "Primary",
            "provider_icon": "icon-a.png",
        },
        {"provider_id": 20, "provider_name": "Fallback", "provider_icon": None},
    ]
