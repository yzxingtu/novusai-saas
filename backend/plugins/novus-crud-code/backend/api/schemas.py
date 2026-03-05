"""DataForge Studio — 表结构 API handlers"""
from __future__ import annotations

from ..services import schema_service as svc


def _pid(request) -> int | None:
    try:
        return int(request.path_params["project_id"])
    except (KeyError, ValueError, TypeError):
        return None


def _sid(request) -> int | None:
    try:
        return int(request.path_params["schema_id"])
    except (KeyError, ValueError, TypeError):
        return None


async def list_schemas(request, db, ctx):
    """GET /projects/{project_id}/schemas"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    p = request.query_params
    items, total = await svc.list_schemas(
        db, pid, page=int(p.get("page[number]", 1)), size=int(p.get("page[size]", 50)),
    )
    return {"items": items, "total": total}


async def create_schema(request, db, ctx):
    """POST /projects/{project_id}/schemas"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    body = await request.json()
    if not body.get("name"):
        return {"error": "name is required", "code": 4001, "status_code": 422}
    item = await svc.create_schema(db, pid, body)
    await db.commit()
    return item


async def get_schema(request, db, ctx):
    """GET /projects/{project_id}/schemas/{schema_id}"""
    pid, sid = _pid(request), _sid(request)
    if pid is None or sid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    item = await svc.get_schema(db, pid, sid)
    if not item:
        return {"error": "schema not found", "code": 4040, "status_code": 404}
    return item


async def update_schema(request, db, ctx):
    """PUT /projects/{project_id}/schemas/{schema_id}"""
    pid, sid = _pid(request), _sid(request)
    if pid is None or sid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    body = await request.json()
    item = await svc.update_schema(db, pid, sid, body)
    if not item:
        return {"error": "schema not found", "code": 4040, "status_code": 404}
    await db.commit()
    return item


async def delete_schema(request, db, ctx):
    """DELETE /projects/{project_id}/schemas/{schema_id}"""
    pid, sid = _pid(request), _sid(request)
    if pid is None or sid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    ok = await svc.delete_schema(db, pid, sid)
    if not ok:
        return {"error": "schema not found", "code": 4040, "status_code": 404}
    await db.commit()
    return {"message": "deleted"}
