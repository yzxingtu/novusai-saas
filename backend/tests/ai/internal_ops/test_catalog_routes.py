from types import SimpleNamespace

from fastapi import APIRouter, FastAPI

from app.ai.internal_ops.catalog import _build_catalog_from_app


def _mark_permission(endpoint, resource: str, action: str):
    endpoint._permission_resource = resource
    endpoint._permission_action = {"action": action}
    return endpoint


def test_catalog_builds_from_nested_fastapi_routers() -> None:
    app = FastAPI()

    admin_router = APIRouter()
    admin_ai_router = APIRouter()
    tenant_router = APIRouter()
    user_router = APIRouter()

    @admin_ai_router.get("/agents", summary="List AI agents")
    async def list_admin_agents() -> dict[str, bool]:
        return {"ok": True}

    @tenant_router.post("/profiles", summary="Create tenant profile")
    async def create_tenant_profile() -> dict[str, bool]:
        return {"ok": True}

    @user_router.get("/me", summary="Get current user")
    async def get_current_user() -> dict[str, bool]:
        return {"ok": True}

    _mark_permission(list_admin_agents, "ai_agent", "view")
    _mark_permission(create_tenant_profile, "tenant_profile", "create")
    _mark_permission(get_current_user, "user_profile", "view")

    admin_router.include_router(admin_ai_router, prefix="/ai")
    app.include_router(admin_router, prefix="/admin")
    app.include_router(tenant_router, prefix="/tenant")
    app.include_router(user_router, prefix="/api/user")

    operations = _build_catalog_from_app(app)

    by_id = {operation.operation_id: operation for operation in operations}
    assert set(by_id) == {
        "GET:/admin/ai/agents",
        "GET:/api/user/me",
        "POST:/tenant/profiles",
    }
    assert by_id["GET:/admin/ai/agents"].scope == "admin"
    assert by_id["GET:/admin/ai/agents"].permission_code == "ai_agent:view"
    assert by_id["GET:/api/user/me"].scope == "user"
    assert by_id["POST:/tenant/profiles"].scope == "tenant"
    assert by_id["POST:/tenant/profiles"].is_write is True


def test_catalog_expands_runtime_included_router_nodes() -> None:
    async def endpoint() -> dict[str, bool]:
        return {"ok": True}

    _mark_permission(endpoint, "runtime_ops", "view")

    concrete_route = SimpleNamespace(
        path="/settings",
        methods={"GET"},
        endpoint=endpoint,
        dependant=None,
        body_field=None,
        summary="Runtime settings",
        name="runtime_settings",
    )
    included_router = SimpleNamespace(
        path=None,
        prefix="/admin",
        methods=set(),
        endpoint=None,
        routes=[
            SimpleNamespace(
                path="/runtime",
                methods=set(),
                endpoint=None,
                routes=[concrete_route],
            )
        ],
    )
    app = SimpleNamespace(routes=[included_router])

    operations = _build_catalog_from_app(app)

    assert [operation.operation_id for operation in operations] == [
        "GET:/admin/runtime/settings"
    ]
    assert operations[0].path == "/admin/runtime/settings"
    assert operations[0].scope == "admin"
    assert operations[0].permission_code == "runtime_ops:view"
