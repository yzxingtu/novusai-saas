"""Test type: behavioral
Scope: admin/tenant conversation detail routes preserve diagnostic payloads.
Mocked dependencies: MonitoringService read model only; route response shaping runs real.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load_route_module(module_name: str, relative_path: str):
    spec = spec_from_file_location(module_name, BACKEND_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load route module: {relative_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


admin_conversations = _load_route_module(
    "test_admin_ai_conversations_route_module",
    "app/api/admin/ai_conversations.py",
)
tenant_conversations = _load_route_module(
    "test_tenant_conversations_route_module",
    "app/api/tenant/conversations.py",
)
admin_conversation_router = admin_conversations.router
tenant_conversation_router = tenant_conversations.router


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
                "family": "data_ops",
                "status": "pending",
                "allowed_tool_names": ["crm_lookup"],
            },
        ],
        "active_intent_id": "intent-2",
        "active_intent": {
            "intent_id": "intent-2",
            "family": "data_ops",
            "allowed_tool_names": ["crm_lookup"],
        },
        "allowed_tool_names": ["crm_lookup"],
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
                "retry_family": "data_ops",
                "allowed_tool_names": ["crm_lookup"],
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

    with patch.object(
        admin_conversations, "MonitoringService", return_value=monitoring
    ):
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
    assert diagnostics["retry_events"][0]["retry_family"] == "data_ops"
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

    with patch.object(
        tenant_conversations, "MonitoringService", return_value=monitoring
    ):
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
    assert diagnostics["retry_events"][0]["retry_family"] == "data_ops"
    assert diagnostics["partial_exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["provider_failure_kind"] == "provider_http_5xx"
