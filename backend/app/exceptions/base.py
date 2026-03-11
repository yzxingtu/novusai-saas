"""
异常基类模块 / Exception Base Module

定义应用异常的基类和通用异常类
Defines application exception base class and common exception classes.
"""

from typing import Any


class AppException(Exception):
    """
    Application Exception Base Class / 应用异常基类

    All business exceptions should inherit from this class.
    所有业务异常都应继承此类。

    Attributes:
        code: Business error code / 业务错误码
        message: Error message / 错误消息
        status_code: HTTP status code / HTTP 状态码
        data: Additional data / 附加数据
    """

    code: int = 5000
    status_code: int = 500
    default_message: str = "common.server_error"

    def __init__(
        self,
        message: str | None = None,
        code: int | None = None,
        status_code: int | None = None,
        data: Any = None,
    ):
        """
        Initialize exception.
        初始化异常。

        Args:
            message: Error message, supports i18n key or plain text / 错误消息，支持 i18n key 或直接文本
            code: Business error code / 业务错误码
            status_code: HTTP status code / HTTP 状态码
            data: Additional data / 附加数据
        """
        from app.core.i18n import _ as translate

        self.message = message or translate(self.default_message)
        self.code = code or self.__class__.code
        self.status_code = status_code or self.__class__.status_code
        self.data = data
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to response dict / 转换为响应字典"""
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }


class ValidationException(AppException):
    """
    Validation Exception / 数据验证异常

    Used for request parameter validation failure.
    用于请求参数验证失败。
    """

    code = 4001
    status_code = 422
    default_message = "common.validation_error"

    def __init__(
        self,
        message: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ):
        """
        Initialize validation exception.
        初始化验证异常。

        Args:
            message: Error message / 错误消息
            errors: Validation error details list / 验证错误详情列表
        """
        super().__init__(message=message, data={"errors": errors} if errors else None)
        self.errors = errors


class AuthenticationException(AppException):
    """
    Authentication Exception / 认证异常

    Used for user identity verification failure.
    用于用户身份验证失败。
    """

    code = 4010
    status_code = 401
    default_message = "common.unauthorized"


class AuthorizationException(AppException):
    """
    Authorization Exception / 授权异常

    Used for insufficient user permissions.
    用于用户权限不足。
    """

    code = 4030
    status_code = 403
    default_message = "common.forbidden"


class NotFoundException(AppException):
    """
    Not Found Exception / 资源不存在异常
    """

    code = 4040
    status_code = 404
    default_message = "common.not_found"


class ConflictException(AppException):
    """
    Conflict Exception / 资源冲突异常

    Used for resource already exists or state conflict.
    用于资源已存在或状态冲突。
    """

    code = 4090
    status_code = 409
    default_message = "common.failed"


class BusinessException(AppException):
    """
    Business Exception / 业务逻辑异常

    Used for business rule validation failure.
    用于业务规则校验失败。
    """

    code = 4220
    status_code = 422
    default_message = "common.failed"


class DependencyBlockedException(BusinessException):
    """
    Dependency Blocked Exception / 删除被依赖阻止异常

    When deleting a record with active dependency references, blocks deletion and returns dependency details.
    Frontend identifies by error_code=4221 and shows dependency detail dialog.
    当删除记录时发现有活跃依赖引用，阻止删除并返回依赖详情。
    前端通过 error_code=4221 识别并弹出依赖详情弹窗。
    """

    code = 4221
    status_code = 422
    default_message = "common.error.has_dependencies"

    def __init__(
        self,
        message: str | None = None,
        dependencies: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message=message)
        self.dependencies = dependencies or []

    def to_dict(self) -> dict[str, Any]:
        """Override serialization with dependencies field / 重写序列化，携带 dependencies 字段"""
        base = super().to_dict()
        base["dependencies"] = self.dependencies
        return base


class RateLimitException(AppException):
    """
    Rate Limit Exception / 请求频率限制异常
    """

    code = 4290
    status_code = 429
    default_message = "ai.rate_limited"


class ExternalServiceException(AppException):
    """
    External Service Exception / 外部服务异常

    Used for external API call failure.
    用于调用外部 API 失败。
    """

    code = 5020
    status_code = 502
    default_message = "common.server_error"


class ServiceUnavailableException(AppException):
    """
    Service Unavailable Exception / 服务不可用异常
    """

    code = 5030
    status_code = 503
    default_message = "common.server_error"


# Exports / 导出
__all__ = [
    "AppException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "NotFoundException",
    "ConflictException",
    "BusinessException",
    "DependencyBlockedException",
    "RateLimitException",
    "ExternalServiceException",
    "ServiceUnavailableException",
]
