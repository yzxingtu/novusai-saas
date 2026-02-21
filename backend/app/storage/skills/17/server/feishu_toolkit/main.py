import logging
import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from feishu_toolkit.calendar_api import router as calendar_router
from feishu_toolkit.messaging_api import router as messaging_router
from feishu_toolkit.approval_api import router as approval_router
from feishu_toolkit.bitable_api import router as bitable_router
from feishu_toolkit.contacts_api import router as contacts_router
from feishu_toolkit.attendance_api import router as attendance_router

app = FastAPI(
    title="飞书办公套件 API",
    description="飞书办公套件代理服务 — 日历/消息/审批/多维表格/通讯录/考勤",
    version="0.1.0",
    servers=[{"url": os.getenv("OPENAPI_SERVER_URL", "http://127.0.0.1:8002")}],
)
logger = logging.getLogger("feishu_toolkit.main")

# ── 注册子路由 ────────────────────────────────────────────
app.include_router(calendar_router, prefix="/calendar", tags=["日历与会议室"])
app.include_router(messaging_router, prefix="/messaging", tags=["消息"])
app.include_router(approval_router, prefix="/approval", tags=["审批"])
app.include_router(bitable_router, prefix="/bitable", tags=["多维表格"])
app.include_router(contacts_router, prefix="/contacts", tags=["通讯录"])
app.include_router(attendance_router, prefix="/attendance", tags=["考勤"])


# ── 健康检查 ──────────────────────────────────────────────
@app.get("/ping")
def ping() -> dict[str, str]:
    """健康检查"""
    return {"message": "pong"}


# ── 全局异常处理 ──────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.error(
        "Validation error on %s %s. body=%s errors=%s",
        request.method,
        request.url.path,
        exc.body,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors()}),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("feishu_toolkit.main:app", host="0.0.0.0", port=port)
