from __future__ import annotations

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


async def list_templates(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.list_copyable_templates(request.query_params)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
