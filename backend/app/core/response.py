"""
统一响应封装模块

提供标准化的 API 响应格式和封装方法
"""

from typing import Any, TypeVar, Generic

from fastapi.responses import JSONResponse, ORJSONResponse
from pydantic import BaseModel, Field

from app.core.i18n import _


def _serialize(data: Any) -> Any:
    """
    将 Pydantic 模型实例转为 dict，触发 model_serializer。
    
    解决 FastAPI 的 jsonable_encoder 绕过自定义 model_serializer 的问题：
    当 Pydantic 模型直接传入 dict 响应时，jsonable_encoder 使用内部序列化，
    不会调用我们的 model_serializer，导致 datetime +00:00 丢失。
    """
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, list):
        return [_serialize(item) for item in data]
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    return data

T = TypeVar("T")


# ============================================
# 响应模型
# ============================================

class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应模型
    
    所有 API 响应都遵循此格式：
    {
        "code": 0,
        "message": "success",
        "data": ...
    }
    """
    
    code: int = Field(default=0, description="响应状态码，0 表示成功")
    message: str = Field(default="success", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")


class PagedData(BaseModel, Generic[T]):
    """分页数据模型"""
    
    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    pages: int = Field(default=0, description="总页数")


# ============================================
# 响应封装函数
# ============================================

def success(
    data: Any = None,
    message: str | None = None,
    code: int = 0,
) -> dict[str, Any]:
    """
    成功响应
    
    Args:
        data: 响应数据
        message: 响应消息，默认使用 i18n 的 common.success
        code: 状态码，默认 0
    
    Returns:
        响应字典
    
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
) -> JSONResponse:
    """
    错误响应
    
    Args:
        message: 错误消息
        code: 业务错误码
        data: 附加数据（如字段验证错误详情）
        status_code: HTTP 状态码
    
    Returns:
        JSONResponse
    
    Examples:
        >>> return error(message="参数错误", code=4001)
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message or _("common.failed"),
            "data": data,
        },
    )


def created(
    data: Any = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    创建成功响应
    
    Args:
        data: 创建的资源数据
        message: 响应消息
    
    Returns:
        响应字典
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
    更新成功响应
    
    Args:
        data: 更新后的资源数据
        message: 响应消息
    
    Returns:
        响应字典
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
    删除成功响应
    
    Args:
        message: 响应消息
    
    Returns:
        响应字典
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
    分页响应
    
    Args:
        items: 当前页数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页数量
        message: 响应消息
    
    Returns:
        响应字典
    
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
    无内容响应（HTTP 204）
    
    Returns:
        JSONResponse
    """
    return JSONResponse(
        status_code=204,
        content=None,
    )


# ============================================
# 错误响应快捷方法
# ============================================

def bad_request(
    message: str | None = None,
    data: Any = None,
) -> JSONResponse:
    """
    错误请求响应（HTTP 400）
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
    未授权响应（HTTP 401）
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
    禁止访问响应（HTTP 403）
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
    资源不存在响应（HTTP 404）
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
    验证错误响应（HTTP 422）
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
    服务器错误响应（HTTP 500）
    """
    return error(
        message=message or _("common.server_error"),
        code=5000,
        status_code=500,
    )


# 导出
__all__ = [
    "ApiResponse",
    "PagedData",
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
