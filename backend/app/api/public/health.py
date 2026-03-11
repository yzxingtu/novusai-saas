"""
Health Check 端点 / Health Check Endpoint

供负载均衡器/容器编排探活使用，不走统一响应包装。
Used by load balancer/container orchestration for health probing, bypasses unified response wrapper.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.deps import DbSession
from app.rbac.decorators import public

router = APIRouter(tags=["Health Check"])


@router.get("/health", summary="Health Check")
@public
async def health_check(db: DbSession):
    checks: dict = {}

    # DB 连通性 / DB connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Redis 连通性 / Redis connectivity
    try:
        from app.core.redis import RedisManager

        ok = await RedisManager.health_check()
        checks["redis"] = "ok" if ok else "error"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        },
    )


__all__ = ["router"]
