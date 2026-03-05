"""
异常模块

提供应用的异常类层次结构
"""

from app.exceptions.base import (
    AppException,
    AuthenticationException,
    AuthorizationException,
    BusinessException,
    ConflictException,
    DependencyBlockedException,
    ExternalServiceException,
    NotFoundException,
    RateLimitException,
    ServiceUnavailableException,
    ValidationException,
)
from app.exceptions.storage import (
    StorageConfigError,
    StorageError,
    StorageNotFoundError,
)

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
    "StorageError",
    "StorageConfigError",
    "StorageNotFoundError",
]
