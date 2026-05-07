from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.tenant import tenant_router


def _get_endpoint(path: str, method: str):
    for route in tenant_router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_tenant_resolve_assignment_returns_agent_payload() -> None:
    endpoint = _get_endpoint("/ai/agent-assignments/resolve/{feature_code}", "GET")

    db = AsyncMock()
    tenant_admin = SimpleNamespace(tenant_id=42)
    assignment = SimpleNamespace(
        feature_code="system.ai_writing",
        agent_id=9,
        config={"mode": "default"},
        is_active=True,
        agent=SimpleNamespace(name="Writer Agent", is_deleted=False),
    )
    service = AsyncMock()
    service.resolve_for_tenant = AsyncMock(return_value=assignment)

    with patch(
        "app.api.tenant.agent_assignments.AgentAssignmentService",
        return_value=service,
    ):
        response = await endpoint(
            feature_code="system.ai_writing",
            db=db,
            tenant_admin=tenant_admin,
        )

    service.resolve_for_tenant.assert_awaited_once_with("system.ai_writing", 42)
    assert response["code"] == 0
    assert response["data"] == {
        "feature_code": "system.ai_writing",
        "agent_id": 9,
        "agent_name": "Writer Agent",
        "config": {"mode": "default"},
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_tenant_resolve_assignment_returns_empty_payload_when_unassigned() -> (
    None
):
    endpoint = _get_endpoint("/ai/agent-assignments/resolve/{feature_code}", "GET")

    db = AsyncMock()
    tenant_admin = SimpleNamespace(tenant_id=42)
    service = AsyncMock()
    service.resolve_for_tenant = AsyncMock(return_value=None)

    with patch(
        "app.api.tenant.agent_assignments.AgentAssignmentService",
        return_value=service,
    ):
        response = await endpoint(
            feature_code="system.ai_writing",
            db=db,
            tenant_admin=tenant_admin,
        )

    service.resolve_for_tenant.assert_awaited_once_with("system.ai_writing", 42)
    assert response["code"] == 0
    assert response["data"] == {
        "feature_code": "system.ai_writing",
        "agent_id": None,
        "agent_name": None,
        "config": None,
        "is_active": False,
    }
