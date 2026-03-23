from __future__ import annotations

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


async def get_home(request, db, ctx):
    del request
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        builder_capabilities = await workflow_service.get_builder_capabilities()
        query_service = _module("services.run_query_service").RunQueryService(db, tenant_id)
        return await query_service.get_tenant_home(builder_capabilities)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def get_builder_capabilities(request, db, ctx):
    del request
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.get_builder_capabilities()
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
