"""
操作日志相关 Schema / Operation Log Schema

定义操作日志 API 的请求和响应数据结构
Defines operation log API request and response data structures.
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


def _translate_log_field(key: str, prefix: str) -> str | None:
    """
    翻译日志字段

    Args:
        key: 字段值，如 "auth", "create"
        prefix: i18n key 前缀，如 "enum.log_module", "enum.operation"

    Returns:
        翻译后的文本，无翻译时返回原值
    """
    if not key:
        return None
    from app.core.i18n import _
    i18n_key = f"{prefix}.{key}"
    translated = _(i18n_key)
    # 如果翻译结果与 key 相同，说明无翻译，返回原值
    return key if translated == i18n_key else translated


class OperationLogResponse(BaseSchema):
    """操作日志响应"""

    id: int = Field(..., description="日志 ID")
    tenant_id: int | None = Field(None, description="企业 ID")
    user_type: str = Field(..., description="用户类型")
    user_id: int | None = Field(None, description="用户 ID")
    username: str | None = Field(None, description="用户名")
    nickname: str | None = Field(None, description="用户昵称")
    module: str | None = Field(None, description="业务模块")
    module_label: str | None = Field(None, description="业务模块（翻译后）")
    action: str | None = Field(None, description="操作类型")
    action_label: str | None = Field(None, description="操作类型（翻译后）")
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
            nickname=getattr(log, "nickname", None),
            module=log.module,
            module_label=_translate_log_field(log.module, "enum.log_module"),
            action=log.action,
            action_label=_translate_log_field(log.action, "enum.operation"),
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
    tenant_id: int | None = Field(None, description="企业 ID")
    user_type: str = Field(..., description="用户类型")
    user_id: int | None = Field(None, description="用户 ID")
    username: str | None = Field(None, description="用户名")
    nickname: str | None = Field(None, description="用户昵称")
    module: str | None = Field(None, description="业务模块")
    module_label: str | None = Field(None, description="业务模块（翻译后）")
    action: str | None = Field(None, description="操作类型")
    action_label: str | None = Field(None, description="操作类型（翻译后）")
    resource: str | None = Field(None, description="资源标识")
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
            user_id=log.user_id,
            username=log.username,
            nickname=getattr(log, "nickname", None),
            module=log.module,
            module_label=_translate_log_field(log.module, "enum.log_module"),
            action=log.action,
            action_label=_translate_log_field(log.action, "enum.operation"),
            resource=log.resource,
            method=log.method,
            path=log.path,
            status_code=log.status_code,
            response_code=log.response_code,
            ip=log.ip,
            duration_ms=log.duration_ms,
            created_at=log.created_at,
        )


class OperatorSelectItem(BaseSchema):
    """操作人下拉选项"""

    user_id: int = Field(..., description="用户 ID")
    user_type: str = Field(..., description="用户类型")
    username: str = Field(..., description="用户名")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像")


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
    "OperatorSelectItem",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
]
