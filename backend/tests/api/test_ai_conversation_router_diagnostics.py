from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.admin.ai_conversations import router as admin_conversation_router
from app.api.tenant.conversations import router as tenant_conversation_router


def _get_endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


def _mock_request_with_all_permissions() -> MagicMock:
    request = MagicMock()
    request.state.user_permissions = {"*"}
    return request


def _conversation_detail_diagnostics_payload() -> dict:
    diagnostics = {
        "execution_path": "deep",
        "intent_plan": [
            {
                "intent_id": "intent-1",
                "family": "weather",
                "status": "completed",
            },
            {
                "intent_id": "intent-2",
                "family": "page_ops",
                "status": "pending",
                "allowed_tool_names": ["get_page_context"],
            },
        ],
        "active_intent_id": "intent-2",
        "active_intent": {
            "intent_id": "intent-2",
            "family": "page_ops",
            "allowed_tool_names": ["get_page_context"],
        },
        "allowed_tool_names": ["get_page_context"],
        "budget": {
            "status": "exited",
            "exit_reason": "retry_budget_exhausted",
            "limits": {"max_retry_per_intent": 2},
            "usage": {"retry_per_intent": {"intent-2": 2}},
        },
        "retry_events": [
            {
                "action": "retry_intent",
                "target_intent_id": "intent-2",
                "retry_family": "page_ops",
                "allowed_tool_names": ["get_page_context"],
            }
        ],
        "partial_exit_reason": "retry_budget_exhausted",
        "provider_failure_kind": "provider_http_5xx",
    }
    return {
        "id": 666,
        "tenant_id": 11,
        "title": "thread",
        "status": "active",
        "message_count": 3,
        "total_tokens": 120,
        "total_cost": 0.8,
        "call_count": 2,
        "context_diagnostics": diagnostics,
        "last_run_summary": diagnostics,
        "message_list": [{"role": "user", "content": "hello"}],
        "call_trace": [],
    }


@pytest.mark.asyncio
async def test_admin_conversation_detail_route_keeps_diagnostics_fields() -> None:
    endpoint = _get_endpoint(
        admin_conversation_router,
        "/ai/conversations/{conversation_id}",
        "GET",
    )

    db = AsyncMock()
    request = _mock_request_with_all_permissions()
    admin = SimpleNamespace(id=1)
    payload = _conversation_detail_diagnostics_payload()
    monitoring = MagicMock()
    monitoring.admin_scope.return_value = "admin_scope"
    monitoring.get_conversation_detail = AsyncMock(return_value=payload)

    with patch("app.api.admin.ai_conversations.MonitoringService", return_value=monitoring):
        response = await endpoint(
            request=request,
            db=db,
            conversation_id=666,
            admin=admin,
            message_skip=0,
            message_limit=50,
        )

    assert response["code"] == 0
    diagnostics = response["data"]["context_diagnostics"]
    assert diagnostics["execution_path"] == "deep"
    assert diagnostics["intent_plan"][1]["intent_id"] == "intent-2"
    assert diagnostics["budget"]["exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["retry_events"][0]["retry_family"] == "page_ops"
    assert diagnostics["partial_exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["provider_failure_kind"] == "provider_http_5xx"


@pytest.mark.asyncio
async def test_tenant_conversation_detail_route_keeps_diagnostics_fields() -> None:
    endpoint = _get_endpoint(
        tenant_conversation_router,
        "/ai/conversations/{conversation_id}",
        "GET",
    )

    db = AsyncMock()
    request = _mock_request_with_all_permissions()
    tenant_admin = SimpleNamespace(tenant_id=11)
    payload = _conversation_detail_diagnostics_payload()
    monitoring = MagicMock()
    monitoring.tenant_scope.return_value = "tenant_scope"
    monitoring.get_conversation_detail = AsyncMock(return_value=payload)

    with patch("app.api.tenant.conversations.MonitoringService", return_value=monitoring):
        response = await endpoint(
            request=request,
            db=db,
            conversation_id=666,
            tenant_admin=tenant_admin,
            message_skip=0,
            message_limit=50,
        )

    assert response["code"] == 0
    diagnostics = response["data"]["context_diagnostics"]
    assert diagnostics["execution_path"] == "deep"
    assert diagnostics["intent_plan"][1]["intent_id"] == "intent-2"
    assert diagnostics["budget"]["exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["retry_events"][0]["retry_family"] == "page_ops"
    assert diagnostics["partial_exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["provider_failure_kind"] == "provider_http_5xx"
