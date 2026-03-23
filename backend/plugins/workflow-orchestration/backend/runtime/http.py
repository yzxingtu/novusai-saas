from __future__ import annotations

from typing import Any

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
DEFAULT_PAGE_NUMBER = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _errors():
    module = load_plugin_module(PLUGIN_NAME, "runtime.errors")
    if module is None:
        raise RuntimeError("workflow runtime errors module is unavailable")
    return module


async def read_json_body(request: Any) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise _errors().WorkflowValidationError() from exc
    if not isinstance(body, dict):
        raise _errors().WorkflowValidationError()
    return body


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_page_number(query_params: Any) -> int:
    return max(
        1,
        safe_int(
            query_params.get("page[number]") or query_params.get("page"),
            DEFAULT_PAGE_NUMBER,
        ),
    )


def get_page_size(query_params: Any) -> int:
    raw = safe_int(
        query_params.get("page[size]") or query_params.get("page_size"),
        DEFAULT_PAGE_SIZE,
    )
    return max(1, min(raw, MAX_PAGE_SIZE))


def require_tenant_id(ctx: Any) -> int:
    tenant_id = ctx.get_current_tenant_id()
    if tenant_id is None:
        raise _errors().WorkflowValidationError()
    return tenant_id


def load_backend_module(dotted_path: str) -> Any:
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise _errors().WorkflowDependencyError(
            f"Missing runtime dependency module: {PLUGIN_NAME}:{dotted_path}",
        )
    return module
