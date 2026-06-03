"""
存储异常模块 / Storage Exception Module

定义存储驱动相关的异常类
Defines storage driver related exception classes.
"""

from app.exceptions.base import AppException


class StorageError(AppException):
    code = 5001
    status_code = 500
    default_message = "storage.error.driver_error"


class StorageConfigError(StorageError):
    code = 5002
    status_code = 500
    default_message = "storage.error.config_error"


class StorageNotFoundError(StorageError):
    code = 4041
    status_code = 404
    default_message = "common.not_found"


__all__ = ["StorageError", "StorageConfigError", "StorageNotFoundError"]
