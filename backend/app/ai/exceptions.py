"""
AI Gateway Unified Exception Hierarchy / AI 网关统一异常层次

Captures raw exceptions from provider SDKs and converts them to unified types,
so upper-layer business code need not be aware of provider differences.
捕获各供应商 SDK 的原始异常，转换为统一异常类型，使上层业务代码无需感知具体供应商差异。
"""

import contextlib

from app.core.i18n import _


class AIGatewayError(Exception):
    """
    AI Gateway base exception / AI 网关异常基类

    All AI gateway exceptions inherit from this class.
    所有 AI 网关相关异常均继承此类。
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
        Initialize AI gateway exception.
        初始化 AI 网关异常。

        Args:
            message: Error message / 错误消息
            provider_code: Provider code (e.g. openai_compatible) / 供应商代码
            model_code: Model code (e.g. gpt-4) / 模型代码
            error_code: Provider original error code / 供应商原始错误码
            retry_after: Suggested retry wait seconds / 建议重试等待秒数
            original_error: Original exception object / 原始异常对象
        """
        self.message = message or _("ai.request_failed")
        self.provider_code = provider_code
        self.model_code = model_code
        self.error_code = error_code or self.__class__.error_code
        self.retry_after = retry_after
        self.original_error = original_error
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert to serializable dict / 转换为可序列化字典"""
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
    Provider general error / 供应商通用错误

    Generic error from provider API (not auth, rate-limit, or timeout).
    供应商 API 返回的通用错误（非认证、非限流、非超时）。
    """

    error_code = "provider_error"
    status_code = 502


class ProviderRateLimitError(AIGatewayError):
    """
    Provider rate limit error / 供应商速率限制错误

    Provider API returned HTTP 429, too many requests.
    供应商 API 返回 HTTP 429，表示请求过于频繁。
    """

    error_code = "provider_rate_limit"
    status_code = 429


class ProviderAuthError(AIGatewayError):
    """
    Provider auth error / 供应商认证错误

    API Key invalid, expired, or insufficient permissions.
    API Key 无效、过期或权限不足。
    """

    error_code = "provider_auth_error"
    status_code = 401


class ModelNotFoundError(AIGatewayError):
    """
    Model not found error / 模型不存在错误

    Requested model not available at the provider.
    请求的模型在供应商中不可用。
    """

    error_code = "model_not_found"
    status_code = 404


class ProviderTimeoutError(AIGatewayError):
    """
    Provider timeout error / 供应商超时错误

    Request to provider API timed out.
    请求供应商 API 超时。
    """

    error_code = "provider_timeout"
    status_code = 504


class ProviderConnectionError(AIGatewayError):
    """
    Provider connection error / 供应商连接错误

    Cannot connect to provider API (network failure, etc.).
    无法连接到供应商 API（网络故障等）。
    """

    error_code = "provider_connection_error"
    status_code = 502


class ContentFilterError(AIGatewayError):
    """
    Content filter error / 内容过滤错误

    Request or response blocked by provider content safety policy.
    请求或响应被供应商内容安全策略拦截。
    """

    error_code = "content_filter"
    status_code = 400


class ContextLengthExceededError(AIGatewayError):
    """
    Context length exceeded error / 上下文长度超出错误

    Input tokens exceed model context window limit.
    输入 tokens 超出模型上下文窗口限制。
    """

    error_code = "context_length_exceeded"
    status_code = 400


# ========== Provider exception conversion utilities / 供应商原始异常转换工具函数 ==========


def convert_openai_error(
    error: Exception,
    provider_code: str = "openai",
    model_code: str | None = None,
) -> AIGatewayError:
    """
    Convert OpenAI SDK exception to unified exception.
    将 OpenAI SDK 异常转换为统一异常。

    Args:
        error: OpenAI SDK original exception / OpenAI SDK 原始异常
        provider_code: Provider code / 供应商代码
        model_code: Model code / 模型代码

    Returns:
        Unified AIGatewayError subclass instance / 统一的 AIGatewayError 子类实例
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
        # Try to get retry-after from response headers / 尝试从响应头获取 retry-after
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
        error_lower = error_message.lower()
        # Check if context length exceeded / 检查是否为上下文长度超出
        if "context_length" in error_lower or "maximum context" in error_lower:
            return ContextLengthExceededError(
                message=_("ai.error.context_length_exceeded"),
                **kwargs,
            )
        # Check if content filter / 检查是否为内容过滤
        if "content_filter" in error_lower or "content_policy" in error_lower:
            return ContentFilterError(
                message=_("ai.error.content_filtered"),
                **kwargs,
            )
        # Image URL fetch / parse failures (distinct from model lacking vision)
        # 图片 URL 拉取或解析失败（与「模型不支持视觉」区分）
        _inaccessible_markers = (
            "error while downloading",
            "unable to download",
            "could not fetch",
            "failed to download",
            "invalid_image_url",
            "invalid image",
            "malformed image",
            "image url",
        )
        if any(m in error_lower for m in _inaccessible_markers) and (
            "url" in error_lower
            or "download" in error_lower
            or "fetch" in error_lower
            or "image" in error_lower
        ):
            return ProviderError(
                message=_("ai.error.image_url_inaccessible"),
                error_code="image_url_inaccessible",
                **kwargs,
            )
        # Check if vision/image_url not supported by model / 检查模型是否不支持图片
        if "image_url" in error_lower or (
            "image" in error_lower and "unsupported" in error_lower
        ):
            return ProviderError(
                message=_("ai.error.vision_not_supported"),
                error_code="vision_not_supported",
                **kwargs,
            )
        return ProviderError(
            message=_("ai.request_failed"),
            error_code=getattr(error, "code", None),
            **kwargs,
        )

    if isinstance(error, APIStatusError):
        status = getattr(error, "status_code", 500)
        # HTTP 5xx → Provider server error / 供应商服务端错误
        if 500 <= status < 600:
            return ProviderError(
                message=_("ai.error.provider_server_error"),
                error_code=str(status),
                **kwargs,
            )
        return ProviderError(
            message=_("ai.request_failed"),
            error_code=str(status),
            **kwargs,
        )

    # Fallback: wrap unknown exception as ProviderError / 兜底：未知异常包装为 ProviderError
    return ProviderError(
        message=_("ai.request_failed"),
        **kwargs,
    )


def is_retryable(error: AIGatewayError) -> bool:
    """
    Determine if an exception is retryable.
    判断异常是否可重试。

    Retryable: ProviderTimeoutError, ProviderConnectionError, 5xx ProviderError,
    and ProviderRateLimitError with retry_after.
    仅 ProviderTimeoutError 和供应商 5xx 错误可重试。
    ProviderRateLimitError 如果有 retry_after 也可重试。4xx 错误不重试。

    Args:
        error: AI gateway exception / AI 网关异常

    Returns:
        Whether retryable / 是否可重试
    """
    if isinstance(error, ProviderTimeoutError):
        return True
    if isinstance(error, ProviderConnectionError):
        return True
    if isinstance(error, ProviderRateLimitError) and error.retry_after is not None:
        return True
    if (
        isinstance(error, ProviderError)
        and error.error_code
        and error.error_code.isdigit()
    ):
        status = int(error.error_code)
        return 500 <= status < 600
    return False


__all__ = [
    # Exception classes / 异常类
    "AIGatewayError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderAuthError",
    "ModelNotFoundError",
    "ProviderTimeoutError",
    "ProviderConnectionError",
    "ContentFilterError",
    "ContextLengthExceededError",
    # Conversion functions / 转换函数
    "convert_openai_error",
    # Utility functions / 工具函数
    "is_retryable",
]
