from __future__ import annotations

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


async def list_runs(request, db, ctx):
    del ctx
    errors = _module("runtime.errors")
    try:
        service = _module("services.run_query_service").RunQueryService(db, tenant_id=None)
        return await service.list_runs(request.query_params)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def get_run_detail(request, db, ctx):
    del ctx
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.run_query_service").RunQueryService(db, tenant_id=None)
        return await service.get_run_detail(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def replay_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.recovery_service").RecoveryService(
            db,
            tenant_id=None,
            actor_type="platform_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.replay_run(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def recover_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        payload = await http.read_json_body(request) if request.method.upper() in {"POST", "PUT", "PATCH"} else {}
        service = _module("services.recovery_service").RecoveryService(
            db,
            tenant_id=None,
            actor_type="platform_admin",
            actor_id=ctx.get_current_user_id(),
        )
        checkpoint_id = http.safe_int(payload.get("checkpoint_id"), 0) or None
        return await service.recover_run(run_id, checkpoint_id=checkpoint_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def terminate_run(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        run_id = http.safe_int(request.path_params.get("run_id"), 0)
        service = _module("services.run_service").RunService(
            db,
            tenant_id=None,
            actor_type="platform_admin",
            actor_id=ctx.get_current_user_id(),
        )
        return await service.terminate_run(run_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
