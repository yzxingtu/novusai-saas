from __future__ import annotations

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


async def list_workflows(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.list_workflows(request.query_params)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def create_workflow(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        payload = await http.read_json_body(request)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.create_workflow(payload)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def copy_from_template(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        payload = await http.read_json_body(request)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.copy_from_template(payload)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def get_workflow_detail(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_id = http.safe_int(request.path_params.get("workflow_id"), 0)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.get_workflow_detail(workflow_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def update_workflow(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_id = http.safe_int(request.path_params.get("workflow_id"), 0)
        payload = await http.read_json_body(request)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.update_workflow(workflow_id, payload)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def publish_workflow(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_id = http.safe_int(request.path_params.get("workflow_id"), 0)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return await service.publish_workflow(workflow_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def list_workflow_versions(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_id = http.safe_int(request.path_params.get("workflow_id"), 0)
        service = _module("services.tenant_workflow_service").TenantWorkflowService(
            db,
            tenant_id,
            ctx=ctx,
        )
        return {
            "items": await service.list_workflow_versions(workflow_id),
        }
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
