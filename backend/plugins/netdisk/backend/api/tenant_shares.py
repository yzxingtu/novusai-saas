"""企业端分享管理 API（已登录用户）/ Tenant share management API (authenticated)."""

from __future__ import annotations

from ._schemas import share_schema as _share_schema


async def create_share(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    body    = await request.json()
    from ..services.share_service import ShareService
    svc   = ShareService(db, ctx.get_current_tenant_id())
    share = await svc.create_share(
        node_id=node_id,
        permission=body.get("permission", "download"),
        password=body.get("password"),
        expires_days=body.get("expires_days"),
    )
    return {"share": _share_schema(share)}


async def list_node_shares(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    from ..services.share_service import ShareService
    svc    = ShareService(db, ctx.get_current_tenant_id())
    shares = await svc.list_node_shares(node_id)
    return {"items": [_share_schema(s) for s in shares], "total": len(shares)}


async def list_my_shares(request, db, ctx):
    """列出当前企业的全部分享链接（含文件名/类型） / List all share links for tenant (with file name/type)."""
    page = int(request.query_params.get("page", "1"))
    size = min(int(request.query_params.get("size", "50")), 100)
    from ..services.share_service import ShareService
    svc    = ShareService(db, ctx.get_current_tenant_id())
    result = await svc.list_my_shares(page=page, size=size)
    return {
        "items": [
            _share_schema(item["share"], node_name=item.get("node_name"), node_type=item.get("node_type"))
            for item in result["items"]
        ],
        "total": result["total"],
    }


async def cancel_share(request, db, ctx):
    token = request.path_params["token"]
    from ..services.share_service import ShareService
    svc = ShareService(db, ctx.get_current_tenant_id())
    await svc.cancel_share(token)
    return {"cancelled": True}


async def get_quota(request, db, ctx):
    from ..services.quota_service import QuotaService
    svc  = QuotaService(db, ctx.get_current_tenant_id())
    data = await svc.get_quota()
    return data
