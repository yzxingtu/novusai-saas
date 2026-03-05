"""DataForge Studio — 数据记录 API handlers"""
from __future__ import annotations

from ..services import record_service as svc


def _ids(request) -> tuple[int | None, int | None]:
    try:
        pid = int(request.path_params["project_id"])
        sid = int(request.path_params["schema_id"])
        return pid, sid
    except (KeyError, ValueError, TypeError):
        return None, None


async def list_records(request, db, ctx):
    """GET /projects/{project_id}/schemas/{schema_id}/records"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    p = request.query_params
    try:
        page = max(1, int(p.get("page[number]", 1)))
        size = min(200, max(1, int(p.get("page[size]", 50))))
    except (ValueError, TypeError):
        page, size = 1, 50
    items, total = await svc.list_records(
        db, pid, sid,
        page=page, size=size,
        sort=p.get("sort", "-created_at"),
    )
    return {"items": items, "total": total, "page": page, "size": size}


async def create_record(request, db, ctx):
    """POST /projects/{project_id}/schemas/{schema_id}/records"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    body = await request.json()
    item = await svc.create_record(db, pid, sid, body)
    await db.commit()
    return item


async def get_record(request, db, ctx):
    """GET /projects/{project_id}/schemas/{schema_id}/records/{record_id}"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    try:
        rid = int(request.path_params["record_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid record_id", "code": 4001, "status_code": 422}
    item = await svc.get_record(db, pid, sid, rid)
    if not item:
        return {"error": "record not found", "code": 4040, "status_code": 404}
    return item


async def update_record(request, db, ctx):
    """PUT /projects/{project_id}/schemas/{schema_id}/records/{record_id}"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    try:
        rid = int(request.path_params["record_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid record_id", "code": 4001, "status_code": 422}
    body = await request.json()
    item = await svc.update_record(db, pid, sid, rid, body)
    if not item:
        return {"error": "record not found", "code": 4040, "status_code": 404}
    await db.commit()
    return item


async def delete_record(request, db, ctx):
    """DELETE /projects/{project_id}/schemas/{schema_id}/records/{record_id}"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    try:
        rid = int(request.path_params["record_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid record_id", "code": 4001, "status_code": 422}
    ok = await svc.delete_record(db, pid, sid, rid)
    if not ok:
        return {"error": "record not found", "code": 4040, "status_code": 404}
    await db.commit()
    return {"message": "deleted"}


async def bulk_delete_records(request, db, ctx):
    """POST /projects/{project_id}/schemas/{schema_id}/records/bulk"""
    pid, sid = _ids(request)
    if pid is None:
        return {"error": "invalid path params", "code": 4001, "status_code": 422}
    body = await request.json()
    ids = body.get("ids", [])
    if not ids:
        return {"error": "ids is required", "code": 4001, "status_code": 422}
    count = await svc.bulk_delete_records(db, pid, sid, ids)
    await db.commit()
    return {"deleted": count}
