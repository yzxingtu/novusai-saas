"""
Test type: structural
Scope: FastAPI OpenAPI operation IDs remain unique while dynamic plugin runtime
routes stay executable but outside the typed schema contract.
Mocked dependencies: App construction only; no lifespan, database, Redis, or
network services are started.
"""

from __future__ import annotations

import warnings
from collections import Counter

from app.main import create_application


def test_openapi_operation_ids_are_unique_and_skip_dynamic_plugin_routes() -> None:
    app = create_application().other_asgi_app
    schema = app.openapi()

    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    duplicates = {
        operation_id: count
        for operation_id, count in Counter(operation_ids).items()
        if count > 1
    }
    excluded_paths: set[str] = {
        "/admin/plugins/{plugin_name}/api/{path}",
        "/tenant/plugins/{plugin_name}/api/{path}",
        "/api/public/plugins/{plugin_name}/api/{path}",
        "/plugin-public-assets/{public_endpoint}/{plugin_name}/{file_path}",
        "/plugin-assets/{plugin_name}/{file_path}",
        "/plugin-icons/{plugin_name}/{file_path}",
    }

    assert duplicates == {}
    assert excluded_paths.isdisjoint(set(schema["paths"]))


def test_dynamic_plugin_routes_remain_registered_outside_openapi_schema() -> None:
    app = create_application().other_asgi_app

    runtime_paths = {
        getattr(route, "path", "")
        for route in app.routes
        if getattr(route, "include_in_schema", True) is False
    }
    expected_runtime_paths: set[str] = {
        "/admin/plugins/{plugin_name}/api/{path:path}",
        "/tenant/plugins/{plugin_name}/api/{path:path}",
        "/api/public/plugins/{plugin_name}/api/{path:path}",
        "/plugin-public-assets/{public_endpoint}/{plugin_name}/{file_path:path}",
        "/plugin-assets/{plugin_name}/{file_path:path}",
        "/plugin-icons/{plugin_name}/{file_path:path}",
    }
    methods_by_path: dict[str, set[str]] = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()))
        for route in app.routes
        if getattr(route, "path", "") in expected_runtime_paths
    }

    assert expected_runtime_paths.issubset(runtime_paths)
    assert {"GET", "POST", "PUT", "DELETE", "PATCH"}.issubset(
        methods_by_path["/admin/plugins/{plugin_name}/api/{path:path}"]
    )
    assert {"GET", "HEAD"}.issubset(
        methods_by_path["/plugin-assets/{plugin_name}/{file_path:path}"]
    )


def test_openapi_generation_does_not_warn_about_dynamic_route_operation_ids() -> None:
    app = create_application().other_asgi_app

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app.openapi()

    duplicate_operation_id_warnings = [
        str(warning.message)
        for warning in caught
        if "Duplicate Operation ID" in str(warning.message)
    ]
    assert duplicate_operation_id_warnings == []
