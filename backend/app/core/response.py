"""
统一响应封装模块 / Unified Response Module

提供标准化的 API 响应格式和封装方法
Provides standardized API response formats and wrapper methods.
"""

import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.i18n import _
from app.middleware.trace import trace_id_var


def _serialize(data: Any) -> Any:
    """
    将 Pydantic 模型实例转为 dict，触发 model_serializer；
    同时将 naive datetime 标记为 UTC 后输出 ISO 8601。
    Convert Pydantic model instances to dict (triggering model_serializer)
    and ensure naive datetimes are serialized with UTC timezone indicator.

    解决两个问题 / Fixes two issues:
    1. FastAPI 的 jsonable_encoder 绕过自定义 model_serializer，丢失 +00:00
    2. to_dict() 返回的 naive datetime 被前端误判为本地时间
    """
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, datetime):
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return data.isoformat()
    if isinstance(data, list):
        return [_serialize(item) for item in data]
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    return data

T = TypeVar("T")


# ============================================
# 响应模型 / Response Models
# ============================================

class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应模型 / Unified API Response Model

    所有 API 响应都遵循此格式 / All API responses follow this format:
    {
        "code": 0,
        "message": "success",
        "data": ...
    }
    """

    code: int = Field(default=0, description="响应状态码，0 表示成功 / Response code, 0 means success")
    message: str = Field(default="success", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")


class PagedData(BaseModel, Generic[T]):
    """分页数据模型 / Paged Data Model"""

    items: list[T] = Field(default_factory=list, description="数据列表 / Data list")
    total: int = Field(default=0, description="总记录数 / Total record count")
    page: int = Field(default=1, description="当前页码 / Current page number")
    page_size: int = Field(default=20, description="每页数量 / Items per page")
    pages: int = Field(default=0, description="总页数 / Total pages")


def get_current_trace_id() -> str | None:
    """Get current trace_id from ContextVar / 从 ContextVar 获取当前 trace_id"""
    trace_id = trace_id_var.get().strip()
    return trace_id or None


def include_debug_payload() -> bool:
    """Whether current environment should expose debug payload / 当前环境是否应暴露调试载荷"""
    return bool(settings.DEBUG)


def build_exception_debug(
    exc: BaseException,
    *,
    detail: Any = None,
    include_traceback: bool = True,
) -> dict[str, Any]:
    """
    Build structured debug payload from exception / 从异常构建结构化 debug 载荷
    """
    debug: dict[str, Any] = {
        "type": type(exc).__name__,
        "detail": detail if detail is not None else str(exc),
    }

    if include_traceback and sys.exc_info()[0] is not None:
        debug["traceback"] = traceback.format_exc()

    return debug


def build_error_payload(
    *,
    message: str | None = None,
    code: int | str = 4000,
    data: Any = None,
    trace_id: str | None = None,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
    include_debug: bool | None = None,
) -> dict[str, Any]:
    """
    Build unified error payload / 构建统一错误响应载荷
    """
    resolved_trace_id = trace_id or get_current_trace_id()
    payload: dict[str, Any] = {
        "code": code,
        "message": message or _("common.failed"),
        "data": _serialize(data),
        "trace_id": resolved_trace_id,
    }

    if extra:
        payload.update({key: _serialize(value) for key, value in extra.items()})

    if include_debug is None:
        include_debug = include_debug_payload()
    if include_debug and debug is not None:
        payload["debug"] = _serialize(debug)

    return payload


def build_error_event(
    *,
    code: int | str,
    message: str | None = None,
    data: Any = None,
    trace_id: str | None = None,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
    include_debug: bool | None = None,
) -> dict[str, Any]:
    """
    Build unified SSE/Socket error event payload / 构建统一 SSE/Socket 错误事件载荷
    """
    return {
        "error": True,
        **build_error_payload(
            message=message,
            code=code,
            data=data,
            trace_id=trace_id,
            debug=debug,
            extra=extra,
            include_debug=include_debug,
        ),
    }


def build_socket_connect_error(
    reason: str,
    *,
    code: int | str,
    message: str | None = None,
    data: Any = None,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
    include_debug: bool | None = None,
) -> ConnectionRefusedError:
    """
    Build Socket.IO connect refusal carrying structured data.
    / 构建携带结构化数据的 Socket.IO 握手拒绝异常。
    """
    merged_extra = {"reason": reason}
    if extra:
        merged_extra.update(extra)

    return ConnectionRefusedError(
        reason,
        build_error_payload(
            message=message,
            code=code,
            data=data,
            debug=debug,
            extra=merged_extra,
            include_debug=include_debug,
        ),
    )


# ============================================
# 响应封装函数 / Response Wrapper Functions
# ============================================

def success(
    data: Any = None,
    message: str | None = None,
    code: int = 0,
) -> dict[str, Any]:
    """
    成功响应 / Success response

    Args:
        data: 响应数据 / Response data
        message: 响应消息，默认使用 i18n 的 common.success / Response message, defaults to i18n common.success
        code: 状态码，默认 0 / Status code, default 0

    Returns:
        响应字典 / Response dict

    Examples:
        >>> return success(data={"id": 1})
        {"code": 0, "message": "操作成功", "data": {"id": 1}}
    """
    return {
        "code": code,
        "message": message or _("common.success"),
        "data": _serialize(data),
    }


def error(
    message: str | None = None,
    code: int = 4000,
    data: Any = None,
    status_code: int = 400,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """
    错误响应 / Error response

    Args:
        message: 错误消息 / Error message
        code: 业务错误码 / Business error code
        data: 附加数据（如字段验证错误详情） / Extra data (e.g. field validation error details)
        status_code: HTTP 状态码 / HTTP status code

    Returns:
        JSONResponse

    Examples:
        >>> return error(message="参数错误", code=4001)
    """
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            message=message,
            code=code,
            data=data,
            debug=debug,
            extra=extra,
        ),
    )


def created(
    data: Any = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    创建成功响应 / Created response

    Args:
        data: 创建的资源数据 / Created resource data
        message: 响应消息 / Response message

    Returns:
        响应字典 / Response dict
    """
    return {
        "code": 0,
        "message": message or _("common.created"),
        "data": _serialize(data),
    }


def updated(
    data: Any = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    更新成功响应 / Updated response

    Args:
        data: 更新后的资源数据 / Updated resource data
        message: 响应消息 / Response message

    Returns:
        响应字典 / Response dict
    """
    return {
        "code": 0,
        "message": message or _("common.updated"),
        "data": _serialize(data),
    }


def deleted(
    message: str | None = None,
) -> dict[str, Any]:
    """
    删除成功响应 / Deleted response

    Args:
        message: 响应消息 / Response message

    Returns:
        响应字典 / Response dict
    """
    return {
        "code": 0,
        "message": message or _("common.deleted"),
        "data": None,
    }


def paginated(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    message: str | None = None,
) -> dict[str, Any]:
    """
    分页响应 / Paginated response

    Args:
        items: 当前页数据列表 / Current page data list
        total: 总记录数 / Total record count
        page: 当前页码 / Current page number
        page_size: 每页数量 / Items per page
        message: 响应消息 / Response message

    Returns:
        响应字典 / Response dict

    Examples:
        >>> return paginated(items=[...], total=100, page=1, page_size=20)
    """
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "code": 0,
        "message": message or _("common.success"),
        "data": {
            "items": _serialize(items),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        },
    }


def no_content() -> JSONResponse:
    """
    无内容响应（HTTP 204） / No content response (HTTP 204)

    Returns:
        JSONResponse
    """
    return JSONResponse(
        status_code=204,
        content=None,
    )


# ============================================
# 错误响应快捷方法 / Error Response Shortcuts
# ============================================

def bad_request(
    message: str | None = None,
    data: Any = None,
) -> JSONResponse:
    """
    错误请求响应（HTTP 400） / Bad request response (HTTP 400)
    """
    return error(
        message=message or _("common.invalid_request"),
        code=4000,
        data=data,
        status_code=400,
    )


def unauthorized(
    message: str | None = None,
) -> JSONResponse:
    """
    未授权响应（HTTP 401） / Unauthorized response (HTTP 401)
    """
    return error(
        message=message or _("common.unauthorized"),
        code=4010,
        status_code=401,
    )


def forbidden(
    message: str | None = None,
) -> JSONResponse:
    """
    禁止访问响应（HTTP 403） / Forbidden response (HTTP 403)
    """
    return error(
        message=message or _("common.forbidden"),
        code=4030,
        status_code=403,
    )


def not_found(
    message: str | None = None,
) -> JSONResponse:
    """
    资源不存在响应（HTTP 404） / Not found response (HTTP 404)
    """
    return error(
        message=message or _("common.not_found"),
        code=4040,
        status_code=404,
    )


def validation_error(
    message: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """
    验证错误响应（HTTP 422） / Validation error response (HTTP 422)
    """
    return error(
        message=message or _("common.validation_error"),
        code=4220,
        data={"errors": errors} if errors else None,
        status_code=422,
    )


def server_error(
    message: str | None = None,
) -> JSONResponse:
    """
    服务器错误响应（HTTP 500） / Server error response (HTTP 500)
    """
    return error(
        message=message or _("common.server_error"),
        code=5000,
        status_code=500,
    )


# 导出 / Exports
__all__ = [
    "ApiResponse",
    "PagedData",
    "get_current_trace_id",
    "include_debug_payload",
    "build_exception_debug",
    "build_error_payload",
    "build_error_event",
    "build_socket_connect_error",
    "success",
    "error",
    "created",
    "updated",
    "deleted",
    "paginated",
    "no_content",
    "bad_request",
    "unauthorized",
    "forbidden",
    "not_found",
    "validation_error",
    "server_error",
]
