"""
管理端网盘控制台 API — 跨企业视图 / 配额管理 / 分享审计

Handler 签名：(request, db, ctx)
- 管理端路由： ctx.get_current_tenant_id() 返回 None，用于跨企业操作
"""

from __future__ import annotations

from ._schemas import node_schema as _node_schema


async def list_tenant_files(request, db, ctx):
    """浏览指定企业文件树（只读）"""
    tenant_id     = int(request.query_params["tenant_id"])
    parent_id_str = request.query_params.get("parent_id")
    parent_id     = int(parent_id_str) if parent_id_str else None
    from ..services.file_service import FileService
    svc   = FileService(db, tenant_id)
    nodes = await svc.list_dir(parent_id)
    return {"items": [_node_schema(n) for n in nodes], "total": len(nodes)}


async def list_quotas(request, db, ctx):
    """列出所有企业配额（统计在 Service 层）"""
    page = int(request.query_params.get("page", "1"))
    size = min(int(request.query_params.get("size", "20")), 100)
    from ..services.quota_service import QuotaService
    svc    = QuotaService(db, tenant_id=0)
    result = await svc.admin_list_quotas(page=page, size=size)
    return {
        "items": [_quota_schema(q) for q in result["items"]],
        "total": result["total"],
        "page":  page,
        "page_size": size,
    }


async def update_quota(request, db, ctx):
    """修改指定企业配额"""
    tenant_id   = int(request.path_params["tenant_id"])
    body        = await request.json()
    quota_bytes = int(body["quota_bytes"])
    from ..services.quota_service import QuotaService
    svc = QuotaService(db, tenant_id=tenant_id)
    await svc.admin_update_quota(tenant_id, quota_bytes)
    return {"updated": True}


async def recalculate_quota(request, db, ctx):
    """重算指定企业 used_bytes"""
    tenant_id = int(request.path_params["tenant_id"])
    from ..services.quota_service import QuotaService
    svc    = QuotaService(db, tenant_id=tenant_id)
    actual = await svc.recalculate()
    return {"used_bytes": actual}


async def list_all_shares(request, db, ctx):
    """全局分享审计列表（统计在 ShareService 层）"""
    page = int(request.query_params.get("page", "1"))
    size = min(int(request.query_params.get("size", "20")), 100)
    from ..services.share_service import ShareService
    svc    = ShareService(db, tenant_id=0)
    result = await svc.admin_list_shares(page=page, size=size)
    return {
        "items": [_share_admin_schema(s) for s in result["items"]],
        "total": result["total"],
        "page":  page,
        "page_size": size,
    }


async def revoke_share(request, db, ctx):
    """管理员强制撤销分享（业务逻辑在 ShareService 层）"""
    token = request.path_params["token"]
    from ..services.share_service import ShareService
    svc = ShareService(db, tenant_id=0)
    await svc.admin_revoke_share(token)
    return {"revoked": True}


async def get_stats(request, db, ctx):
    """平台存储统计 Dashboard（统计在 Service 层）"""
    from ..services.quota_service import QuotaService
    svc  = QuotaService(db, tenant_id=0)
    data = await svc.admin_stats()
    return data


def _quota_schema(q) -> dict:
    return {
        "tenantId":    q.tenant_id,
        "quotaBytes":  q.quota_bytes,
        "usedBytes":   q.used_bytes,
        "freeBytes":   q.free_bytes,
        "usedPercent": q.used_percent,
    }


def _share_admin_schema(s) -> dict:
    return {
        "id":          s.id,
        "tenantId":    s.tenant_id,
        "nodeId":      s.node_id,
        "shareToken":  s.share_token,
        "permission":  s.permission,
        "isActive":    s.is_active,
        "expiresAt":   s.expires_at.isoformat() if s.expires_at else None,
        "accessCount": s.access_count,
        "createdAt":   s.created_at.isoformat() if s.created_at else None,
    }
