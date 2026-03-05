"""
公开分享访问 API — auth=none 公开路由

Handler 签名：(request, db, ctx)
- 公开路由中 ctx.get_current_tenant_id() 返回 None
- 遇密码验证需限流（防暴力穷举）
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi.responses import JSONResponse

from app.core.i18n import _

_VERIFY_MAX_REQUESTS = 5
_VERIFY_WINDOW_SECONDS = 60
_verify_buckets: dict[str, list[float]] = defaultdict(list)


def _check_verify_rate_limit(request) -> JSONResponse | None:
    """IP 维度限流：5 次 / 60 秒。"""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    cutoff = now - _VERIFY_WINDOW_SECONDS

    bucket = [ts for ts in _verify_buckets.get(client_ip, []) if ts > cutoff]
    if len(bucket) >= _VERIFY_MAX_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={
                "code": 4290,
                "message": _("plugin.netdisk.error.verify_rate_limited"),
            },
        )

    bucket.append(now)
    _verify_buckets[client_ip] = bucket
    return None


async def access_share(request, db, ctx):
    """公开分享访问（无需登录）"""
    token = request.path_params["token"]
    from ..services.share_service import ShareService
    svc    = ShareService(db, tenant_id=0)
    result = await svc.access_share(token)
    return {
        "share": _share_public_schema(result["share"]),
        "node":  _node_public_schema(result["node"]),
    }


async def verify_share_password(request, db, ctx):
    """验证分享密码（限流：5 次/60 秒/IP）。"""
    rate_resp = _check_verify_rate_limit(request)
    if rate_resp is not None:
        return rate_resp

    token = request.path_params["token"]
    body  = await request.json()
    from ..services.share_service import ShareService
    svc = ShareService(db, tenant_id=0)
    ok  = await svc.verify_password(token, body.get("password", ""))
    return {"verified": ok}


async def download_share_file(request, db, ctx):
    """下载分享文件，返回签名 URL（无需登录）"""
    token   = request.path_params["token"]
    node_id = int(request.path_params["node_id"])
    from ..services.share_service import ShareService
    svc = ShareService(db, tenant_id=0)
    url = await svc.get_download_url(token, node_id)
    return {"url": url}


def _share_public_schema(share) -> dict:
    return {
        "shareToken":  share.share_token,
        "permission":  share.permission,
        "hasPassword": share.password_hash is not None,
        "expiresAt":   share.expires_at.isoformat() if share.expires_at else None,
        "accessCount": share.access_count,
    }


def _node_public_schema(node) -> dict:
    return {
        "id":       node.id,
        "name":     node.name,
        "nodeType": node.node_type,
        "size":     node.size_bytes,
        "mimeType": node.mime_type,
    }
