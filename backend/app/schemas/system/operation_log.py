"""
操作日志相关 Schema

定义操作日志 API 的请求和响应数据结构
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class OperationLogResponse(BaseSchema):
    """操作日志响应"""
    
    id: int = Field(..., description="日志 ID")
    tenant_id: int | None = Field(None, description="租户 ID")
    user_type: str = Field(..., description="用户类型")
    user_id: int | None = Field(None, description="用户 ID")
    username: str | None = Field(None, description="用户名")
    module: str | None = Field(None, description="业务模块")
    action: str | None = Field(None, description="操作类型")
    resource: str | None = Field(None, description="资源标识")
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="请求路径")
    query_params: dict | None = Field(None, description="查询参数")
    request_body: dict | None = Field(None, description="请求体摘要")
    status_code: int | None = Field(None, description="HTTP 状态码")
    response_code: int | None = Field(None, description="业务响应码")
    response_message: str | None = Field(None, description="响应消息")
    ip: str | None = Field(None, description="客户端 IP")
    user_agent: str | None = Field(None, description="User-Agent")
    duration_ms: int | None = Field(None, description="请求耗时（毫秒）")
    created_at: datetime = Field(..., description="创建时间")
    
    @classmethod
    def from_model(cls, log) -> "OperationLogResponse":
        """从模型创建响应"""
        return cls(
            id=log.id,
            tenant_id=log.tenant_id,
            user_type=log.user_type,
            user_id=log.user_id,
            username=log.username,
            module=log.module,
            action=log.action,
            resource=log.resource,
            method=log.method,
            path=log.path,
            query_params=log.query_params,
            request_body=log.request_body,
            status_code=log.status_code,
            response_code=log.response_code,
            response_message=log.response_message,
            ip=log.ip,
            user_agent=log.user_agent,
            duration_ms=log.duration_ms,
            created_at=log.created_at,
        )


class OperationLogListResponse(BaseSchema):
    """操作日志列表项响应（简化版）"""
    
    id: int = Field(..., description="日志 ID")
    tenant_id: int | None = Field(None, description="租户 ID")
    user_type: str = Field(..., description="用户类型")
    username: str | None = Field(None, description="用户名")
    module: str | None = Field(None, description="业务模块")
    action: str | None = Field(None, description="操作类型")
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="请求路径")
    status_code: int | None = Field(None, description="HTTP 状态码")
    response_code: int | None = Field(None, description="业务响应码")
    ip: str | None = Field(None, description="客户端 IP")
    duration_ms: int | None = Field(None, description="请求耗时（毫秒）")
    created_at: datetime = Field(..., description="创建时间")
    
    @classmethod
    def from_model(cls, log) -> "OperationLogListResponse":
        """从模型创建列表响应"""
        return cls(
            id=log.id,
            tenant_id=log.tenant_id,
            user_type=log.user_type,
            username=log.username,
            module=log.module,
            action=log.action,
            method=log.method,
            path=log.path,
            status_code=log.status_code,
            response_code=log.response_code,
            ip=log.ip,
            duration_ms=log.duration_ms,
            created_at=log.created_at,
        )


class OperationLogDeleteRequest(BaseSchema):
    """批量删除日志请求"""
    
    ids: list[int] = Field(..., min_length=1, max_length=100, description="日志 ID 列表")


class LogStatsItem(BaseSchema):
    """日志统计项"""
    
    name: str = Field(..., description="分类名称")
    count: int = Field(..., description="数量")


class LogStatsResponse(BaseSchema):
    """日志统计响应"""
    
    by_module: list[LogStatsItem] = Field(default_factory=list, description="按模块统计")
    by_action: list[LogStatsItem] = Field(default_factory=list, description="按操作类型统计")
    total: int = Field(..., description="总数")


__all__ = [
    "OperationLogResponse",
    "OperationLogListResponse",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
]
