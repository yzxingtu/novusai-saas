"""DataForge Studio — 项目 API handlers"""
from __future__ import annotations

from ..services import project_service as svc


async def list_projects(request, db, ctx):
    """GET /projects"""
    p = request.query_params
    try:
        page = max(1, int(p.get("page[number]", 1)))
        size = min(100, max(1, int(p.get("page[size]", 20))))
    except (ValueError, TypeError):
        page, size = 1, 20
    items, total = await svc.list_projects(
        db,
        search=p.get("filter[name][ilike]") or p.get("q"),
        page=page, size=size,
        sort=p.get("sort", "-created_at"),
    )
    return {"items": items, "total": total, "page": page, "size": size}


async def create_project(request, db, ctx):
    """POST /projects"""
    body = await request.json()
    if not body.get("name"):
        return {"error": "name is required", "code": 4001, "status_code": 422}
    item = await svc.create_project(db, body)
    await db.commit()
    return item


async def get_project(request, db, ctx):
    """GET /projects/{project_id}"""
    try:
        pid = int(request.path_params["project_id"])
    except (KeyError, ValueError):
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    item = await svc.get_project(db, pid)
    if not item:
        return {"error": "project not found", "code": 4040, "status_code": 404}
    return item


async def update_project(request, db, ctx):
    """PUT /projects/{project_id}"""
    try:
        pid = int(request.path_params["project_id"])
    except (KeyError, ValueError):
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    body = await request.json()
    item = await svc.update_project(db, pid, body)
    if not item:
        return {"error": "project not found", "code": 4040, "status_code": 404}
    await db.commit()
    return item


async def delete_project(request, db, ctx):
    """DELETE /projects/{project_id}"""
    try:
        pid = int(request.path_params["project_id"])
    except (KeyError, ValueError):
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}
    ok = await svc.delete_project(db, pid)
    if not ok:
        return {"error": "project not found", "code": 4040, "status_code": 404}
    await db.commit()
    return {"message": "deleted"}
