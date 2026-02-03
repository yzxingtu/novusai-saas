from app.exceptions.base import AppException


class StorageError(AppException):
    code = 5001
    status_code = 500
    default_message = "common.server_error"


class StorageConfigError(StorageError):
    code = 5002
    status_code = 500
    default_message = "common.server_error"


class StorageNotFoundError(StorageError):
    code = 4041
    status_code = 404
    default_message = "common.not_found"


__all__ = ["StorageError", "StorageConfigError", "StorageNotFoundError"]
