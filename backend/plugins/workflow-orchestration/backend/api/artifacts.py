from __future__ import annotations

from io import BytesIO

from fastapi.responses import StreamingResponse

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _module(dotted_path: str):
    module = load_plugin_module(PLUGIN_NAME, dotted_path)
    if module is None:
        raise RuntimeError(f"Missing backend module: {dotted_path}")
    return module


def _content_disposition(filename: str) -> str:
    safe = filename.replace("\n", "_").replace("\r", "_").replace("\"", "'")
    return f'attachment; filename="{safe}"'


async def list_artifacts(request, db, ctx):
    errors = _module("runtime.errors")
    try:
        tenant_id = ctx.get_current_tenant_id()
        service = _module("services.artifact_service").ArtifactService(db, tenant_id=tenant_id)
        return await service.list_artifacts(request.query_params)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def get_artifact_detail(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = ctx.get_current_tenant_id()
        artifact_id = http.safe_int(request.path_params.get("artifact_id"), 0)
        service = _module("services.artifact_service").ArtifactService(db, tenant_id=tenant_id)
        return await service.get_artifact_detail(artifact_id)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def submit_feedback(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = ctx.get_current_tenant_id()
        artifact_id = http.safe_int(request.path_params.get("artifact_id"), 0)
        payload = await http.read_json_body(request)
        service = _module("services.artifact_service").ArtifactService(db, tenant_id=tenant_id)
        return await service.submit_feedback(artifact_id, payload)
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()


async def download_artifact(request, db, ctx):
    errors = _module("runtime.errors")
    http = _module("runtime.http")
    try:
        tenant_id = ctx.get_current_tenant_id()
        artifact_id = http.safe_int(request.path_params.get("artifact_id"), 0)
        service = _module("services.artifact_service").ArtifactService(db, tenant_id=tenant_id)
        payload = await service.download_artifact(artifact_id)
        response = StreamingResponse(
            BytesIO(payload["content"]),
            media_type=payload["mime_type"],
        )
        response.headers["Content-Disposition"] = _content_disposition(payload["filename"])
        return response
    except errors.WorkflowRuntimeError as exc:
        return exc.to_dict()
