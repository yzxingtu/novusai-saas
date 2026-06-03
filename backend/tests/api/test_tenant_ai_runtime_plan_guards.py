"""
Test type: behavioral
Regression for: tenant plan AI entitlement bypass through direct tenant AI APIs.
Scope: Tenant AI gateway and global AgentChat routes must enforce the same
account/plan availability guard before constructing downstream AI services.
Mock strategy: Dependencies and downstream services are sentinels; the guard
decision is not mocked as allowed in the rejection cases.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_tenant_admin, get_db
from app.exceptions import AppException, AuthorizationException
from app.services.ai.account_ai_access_service import (
    TENANT_PLAN_AI_DISABLED_CODE,
    TENANT_PLAN_AI_DISABLED_REASON,
)
from app.services.tenant.quota_service import QuotaCheckResult


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parent.parent.parent / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module {relative_path}")
    spec.loader.exec_module(module)
    return module


def _register_app_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


def _tenant_admin() -> SimpleNamespace:
    return SimpleNamespace(
        ai_enabled=True,
        id=7,
        is_active=True,
        is_owner=True,
        tenant_id=5,
        tenant_plan_ai_enabled=False,
    )


class _RejectingAccessService:
    def __init__(self, _db):
        pass

    async def require_tenant_admin_ai_access(self, _tenant_admin) -> None:
        raise AuthorizationException(
            message="tenant plan disabled",
            code=TENANT_PLAN_AI_DISABLED_CODE,
            extra={
                "reason": TENANT_PLAN_AI_DISABLED_REASON,
                "feature": "ai_chat",
            },
        )


class _AllowingAccessService:
    def __init__(self, _db):
        pass

    async def require_tenant_admin_ai_access(self, _tenant_admin) -> None:
        return None


class _RejectingQuotaService:
    @classmethod
    async def check_api_quota_for_tenant_id(cls, _db, _tenant_id):
        return QuotaCheckResult(
            allowed=False,
            current=10,
            limit=10,
            remaining=0,
            message="monthly api quota exhausted",
        )


class _UnexpectedQuotaService:
    @classmethod
    async def check_api_quota_for_tenant_id(cls, _db, _tenant_id):
        raise AssertionError("quota should not be checked after AI access denial")


def _build_app(router) -> FastAPI:
    app = FastAPI()
    _register_app_exception_handler(app)

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_admin():
        return _tenant_admin()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_admin] = override_tenant_admin
    app.include_router(router)
    return app


@pytest.mark.parametrize(
    ("path", "payload"),
    (
        (
            "/ai/gateway/chat",
            {
                "model_code": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
            },
        ),
        (
            "/ai/gateway/chat/stream",
            {
                "model_code": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
            },
        ),
        (
            "/ai/gateway/embedding",
            {
                "model_code": "openai:text-embedding-3-small",
                "texts": ["hello"],
            },
        ),
    ),
)
def test_tenant_ai_gateway_rejects_plan_disabled_before_internal_service(
    path,
    payload,
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/tenant/ai_gateway.py",
        f"test_tenant_ai_gateway_plan_guard_{path.replace('/', '_')}",
    )
    monkeypatch.setattr(module.TenantAIGatewayController, "_instance", None)
    monkeypatch.setattr(module.TenantAIGatewayController, "_router", None)

    service_events: list[str] = []

    class UnexpectedInternalAIService:
        def __init__(self, *_args):
            service_events.append("constructed")

    monkeypatch.setattr(module, "AccountAIAccessService", _RejectingAccessService)
    monkeypatch.setattr(module, "QuotaService", _UnexpectedQuotaService)
    monkeypatch.setattr(module, "InternalAIService", UnexpectedInternalAIService)

    app = _build_app(module.TenantAIGatewayController.get_router())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=payload)

    body = response.json()
    assert response.status_code == 403
    assert body["code"] == TENANT_PLAN_AI_DISABLED_CODE
    assert body["reason"] == TENANT_PLAN_AI_DISABLED_REASON
    assert body["feature"] == "ai_chat"
    assert service_events == []


def test_tenant_ai_gateway_rejects_monthly_api_quota_before_internal_service(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/tenant/ai_gateway.py",
        "test_tenant_ai_gateway_monthly_quota_guard",
    )
    monkeypatch.setattr(module.TenantAIGatewayController, "_instance", None)
    monkeypatch.setattr(module.TenantAIGatewayController, "_router", None)

    service_events: list[str] = []

    class UnexpectedInternalAIService:
        def __init__(self, *_args):
            service_events.append("constructed")

    monkeypatch.setattr(module, "AccountAIAccessService", _AllowingAccessService)
    monkeypatch.setattr(module, "QuotaService", _RejectingQuotaService)
    monkeypatch.setattr(module, "InternalAIService", UnexpectedInternalAIService)

    app = _build_app(module.TenantAIGatewayController.get_router())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/ai/gateway/chat",
            json={
                "model_code": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    body = response.json()
    assert response.status_code == 422
    assert body["message"] == "monthly api quota exhausted"
    assert service_events == []


def test_tenant_agent_chat_rejects_plan_disabled_before_agent_or_chat_service(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/tenant/agent_chat.py",
        "test_tenant_agent_chat_plan_guard",
    )
    monkeypatch.setattr(module.TenantAgentChatController, "_instance", None)
    monkeypatch.setattr(module.TenantAgentChatController, "_router", None)

    service_events: list[str] = []

    class UnexpectedAgentService:
        def __init__(self, *_args):
            service_events.append("agent_service_constructed")

    class UnexpectedAgentChatService:
        def __init__(self, *_args):
            service_events.append("chat_service_constructed")

    monkeypatch.setattr(module, "AccountAIAccessService", _RejectingAccessService)
    monkeypatch.setattr(module, "AgentService", UnexpectedAgentService)
    monkeypatch.setattr(module, "AgentChatService", UnexpectedAgentChatService)

    app = _build_app(module.TenantAgentChatController.get_router())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/ai/agent-chat/42/chat/stream",
            json={"message": "[Task Instructions]\n续写富文本内容"},
        )

    body = response.json()
    assert response.status_code == 403
    assert body["code"] == TENANT_PLAN_AI_DISABLED_CODE
    assert body["reason"] == TENANT_PLAN_AI_DISABLED_REASON
    assert body["feature"] == "ai_chat"
    assert service_events == []


def test_tenant_agent_batch_rejects_plan_disabled_before_dispatch(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/tenant/_agent_batch.py",
        "test_tenant_agent_batch_plan_guard",
    )

    monkeypatch.setattr(module, "AccountAIAccessService", _RejectingAccessService)
    monkeypatch.setattr(module, "QuotaService", _UnexpectedQuotaService)

    app = _build_app(module.router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/42/batch",
            json={"items": [{"topic": "one"}, {"topic": "two"}]},
        )

    body = response.json()
    assert response.status_code == 403
    assert body["code"] == TENANT_PLAN_AI_DISABLED_CODE
    assert body["reason"] == TENANT_PLAN_AI_DISABLED_REASON
    assert body["feature"] == "ai_chat"


def test_tenant_agent_batch_rejects_monthly_quota_for_all_items_before_dispatch(
    monkeypatch,
) -> None:
    module = _load_module(
        "app/api/tenant/_agent_batch.py",
        "test_tenant_agent_batch_monthly_quota_guard",
    )
    quota_calls: list[int] = []

    class _RejectingBatchQuotaService:
        @classmethod
        async def check_api_quota_for_tenant_id(
            cls,
            _db,
            _tenant_id,
            additional: int = 1,
        ):
            quota_calls.append(additional)
            return QuotaCheckResult(
                allowed=False,
                current=9,
                limit=10,
                remaining=1,
                message="monthly api quota exhausted",
            )

    monkeypatch.setattr(module, "AccountAIAccessService", _AllowingAccessService)
    monkeypatch.setattr(module, "QuotaService", _RejectingBatchQuotaService)

    app = _build_app(module.router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/42/batch",
            json={"items": [{"topic": "one"}, {"topic": "two"}]},
        )

    body = response.json()
    assert response.status_code == 422
    assert body["message"] == "monthly api quota exhausted"
    assert quota_calls == [2]
