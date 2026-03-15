"""
平台管理端 WebSocket 相关 HTTP API / Platform Admin WebSocket HTTP API

提供在线状态查询接口（页面初始化时加载）。
Provides online presence query endpoints (loaded during page initialization).
Socket.IO 实时推送由 app/sio/ namespace 处理。
Socket.IO real-time push is handled by app/sio/ namespace.
"""

from fastapi import APIRouter

from app.core.deps import ActiveAdmin
from app.core.response import success
from app.rbac.decorators import auth_only
from app.sio.presence import PresenceManager

router = APIRouter(prefix="/ws", tags=["WebSocket 在线状态 / WebSocket Presence"])


@router.get("/presence", summary="平台管理员在线状态")
@auth_only
async def get_admin_presence(
    admin: ActiveAdmin,
):
    """
    获取所有平台管理员的在线状态 / Get platform admin online presence.

    返回在线管理员 ID 列表和总在线数。
    Returns online admin ID list and total online count.
    """
    details = await PresenceManager.get_online_details("admin")
    online_ids = list(details.keys())

    return success(data={
        "online_ids": online_ids,
        "total_online": len(online_ids),
        "details": {str(k): v for k, v in details.items()},
    })


@router.get("/presence/tenant/{tenant_id}", summary="指定企业管理员在线状态")
@auth_only
async def get_tenant_admin_presence(
    tenant_id: int,
    admin: ActiveAdmin,
):
    """
    获取指定企业的管理员在线状态
    Get admin online presence for a specific tenant

    平台管理员可查看任意企业的管理员在线情况。
    Platform admins can view admin online status for any tenant.

    Args:
        tenant_id: 企业 ID / Tenant ID
    """
    details = await PresenceManager.get_online_details("tenant_admin", tenant_id)
    online_ids = list(details.keys())

    return success(data={
        "online_ids": online_ids,
        "total_online": len(online_ids),
        "tenant_id": tenant_id,
        "details": {str(k): v for k, v in details.items()},
    })
