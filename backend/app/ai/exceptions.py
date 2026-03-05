"""
AI 网关统一异常层次

捕获各供应商 SDK 的原始异常，转换为统一异常类型，
使上层业务代码无需感知具体供应商差异。
"""

import contextlib

from app.core.i18n import _


class AIGatewayError(Exception):
    """
    AI 网关异常基类

    所有 AI 网关相关异常均继承此类
    """

    error_code: str = "ai_gateway_error"
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        provider_code: str | None = None,
        model_code: str | None = None,
        error_code: str | None = None,
        retry_after: int | None = None,
        original_error: Exception | None = None,
    ):
        """
        初始化 AI 网关异常

        Args:
            message: 错误消息
            provider_code: 供应商代码（如 openai_compatible）
            model_code: 模型代码（如 gpt-4）
            error_code: 供应商原始错误码
            retry_after: 建议重试等待秒数
            original_error: 原始异常对象
        """
        self.message = message or _("ai.request_failed")
        self.provider_code = provider_code
        self.model_code = model_code
        self.error_code = error_code or self.__class__.error_code
        self.retry_after = retry_after
        self.original_error = original_error
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为可序列化字典"""
        result = {
            "error_code": self.error_code,
            "message": self.message,
            "provider_code": self.provider_code,
            "model_code": self.model_code,
        }
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        return result


class ProviderError(AIGatewayError):
    """
    供应商通用错误

    供应商 API 返回的通用错误（非认证、非限流、非超时）
    """

    error_code = "provider_error"
    status_code = 502


class ProviderRateLimitError(AIGatewayError):
    """
    供应商速率限制错误

    供应商 API 返回 HTTP 429，表示请求过于频繁
    """

    error_code = "provider_rate_limit"
    status_code = 429


class ProviderAuthError(AIGatewayError):
    """
    供应商认证错误

    API Key 无效、过期或权限不足
    """

    error_code = "provider_auth_error"
    status_code = 401


class ModelNotFoundError(AIGatewayError):
    """
    模型不存在错误

    请求的模型在供应商中不可用
    """

    error_code = "model_not_found"
    status_code = 404


class ProviderTimeoutError(AIGatewayError):
    """
    供应商超时错误

    请求供应商 API 超时
    """

    error_code = "provider_timeout"
    status_code = 504


class ProviderConnectionError(AIGatewayError):
    """
    供应商连接错误

    无法连接到供应商 API（网络故障等）
    """

    error_code = "provider_connection_error"
    status_code = 502


class ContentFilterError(AIGatewayError):
    """
    内容过滤错误

    请求或响应被供应商内容安全策略拦截
    """

    error_code = "content_filter"
    status_code = 400


class ContextLengthExceededError(AIGatewayError):
    """
    上下文长度超出错误

    输入 tokens 超出模型上下文窗口限制
    """

    error_code = "context_length_exceeded"
    status_code = 400


# ========== 供应商原始异常转换工具函数 ==========

def convert_openai_error(
    error: Exception,
    provider_code: str = "openai",
    model_code: str | None = None,
) -> AIGatewayError:
    """
    将 OpenAI SDK 异常转换为统一异常

    Args:
        error: OpenAI SDK 原始异常
        provider_code: 供应商代码
        model_code: 模型代码

    Returns:
        统一的 AIGatewayError 子类实例
    """
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        RateLimitError,
    )

    kwargs = {
        "provider_code": provider_code,
        "model_code": model_code,
        "original_error": error,
    }

    if isinstance(error, APITimeoutError):
        return ProviderTimeoutError(
            message=_("ai.error.provider_timeout"),
            **kwargs,
        )

    if isinstance(error, APIConnectionError):
        return ProviderConnectionError(
            message=_("ai.error.provider_connection"),
            **kwargs,
        )

    if isinstance(error, AuthenticationError):
        return ProviderAuthError(
            message=_("ai.error.provider_auth"),
            error_code=getattr(error, "code", None),
            **kwargs,
        )

    if isinstance(error, RateLimitError):
        # 尝试从响应头获取 retry-after
        retry_after = None
        if hasattr(error, "response") and error.response is not None:
            retry_header = error.response.headers.get("retry-after")
            if retry_header:
                with contextlib.suppress(ValueError, TypeError):
                    retry_after = int(retry_header)
        return ProviderRateLimitError(
            message=_("ai.error.provider_rate_limit"),
            retry_after=retry_after,
            **kwargs,
        )

    if isinstance(error, NotFoundError):
        return ModelNotFoundError(
            message=_("ai.error.model_not_found"),
            **kwargs,
        )

    if isinstance(error, BadRequestError):
        error_message = str(error)
        # 检查是否为上下文长度超出
        if "context_length" in error_message.lower() or "maximum context" in error_message.lower():
            return ContextLengthExceededError(
                message=_("ai.error.context_length_exceeded"),
                **kwargs,
            )
        # 检查是否为内容过滤
        if "content_filter" in error_message.lower() or "content_policy" in error_message.lower():
            return ContentFilterError(
                message=_("ai.error.content_filtered"),
                **kwargs,
            )
        return ProviderError(
            message=str(error),
            error_code=getattr(error, "code", None),
            **kwargs,
        )

    if isinstance(error, APIStatusError):
        status = getattr(error, "status_code", 500)
        # HTTP 5xx → 供应商服务端错误
        if 500 <= status < 600:
            return ProviderError(
                message=_("ai.error.provider_server_error"),
                error_code=str(status),
                **kwargs,
            )
        return ProviderError(
            message=str(error),
            error_code=str(status),
            **kwargs,
        )

    # 兜底：未知异常包装为 ProviderError
    return ProviderError(
        message=str(error),
        **kwargs,
    )


def is_retryable(error: AIGatewayError) -> bool:
    """
    判断异常是否可重试

    仅 ProviderTimeoutError 和供应商 5xx 错误可重试。
    ProviderRateLimitError 如果有 retry_after 也可重试。
    4xx 错误（认证、参数等）不重试。

    Args:
        error: AI 网关异常

    Returns:
        是否可重试
    """
    if isinstance(error, ProviderTimeoutError):
        return True
    if isinstance(error, ProviderConnectionError):
        return True
    if isinstance(error, ProviderRateLimitError) and error.retry_after is not None:
        return True
    if isinstance(error, ProviderError) and error.error_code and error.error_code.isdigit():
        status = int(error.error_code)
        return 500 <= status < 600
    return False


__all__ = [
    # 异常类
    "AIGatewayError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderAuthError",
    "ModelNotFoundError",
    "ProviderTimeoutError",
    "ProviderConnectionError",
    "ContentFilterError",
    "ContextLengthExceededError",
    # 转换函数
    "convert_openai_error",
    # 工具函数
    "is_retryable",
]
