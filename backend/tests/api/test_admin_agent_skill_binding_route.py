from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.admin.agents import AdminAgentController
from app.schemas.ai.agent_skill_grant import AgentSkillGrantUpdate


def _get_endpoint(path: str, method: str):
    router = AdminAgentController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_update_skill_binding_uses_grant_id_keyword() -> None:
    endpoint = _get_endpoint("/ai/agents/{agent_id}/skills/{binding_id}", "PUT")

    db = AsyncMock()
    db.commit = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    agent = SimpleNamespace(id=59, owner_tenant_id=None)
    updated = SimpleNamespace(
        id=16,
        agent_id=59,
        skill=None,
        skill_id=51,
        enabled=True,
        config_override=None,
        sort_order=0,
        default_consent_mode="ask",
        capability_consent_overrides=None,
    )

    admin_agent_service = MagicMock()
    admin_agent_service.get_by_id = AsyncMock(return_value=agent)

    grant_service = MagicMock()
    grant_service.update_grant = AsyncMock(return_value=updated)
    grant_service.serialize_grant_public = MagicMock(return_value={"id": 16})

    with patch(
        "app.api.admin.agents.AdminAgentService",
        return_value=admin_agent_service,
    ), patch(
        "app.api.admin.agents.AgentSkillGrantService",
        return_value=grant_service,
    ):
        response = await endpoint(
            request,
            db,
            59,
            16,
            AgentSkillGrantUpdate(default_consent_mode="ask"),
            admin,
        )

    grant_service.update_grant.assert_awaited_once_with(
        grant_id=16,
        data={"default_consent_mode": "ask"},
    )
    db.commit.assert_awaited_once()
    assert response["code"] == 0
    assert response["data"] == {"id": 16}
