"""
异常模块

提供应用的异常类层次结构
"""

from app.exceptions.base import (
    AppException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    NotFoundException,
    ConflictException,
    BusinessException,
    DependencyBlockedException,
    RateLimitException,
    ExternalServiceException,
    ServiceUnavailableException,
)
from app.exceptions.storage import StorageError, StorageConfigError, StorageNotFoundError

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
