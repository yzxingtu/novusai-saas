"""
Test type: behavioral
Regression for: BUG-2026-05-02-AI-ACCOUNT-002
Scope: AI chat account/tenant-plan availability guards on live chat routes.
Mock strategy: FastAPI dependencies and downstream services are replaced with
sentinels so the route guard must produce the 403; the test does not mock the
guard decision or successful response.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.deps import (
    get_current_active_admin,
    get_current_active_tenant_admin,
    get_current_active_tenant_user,
    get_db,
)
from app.exceptions import AppException
from app.services.ai.account_ai_access_service import AccountAIAccessService


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _DBExecuteResult:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = list(scalars or [])

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _ScalarsResult(self._scalars)


class _QueuedDB:
    def __init__(self, *, get_result=None, execute_results=None):
        self._get_result = get_result
        self._execute_results = list(execute_results or [])

    async def get(self, *_args):
        return self._get_result

    async def execute(self, *_args):
        if not self._execute_results:
            raise AssertionError("Unexpected execute call")
        return self._execute_results.pop(0)


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parent.parent / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module {relative_path}")
    spec.loader.exec_module(module)
    return module


def _safe_module_name(prefix: str, method: str, path: str) -> str:
    return (
        f"{prefix}_{method}_{path}".replace("/", "_")
        .replace("-", "_")
        .replace("{", "_")
        .replace("}", "_")
    )


def _register_app_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


def _chat_payload() -> dict[str, str]:
    return {"message": "hello"}


def _route_payload() -> dict[str, str]:
    return {"message": "hello"}


def _title_payload() -> dict[str, str]:
    return {"title": "renamed"}


class _ChatResult:
    def model_dump(self) -> dict[str, object]:
        return {
            "conversation_id": 11,
            "duration_ms": 4,
            "message": "ok",
            "tool_calls": [],
            "total_tokens": 2,
        }


_ADMIN_DISABLED_ROUTE_CASES = (
    ("post", "/ai/agent-chat/42/chat", _chat_payload()),
    ("post", "/ai/agent-chat/42/chat/stream", _chat_payload()),
    ("post", "/ai/agent-chat/route", _route_payload()),
    ("get", "/ai/agent-chat/conversations", None),
    ("get", "/ai/agent-chat/conversations/11", None),
    ("patch", "/ai/agent-chat/conversations/11", _title_payload()),
    ("delete", "/ai/agent-chat/conversations/11", None),
    ("get", "/ai/agent-chat/conversations/11/memory-state", None),
    ("delete", "/ai/agent-chat/conversations/11/memory-state", None),
    ("post", "/ai/agent-chat/conversations/11/compact", None),
    ("get", "/ai/agent-chat/conversations/11/timeline", None),
)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    _ADMIN_DISABLED_ROUTE_CASES,
    ids=[f"{method.upper()} {path}" for method, path, _ in _ADMIN_DISABLED_ROUTE_CASES],
)
def test_admin_ai_chat_rejects_account_disabled_before_chat_surfaces(
    method,
    path,
    json_body,
    monkeypatch,
) -> None:
    admin_module = _load_module(
        "app/api/admin/ai_agent_chat.py",
        _safe_module_name("test_admin_ai_guard_module", method, path),
    )
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_instance", None)
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_router", None)

    service_events: list[str] = []

    class SentinelAgentChatService:
        def __init__(self, *_args):
            service_events.append("constructed")

        async def chat(self, **_kwargs):
            service_events.append("chat")
            return _ChatResult()

        async def stream_chat(self, **_kwargs):
            service_events.append("stream_chat")
            return JSONResponse(content={})

    class SentinelConversationService:
        def __init__(self, *_args):
            service_events.append("conversation_constructed")

        async def __getattr__(self, name):
            service_events.append(f"conversation_{name}")
            return None

    monkeypatch.setattr(
        admin_module,
        "PermissionService",
        lambda _db: SimpleNamespace(
            get_admin_permissions=AsyncMock(return_value=["*"])
        ),
    )
    monkeypatch.setattr(admin_module, "AgentChatService", SentinelAgentChatService)
    monkeypatch.setattr(
        admin_module, "ConversationService", SentinelConversationService
    )

    async def sentinel_route(*_args, **_kwargs):
        service_events.append("handle_route")
        return JSONResponse(content={})

    monkeypatch.setattr(admin_module, "handle_route", sentinel_route)

    app = FastAPI()
    _register_app_exception_handler(app)

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    app.include_router(admin_module.AdminAgentChatController.get_router())

    async def override_db():
        yield SimpleNamespace()

    async def override_admin():
        return SimpleNamespace(
            ai_enabled=False,
            id=1,
            is_active=True,
            is_super=True,
            org_node_id=101,
            username="disabled_admin",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin

    with TestClient(app, raise_server_exceptions=False) as client:
        request_fn = getattr(client, method)
        response = request_fn(path, json=json_body) if json_body else request_fn(path)

    payload = response.json()
    assert response.status_code == 403
    assert payload["code"] == 4032
    assert payload["reason"] == "account_ai_disabled"
    assert payload["feature"] == "ai_chat"
    assert service_events == []


_TENANT_DISABLED_ROUTE_CASES = (
    ("post", "/ai/agent-chat/42/chat", _chat_payload()),
    ("post", "/ai/agent-chat/42/chat/stream", _chat_payload()),
    ("post", "/ai/agent-chat/route", _route_payload()),
    ("get", "/ai/agent-chat/conversations", None),
    ("get", "/ai/agent-chat/conversations/11", None),
    ("get", "/ai/agent-chat/conversations/11/compact", None),
    ("get", "/ai/agent-chat/conversations/11/timeline", None),
    ("patch", "/ai/agent-chat/conversations/11", _title_payload()),
    ("delete", "/ai/agent-chat/conversations/11", None),
    ("get", "/ai/agent-chat/conversations/11/memory-state", None),
    ("delete", "/ai/agent-chat/conversations/11/memory-state", None),
    ("post", "/ai/agent-chat/conversations/11/compact", None),
)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    _TENANT_DISABLED_ROUTE_CASES,
    ids=[
        f"{method.upper()} {path}" for method, path, _ in _TENANT_DISABLED_ROUTE_CASES
    ],
)
def test_tenant_owner_ai_chat_rejects_account_disabled_before_agent_services(
    method,
    path,
    json_body,
    monkeypatch,
) -> None:
    tenant_module = _load_module(
        "app/api/tenant/agent_chat.py",
        _safe_module_name("test_tenant_ai_account_guard_module", method, path),
    )
    monkeypatch.setattr(tenant_module.TenantAgentChatController, "_instance", None)
    monkeypatch.setattr(tenant_module.TenantAgentChatController, "_router", None)

    service_events: list[str] = []

    class SentinelAgentService:
        def __init__(self, *_args):
            service_events.append("agent_access_constructed")

        async def check_user_access(self, **_kwargs):
            service_events.append("agent_access_checked")
            return True

    class SentinelAgentChatService:
        def __init__(self, *_args):
            service_events.append("chat_constructed")

        async def chat(self, **_kwargs):
            service_events.append("chat")
            return _ChatResult()

        async def stream_chat(self, **_kwargs):
            service_events.append("stream_chat")
            return JSONResponse(content={})

    class SentinelConversationService:
        def __init__(self, *_args):
            service_events.append("conversation_constructed")

        async def __getattr__(self, name):
            service_events.append(f"conversation_{name}")
            return None

    monkeypatch.setattr(tenant_module, "AgentService", SentinelAgentService)
    monkeypatch.setattr(tenant_module, "AgentChatService", SentinelAgentChatService)
    monkeypatch.setattr(
        tenant_module, "ConversationService", SentinelConversationService
    )
    monkeypatch.setattr(
        tenant_module,
        "PermissionService",
        lambda _db: SimpleNamespace(
            get_tenant_admin_permissions=AsyncMock(return_value=["*"])
        ),
    )

    app = FastAPI()
    _register_app_exception_handler(app)

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    async def sentinel_route(*_args, **_kwargs):
        service_events.append("handle_route")
        return JSONResponse(content={})

    monkeypatch.setattr(tenant_module, "handle_route", sentinel_route)

    app.include_router(tenant_module.TenantAgentChatController.get_router())

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_admin():
        return SimpleNamespace(
            ai_chat_enabled=False,
            ai_enabled=False,
            ai_unavailable_reason="account_disabled",
            effective_ai_enabled=False,
            id=7,
            is_active=True,
            is_owner=True,
            role_id=3,
            tenant_ai_enabled=True,
            tenant_id=5,
            tenant_plan_ai_enabled=True,
            username="disabled_tenant_admin",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_admin] = override_tenant_admin

    with TestClient(app, raise_server_exceptions=False) as client:
        request_fn = getattr(client, method)
        response = request_fn(path, json=json_body) if json_body else request_fn(path)

    payload = response.json()
    assert response.status_code == 403
    assert payload["code"] == 4032
    assert payload["reason"] == "account_ai_disabled"
    assert payload["feature"] == "ai_chat"
    assert service_events == []


def test_tenant_ai_chat_rejects_tenant_plan_disabled_before_agent_services(
    monkeypatch,
) -> None:
    tenant_module = _load_module(
        "app/api/tenant/agent_chat.py",
        "test_tenant_ai_plan_guard_module",
    )
    monkeypatch.setattr(tenant_module.TenantAgentChatController, "_instance", None)
    monkeypatch.setattr(tenant_module.TenantAgentChatController, "_router", None)

    service_events: list[str] = []

    class SentinelAgentService:
        def __init__(self, *_args):
            service_events.append("agent_access_constructed")

        async def check_user_access(self, **_kwargs):
            service_events.append("agent_access_checked")
            return True

    class SentinelAgentChatService:
        def __init__(self, *_args):
            service_events.append("chat_constructed")

        async def chat(self, **_kwargs):
            service_events.append("chat")
            return _ChatResult()

    monkeypatch.setattr(tenant_module, "AgentService", SentinelAgentService)
    monkeypatch.setattr(tenant_module, "AgentChatService", SentinelAgentChatService)
    monkeypatch.setattr(
        tenant_module,
        "PermissionService",
        lambda _db: SimpleNamespace(
            get_tenant_admin_permissions=AsyncMock(return_value=["*"])
        ),
    )

    app = FastAPI()
    _register_app_exception_handler(app)

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    app.include_router(tenant_module.TenantAgentChatController.get_router())

    async def override_db():
        yield SimpleNamespace()

    async def override_tenant_admin():
        return SimpleNamespace(
            ai_chat_enabled=False,
            ai_enabled=True,
            ai_unavailable_reason="tenant_plan_disabled",
            effective_ai_enabled=False,
            id=8,
            is_active=True,
            role_id=3,
            tenant_ai_enabled=False,
            tenant_id=5,
            tenant_plan_ai_enabled=False,
            username="plan_disabled_tenant_admin",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_admin] = override_tenant_admin

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/ai/agent-chat/42/chat", json=_chat_payload())

    payload = response.json()
    assert response.status_code == 403
    assert payload["code"] == 4033
    assert payload["reason"] == "tenant_plan_ai_disabled"
    assert payload["feature"] == "ai_chat"
    assert service_events == []


_USER_DISABLED_ROUTE_CASES = (
    ("post", "/ai/agent-chat/42/chat", _chat_payload()),
    ("post", "/ai/agent-chat/42/chat/stream", _chat_payload()),
    ("post", "/ai/agent-chat/route", _route_payload()),
    ("get", "/ai/agent-chat/conversations", None),
    ("get", "/ai/agent-chat/conversations/11", None),
    ("get", "/ai/agent-chat/conversations/11/compact", None),
    ("get", "/ai/agent-chat/conversations/11/timeline", None),
    ("patch", "/ai/agent-chat/conversations/11", _title_payload()),
    ("delete", "/ai/agent-chat/conversations/11", None),
    ("get", "/ai/agent-chat/conversations/11/memory-state", None),
    ("delete", "/ai/agent-chat/conversations/11/memory-state", None),
    ("post", "/ai/agent-chat/conversations/11/compact", None),
)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    _USER_DISABLED_ROUTE_CASES,
    ids=[f"{method.upper()} {path}" for method, path, _ in _USER_DISABLED_ROUTE_CASES],
)
def test_tenant_user_ai_chat_rejects_plan_disabled_before_agent_services(
    method,
    path,
    json_body,
    monkeypatch,
) -> None:
    user_module = _load_module(
        "app/api/user/agent_chat.py",
        _safe_module_name("test_user_ai_plan_guard_module", method, path),
    )
    monkeypatch.setattr(user_module.UserAgentChatController, "_instance", None)
    monkeypatch.setattr(user_module.UserAgentChatController, "_router", None)

    service_events: list[str] = []

    class SentinelAgentService:
        def __init__(self, *_args):
            service_events.append("agent_access_constructed")

        async def check_user_access(self, **_kwargs):
            service_events.append("agent_access_checked")
            return True

    class SentinelAgentChatService:
        def __init__(self, *_args):
            service_events.append("chat_constructed")

        async def chat(self, **_kwargs):
            service_events.append("chat")
            return _ChatResult()

        async def stream_chat(self, **_kwargs):
            service_events.append("stream_chat")
            return JSONResponse(content={})

    class SentinelConversationService:
        def __init__(self, *_args):
            service_events.append("conversation_constructed")

    async def sentinel_route(*_args, **_kwargs):
        service_events.append("handle_route")
        return JSONResponse(content={})

    monkeypatch.setattr(user_module, "AgentService", SentinelAgentService)
    monkeypatch.setattr(user_module, "AgentChatService", SentinelAgentChatService)
    monkeypatch.setattr(user_module, "ConversationService", SentinelConversationService)
    monkeypatch.setattr(user_module, "handle_route", sentinel_route)

    app = FastAPI()
    _register_app_exception_handler(app)
    app.include_router(user_module.UserAgentChatController.get_router())

    async def override_db():
        yield SimpleNamespace(
            execute=AsyncMock(return_value=_DBExecuteResult(scalar=None))
        )

    async def override_tenant_user():
        return SimpleNamespace(
            id=17,
            is_active=True,
            role_id=4,
            tenant_id=5,
            username="plan_disabled_tenant_user",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_user] = override_tenant_user

    with TestClient(app, raise_server_exceptions=False) as client:
        request_fn = getattr(client, method)
        response = request_fn(path, json=json_body) if json_body else request_fn(path)

    payload = response.json()
    assert response.status_code == 403
    assert payload["code"] == 4033
    assert payload["reason"] == "tenant_plan_ai_disabled"
    assert payload["feature"] == "ai_chat"
    assert service_events == []


@pytest.mark.parametrize(
    ("path", "json_body"),
    (
        ("/ai/agents", None),
        ("/ai/agents/42/knowledge-bases", None),
    ),
)
def test_tenant_user_agent_directory_rejects_plan_disabled_before_services(
    path,
    json_body,
    monkeypatch,
) -> None:
    user_agents_module = _load_module(
        "app/api/user/agents.py",
        _safe_module_name("test_user_agents_plan_guard_module", "get", path),
    )
    monkeypatch.setattr(user_agents_module.UserAgentController, "_instance", None)
    monkeypatch.setattr(user_agents_module.UserAgentController, "_router", None)

    service_events: list[str] = []

    class SentinelAgentService:
        def __init__(self, *_args):
            service_events.append("agent_constructed")

    class SentinelAgentKBBindingService:
        def __init__(self, *_args):
            service_events.append("kb_constructed")

    monkeypatch.setattr(user_agents_module, "AgentService", SentinelAgentService)
    monkeypatch.setattr(
        user_agents_module,
        "AgentKBBindingService",
        SentinelAgentKBBindingService,
    )

    app = FastAPI()
    _register_app_exception_handler(app)
    app.include_router(user_agents_module.UserAgentController.get_router())

    async def override_db():
        yield SimpleNamespace(
            execute=AsyncMock(return_value=_DBExecuteResult(scalar=None))
        )

    async def override_tenant_user():
        return SimpleNamespace(
            id=17,
            is_active=True,
            role_id=4,
            tenant_id=5,
            username="plan_disabled_tenant_user",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_tenant_user] = override_tenant_user

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path, json=json_body) if json_body else client.get(path)

    payload = response.json()
    assert response.status_code == 403
    assert payload["code"] == 4033
    assert payload["reason"] == "tenant_plan_ai_disabled"
    assert payload["feature"] == "ai_chat"
    assert service_events == []


@pytest.mark.asyncio
async def test_tenant_ai_guard_matches_auth_profile_for_legacy_plan_feature_default() -> (
    None
):
    feature_calls: list[tuple[str, bool]] = []

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=True,
                plan_id=9,
                quota={},
                tenant_plan=SimpleNamespace(
                    is_active=True,
                    get_feature=lambda key, default=False: (
                        feature_calls.append((key, default)) or default
                    ),
                ),
            )

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    tenant_admin = SimpleNamespace(
        ai_enabled=True,
        id=9,
        tenant_id=5,
    )

    await AccountAIAccessService(db).require_tenant_admin_ai_access(tenant_admin)
    assert feature_calls == [("ai_enabled", True)]
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_tenant_ai_guard_rejects_inactive_plan_before_feature_default() -> None:
    feature_calls: list[str] = []

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=True,
                plan_id=9,
                quota={},
                tenant_plan=SimpleNamespace(
                    is_active=False,
                    get_feature=lambda key, _default=False: (
                        feature_calls.append(key) or True
                    ),
                ),
            )

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    tenant_admin = SimpleNamespace(
        ai_enabled=True,
        id=9,
        tenant_id=5,
    )

    with pytest.raises(AppException) as exc_info:
        await AccountAIAccessService(db).require_tenant_admin_ai_access(tenant_admin)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 4033
    assert exc_info.value.extra["reason"] == "tenant_plan_ai_disabled"
    assert feature_calls == []


@pytest.mark.asyncio
async def test_tenant_ai_guard_rejects_inactive_tenant_before_feature_default() -> None:
    feature_calls: list[str] = []

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=False,
                plan_id=9,
                quota={},
                tenant_plan=SimpleNamespace(
                    is_active=True,
                    get_feature=lambda key, _default=False: (
                        feature_calls.append(key) or True
                    ),
                ),
            )

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    tenant_admin = SimpleNamespace(
        ai_enabled=True,
        id=9,
        tenant_id=5,
    )

    with pytest.raises(AppException) as exc_info:
        await AccountAIAccessService(db).require_tenant_admin_ai_access(tenant_admin)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 4033
    assert exc_info.value.extra["reason"] == "tenant_plan_ai_disabled"
    assert feature_calls == []


@pytest.mark.asyncio
async def test_tenant_user_ai_guard_rejects_inactive_plan_before_feature_default() -> (
    None
):
    feature_calls: list[str] = []

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=True,
                plan_id=9,
                quota={},
                tenant_plan=SimpleNamespace(
                    is_active=False,
                    get_feature=lambda key, _default=False: (
                        feature_calls.append(key) or True
                    ),
                ),
            )

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    tenant_user = SimpleNamespace(
        id=17,
        is_active=True,
        tenant_id=5,
    )

    with pytest.raises(AppException) as exc_info:
        await AccountAIAccessService(db).require_tenant_user_ai_access(tenant_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 4033
    assert exc_info.value.extra["reason"] == "tenant_plan_ai_disabled"
    assert feature_calls == []


@pytest.mark.asyncio
async def test_platform_admin_effective_ai_disabled_when_ancestor_leader_is_disabled() -> (
    None
):
    db = _QueuedDB(
        get_result=SimpleNamespace(id=3, is_deleted=False, path="/1/2/3/"),
        execute_results=[_DBExecuteResult(scalars=[True, False])],
    )
    admin = SimpleNamespace(
        ai_enabled=True,
        id=33,
        is_deleted=False,
        org_node_id=3,
    )

    profile = await AccountAIAccessService(
        db  # type: ignore[arg-type]
    ).get_platform_admin_ai_availability_profile(admin)

    assert profile["account_ai_enabled"] is True
    assert profile["leader_ai_enabled"] is False
    assert profile["effective_ai_enabled"] is False
    assert profile["ai_unavailable_reason"] == "leader_ai_disabled"


@pytest.mark.asyncio
async def test_tenant_admin_guard_rejects_when_leader_chain_disables_ai() -> None:
    db = _QueuedDB(
        get_result=SimpleNamespace(
            id=12,
            is_deleted=False,
            path="/10/11/12/",
            tenant_id=5,
        ),
        execute_results=[
            _DBExecuteResult(scalars=[False]),
            _DBExecuteResult(
                scalar=SimpleNamespace(
                    id=5,
                    is_active=True,
                    is_deleted=False,
                    plan_id=9,
                    quota={},
                    tenant_plan=SimpleNamespace(
                        is_active=True, get_feature=lambda _key, default=False: default
                    ),
                )
            ),
        ],
    )
    tenant_admin = SimpleNamespace(
        ai_enabled=True,
        id=44,
        is_deleted=False,
        org_node_id=12,
        tenant_id=5,
    )

    with pytest.raises(AppException) as exc_info:
        await AccountAIAccessService(
            db  # type: ignore[arg-type]
        ).require_tenant_admin_ai_access(tenant_admin)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 4032
    assert exc_info.value.extra["reason"] == "leader_ai_disabled"
