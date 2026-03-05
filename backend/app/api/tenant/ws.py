"""
租户管理端 WebSocket 相关 HTTP API

提供当前租户管理员在线状态查询接口。
"""

from fastapi import APIRouter

from app.core.deps import ActiveTenantAdmin
from app.core.response import success
from app.rbac.decorators import auth_only
from app.sio.presence import PresenceManager

router = APIRouter(prefix="/ws", tags=["WebSocket 在线状态"])


@router.get("/presence", summary="当前租户管理员在线状态")
@auth_only
async def get_tenant_presence(
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取当前租户的管理员在线状态

    自动从当前登录的租户管理员获取 tenant_id，
    确保租户隔离（只能查看本租户的在线状态）。
    """
    tenant_id = tenant_admin.tenant_id
    details = await PresenceManager.get_online_details("tenant_admin", tenant_id)
    online_ids = list(details.keys())

    return success(data={
        "online_ids": online_ids,
        "total_online": len(online_ids),
        "tenant_id": tenant_id,
        "details": {str(k): v for k, v in details.items()},
    })
