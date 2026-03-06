"""
异常基类模块

定义应用异常的基类和通用异常类
"""

from typing import Any


class AppException(Exception):
    """
    应用异常基类

    所有业务异常都应继承此类

    Attributes:
        code: 业务错误码
        message: 错误消息
        status_code: HTTP 状态码
        data: 附加数据
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
        初始化异常

        Args:
            message: 错误消息，支持 i18n key 或直接文本
            code: 业务错误码
            status_code: HTTP 状态码
            data: 附加数据
        """
        from app.core.i18n import _ as translate

        self.message = message or translate(self.default_message)
        self.code = code or self.__class__.code
        self.status_code = status_code or self.__class__.status_code
        self.data = data
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为响应字典"""
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }


class ValidationException(AppException):
    """
    数据验证异常

    用于请求参数验证失败
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
        初始化验证异常

        Args:
            message: 错误消息
            errors: 验证错误详情列表
        """
        super().__init__(message=message, data={"errors": errors} if errors else None)
        self.errors = errors


class AuthenticationException(AppException):
    """
    认证异常

    用于用户身份验证失败
    """

    code = 4010
    status_code = 401
    default_message = "common.unauthorized"


class AuthorizationException(AppException):
    """
    授权异常

    用于用户权限不足
    """

    code = 4030
    status_code = 403
    default_message = "common.forbidden"


class NotFoundException(AppException):
    """
    资源不存在异常
    """

    code = 4040
    status_code = 404
    default_message = "common.not_found"


class ConflictException(AppException):
    """
    资源冲突异常

    用于资源已存在或状态冲突
    """

    code = 4090
    status_code = 409
    default_message = "common.failed"


class BusinessException(AppException):
    """
    业务逻辑异常

    用于业务规则校验失败
    """

    code = 4220
    status_code = 422
    default_message = "common.failed"


class DependencyBlockedException(BusinessException):
    """
    删除被依赖阻止异常

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
        """重写序列化，携带 dependencies 字段"""
        base = super().to_dict()
        base["dependencies"] = self.dependencies
        return base


class RateLimitException(AppException):
    """
    请求频率限制异常
    """

    code = 4290
    status_code = 429
    default_message = "ai.rate_limited"


class ExternalServiceException(AppException):
    """
    外部服务异常

    用于调用外部 API 失败
    """

    code = 5020
    status_code = 502
    default_message = "common.server_error"


class ServiceUnavailableException(AppException):
    """
    服务不可用异常
    """

    code = 5030
    status_code = 503
    default_message = "common.server_error"


# 导出
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
