"""DataForge Studio — 表关联 API handlers"""
from __future__ import annotations

from ..services import schema_service as svc


def _pid(request) -> int | None:
    try:
        return int(request.path_params["project_id"])
    except (KeyError, ValueError, TypeError):
        return None


async def list_relations(request, db, ctx):
    """GET /projects/{project_id}/relations"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    items = await svc.list_relations(db, pid)
    return {"items": items, "total": len(items)}


async def create_relation(request, db, ctx):
    """POST /projects/{project_id}/relations"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    body = await request.json()
    for field in ("from_schema_id", "to_schema_id", "from_field", "to_field"):
        if not body.get(field):
            return {"error": f"{field} is required", "code": 4001, "status_code": 422}
    try:
        item = await svc.create_relation(db, pid, body)
    except ValueError as exc:
        return {"error": str(exc), "code": 4001, "status_code": 422}
    await db.commit()
    return item


async def update_relation(request, db, ctx):
    """PUT /projects/{project_id}/relations/{relation_id}"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    try:
        rid = int(request.path_params["relation_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid relation_id", "code": 4001, "status_code": 422}
    body = await request.json()
    item = await svc.update_relation(db, pid, rid, body)
    if not item:
        return {"error": "relation not found", "code": 4040, "status_code": 404}
    await db.commit()
    return item


async def delete_relation(request, db, ctx):
    """DELETE /projects/{project_id}/relations/{relation_id}"""
    pid = _pid(request)
    if pid is None:
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    try:
        rid = int(request.path_params["relation_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid relation_id", "code": 4001, "status_code": 422}
    ok = await svc.delete_relation(db, pid, rid)
    if not ok:
        return {"error": "relation not found", "code": 4040, "status_code": 404}
    await db.commit()
    return {"message": "deleted"}
