from app.api.tenant import tenant_router


def test_tenant_router_excludes_system_task_management_routes() -> None:
    paths = {route.path for route in tenant_router.routes}

    assert "/tasks" not in paths
    assert "/tasks/stats" not in paths
    assert "/tasks/{task_log_id}" not in paths
    assert "/periodic-tasks" not in paths
    assert "/periodic-tasks/{task_id}" not in paths
    assert "/periodic-tasks/{task_id}/trigger" not in paths
