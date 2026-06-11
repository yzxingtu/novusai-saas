"""
Internal Operations Module / 内部操作模块

Exposes the platform/tenant management API surface to built-in copilot agents
through a meta-tool channel (list / describe / invoke), executing requests
on behalf of the current conversation user with a short-lived proxy token.
通过 meta-tool 通道（list / describe / invoke）将平台/租户后台 API 面暴露给
内置运营 Copilot 智能体，使用短时效代理 token 以当前对话用户身份执行请求。
"""

from app.ai.internal_ops.catalog import (
    InternalOperation,
    get_operation,
    get_operation_catalog,
    search_operations,
)
from app.ai.internal_ops.proxy_token import issue_ai_proxy_token

__all__ = [
    "InternalOperation",
    "get_operation",
    "get_operation_catalog",
    "search_operations",
    "issue_ai_proxy_token",
]
