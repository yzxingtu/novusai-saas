"""
核心模块 / Core Module

包含应用配置、基类、依赖注入等核心组件
Contains application configuration, base classes, dependency injection and other core components.
"""

# 配置 / Configuration
# 基类 - 控制器 / Base Classes - Controller
from app.core.base_controller import BaseController, GlobalController, TenantController

# 基类 - 模型 / Base Classes - Model
from app.core.base_model import Base, BaseModel, TenantModel

# 基类 - 仓储 / Base Classes - Repository
from app.core.base_repository import BaseRepository, TenantRepository

# 基类 - 数据模式 / Base Classes - Schema
from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
    PageParams,
    PageResponse,
    TenantResponseSchema,
)

# 基类 - 服务 / Base Classes - Service
from app.core.base_service import BaseService, GlobalService, TenantService
from app.core.config import settings

# 数据库 / Database
from app.core.database import close_database, get_db, get_db_context, init_database

# 国际化 / Internationalization
from app.core.i18n import _, get_locale, set_locale, translate

# 日志 / Logging
from app.core.logging import LogManager, get_logger, init_logging

# 响应封装 / Response Wrappers
from app.core.response import (
    ApiResponse,
    PagedData,
    bad_request,
    created,
    deleted,
    error,
    forbidden,
    no_content,
    not_found,
    paginated,
    server_error,
    success,
    unauthorized,
    updated,
    validation_error,
)

__all__ = [
    # 配置 / Configuration
    "settings",
    # 国际化 / Internationalization
    "_",
    "translate",
    "get_locale",
    "set_locale",
    # 模型 / Model
    "Base",
    "BaseModel",
    "TenantModel",
    # 数据模式 / Schema
    "BaseSchema",
    "BaseCreateSchema",
    "BaseUpdateSchema",
    "BaseResponseSchema",
    "TenantResponseSchema",
    "PageParams",
    "PageResponse",
    # 仓储 / Repository
    "BaseRepository",
    "TenantRepository",
    # 服务 / Service
    "BaseService",
    "TenantService",
    "GlobalService",
    # 控制器 / Controller
    "BaseController",
    "TenantController",
    "GlobalController",
    # 数据库 / Database
    "get_db",
    "get_db_context",
    "init_database",
    "close_database",
    # 响应 / Response
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
    # 日志 / Logging
    "LogManager",
    "get_logger",
    "init_logging",
]
