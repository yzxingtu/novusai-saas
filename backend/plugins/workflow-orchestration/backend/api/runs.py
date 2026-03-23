from __future__ import annotations

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


def _normalized_action(payload: dict[str, object]) -> str:
    return str(payload.get("action") or "").strip().lower()


def _has_waiting_action_payload(payload: dict[str, object]) -> bool:
    if not payload:
        return False
    action = _normalized_action(payload)
    if action and action != "resume":
        return True
    return any(
        key in payload
        for key in (
            "decision",
            "approved",
            "input_payload",
            "inputs",
            "input_envelope_json",
            "human_input",
            "manual_input",
        )
    )


async def create_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        workflow_id = http.safe_int(request.path_params.get("workflow_id"), 0)
        payload = await http.read_json_body(request) if request.method.upper() in {"POST", "PUT", "PATCH"} else {}
        service = _module("services.run_service").RunService(
            db,
            tenant_id,
            actor_type="tenant_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.create_run_from_workflow(workflow_id, payload)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_list_runs(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        service = _module("services.run_query_service").RunQueryService(db, tenant_id)
        return await service.list_runs(request.query_params)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_get_run_detail(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.run_query_service").RunQueryService(db, tenant_id)
        return await service.get_tenant_run_detail(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_pause_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.run_service").RunService(
            db,
            tenant_id,
            actor_type="tenant_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.pause_run(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_resume_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        payload = await http.read_json_body(request) if request.method.upper() in {"POST", "PUT", "PATCH"} else {}
        checkpoint_id = http.safe_int(payload.get("checkpoint_id"), 0) or None
        service = _module("services.recovery_service").RecoveryService(
            db,
            tenant_id,
            actor_type="tenant_admin",
            actor_id=ctx.get_current_user_id(),
        )
        if _has_waiting_action_payload(payload):
            return await service.submit_waiting_action(run_id, payload)
        return await service.resume_run(run_id, checkpoint_id=checkpoint_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_retry_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.recovery_service").RecoveryService(
            db,
            tenant_id,
            actor_type="tenant_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.retry_run(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def tenant_terminate_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = http.require_tenant_id(ctx)
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.run_service").RunService(
            db,
            tenant_id,
            actor_type="tenant_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.terminate_run(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
