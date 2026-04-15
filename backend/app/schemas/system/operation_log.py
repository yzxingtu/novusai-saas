"""
操作日志相关 Schema / Operation Log Schema

定义操作日志 API 的请求和响应数据结构
Defines operation log API request and response data structures.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.core.identity_snapshot import snapshot_has_key, snapshot_value
from app.operation_log_module_resolution import resolve_operation_log_module


def _translate_log_field(key: str, prefix: str) -> str | None:
    """
    翻译日志字段 / Translate log field by i18n.

    Args:
        key: 字段值，如 "auth", "create" / Field value, e.g. "auth", "create"
        prefix: i18n key 前缀，如 "enum.log_module" / i18n key prefix, e.g. "enum.log_module"

    Returns:
        翻译后的文本，无翻译时返回原值 / Translated text, or original if no translation.
    """
    if not key:
        return None
    from app.core.i18n import _

    i18n_key = f"{prefix}.{key}"
    translated = _(i18n_key)
    # 如果翻译结果与 key 相同，说明无翻译，返回原值
    return key if translated == i18n_key else translated


def _resolve_identity_fields(
    log,
    identity_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并日志快照与实时身份字段 / Merge log snapshot and live identity fields."""
    identity_meta = identity_meta or {}
    snapshot = (
        getattr(log, "identity_snapshot", None)
        if isinstance(getattr(log, "identity_snapshot", None), dict)
        else {}
    )
    username = (
        snapshot_value(snapshot, "username")
        or getattr(log, "username", None)
        or identity_meta.get("username")
    )
    nickname = (
        snapshot_value(snapshot, "nickname")
        or getattr(log, "nickname", None)
        or identity_meta.get("nickname")
    )
    display_name = (
        snapshot_value(snapshot, "display_name")
        or identity_meta.get("display_name")
        or nickname
        or username
    )
    if snapshot_has_key(snapshot, "display_role_name"):
        role_name = snapshot.get("display_role_name")
    elif snapshot_has_key(snapshot, "role_name"):
        role_name = snapshot.get("role_name")
    else:
        role_name = (
            identity_meta.get("display_role_name")
            or identity_meta.get("role_name")
        )
    return {
        "username": username,
        "nickname": nickname,
        "display_name": display_name,
        "avatar": snapshot_value(snapshot, "avatar", identity_meta.get("avatar")),
        "org_node_id": snapshot_value(
            snapshot,
            "org_node_id",
            identity_meta.get("org_node_id"),
        ),
        "org_node_name": snapshot_value(
            snapshot,
            "org_node_name",
            identity_meta.get("org_node_name"),
        ),
        "role_name": role_name,
        "is_active": snapshot_value(
            snapshot,
            "is_active",
            identity_meta.get("is_active"),
        ),
        "is_owner": snapshot_value(
            snapshot,
            "is_owner",
            identity_meta.get("is_owner"),
        ),
        "is_leader": snapshot_value(
            snapshot,
            "is_leader",
            identity_meta.get("is_leader"),
        ),
    }


class OperationLogResponse(BaseSchema):
    """操作日志响应 / Operation log response."""

    id: int = Field(..., description="日志 ID")
    trace_id: str | None = Field(None, description="追踪 ID")
    tenant_id: int | None = Field(None, description="企业 ID")
    user_type: str = Field(..., description="用户类型")
    user_id: int | None = Field(None, description="用户 ID")
    display_name: str | None = Field(None, description="统一展示名")
    username: str | None = Field(None, description="用户名")
    nickname: str | None = Field(None, description="用户昵称")
    avatar: str | None = Field(None, description="头像")
    org_node_id: int | None = Field(None, description="组织节点 ID")
    org_node_name: str | None = Field(None, description="组织节点名称")
    role_name: str | None = Field(None, description="角色名称")
    is_active: bool | None = Field(None, description="是否启用")
    is_owner: bool | None = Field(None, description="是否 owner/super")
    is_leader: bool | None = Field(None, description="是否组织负责人")
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
    def from_model(
        cls,
        log,
        identity_meta: dict[str, Any] | None = None,
    ) -> "OperationLogResponse":
        """从模型创建响应 / Build response from model."""
        identity_fields = _resolve_identity_fields(log, identity_meta)
        effective_module = resolve_operation_log_module(
            module=log.module,
            resource=log.resource,
            path=log.path,
        )
        return cls(
            id=log.id,
            trace_id=log.trace_id,
            tenant_id=log.tenant_id,
            user_type=log.user_type,
            user_id=log.user_id,
            display_name=identity_fields["display_name"],
            username=identity_fields["username"],
            nickname=identity_fields["nickname"],
            avatar=identity_fields["avatar"],
            org_node_id=identity_fields["org_node_id"],
            org_node_name=identity_fields["org_node_name"],
            role_name=identity_fields["role_name"],
            is_active=identity_fields["is_active"],
            is_owner=identity_fields["is_owner"],
            is_leader=identity_fields["is_leader"],
            module=effective_module,
            module_label=_translate_log_field(effective_module, "enum.log_module"),
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
    """操作日志列表项响应（简化版） / Operation log list item response (simplified)."""

    id: int = Field(..., description="日志 ID")
    trace_id: str | None = Field(None, description="追踪 ID")
    tenant_id: int | None = Field(None, description="企业 ID")
    user_type: str = Field(..., description="用户类型")
    user_id: int | None = Field(None, description="用户 ID")
    display_name: str | None = Field(None, description="统一展示名")
    username: str | None = Field(None, description="用户名")
    nickname: str | None = Field(None, description="用户昵称")
    avatar: str | None = Field(None, description="头像")
    org_node_id: int | None = Field(None, description="组织节点 ID")
    org_node_name: str | None = Field(None, description="组织节点名称")
    role_name: str | None = Field(None, description="角色名称")
    is_active: bool | None = Field(None, description="是否启用")
    is_owner: bool | None = Field(None, description="是否 owner/super")
    is_leader: bool | None = Field(None, description="是否组织负责人")
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
    def from_model(
        cls,
        log,
        identity_meta: dict[str, Any] | None = None,
    ) -> "OperationLogListResponse":
        """从模型创建列表响应 / Build list response from model."""
        identity_fields = _resolve_identity_fields(log, identity_meta)
        effective_module = resolve_operation_log_module(
            module=log.module,
            resource=log.resource,
            path=log.path,
        )
        return cls(
            id=log.id,
            trace_id=log.trace_id,
            tenant_id=log.tenant_id,
            user_type=log.user_type,
            user_id=log.user_id,
            display_name=identity_fields["display_name"],
            username=identity_fields["username"],
            nickname=identity_fields["nickname"],
            avatar=identity_fields["avatar"],
            org_node_id=identity_fields["org_node_id"],
            org_node_name=identity_fields["org_node_name"],
            role_name=identity_fields["role_name"],
            is_active=identity_fields["is_active"],
            is_owner=identity_fields["is_owner"],
            is_leader=identity_fields["is_leader"],
            module=effective_module,
            module_label=_translate_log_field(effective_module, "enum.log_module"),
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
    """操作人下拉选项 / Operator select option."""

    user_id: int = Field(..., description="用户 ID")
    user_type: str = Field(..., description="用户类型")
    display_name: str | None = Field(None, description="统一展示名")
    username: str = Field(..., description="用户名")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像")
    org_node_id: int | None = Field(None, description="组织节点 ID")
    org_node_name: str | None = Field(None, description="组织节点名称")
    role_name: str | None = Field(None, description="角色名称")
    is_active: bool | None = Field(None, description="是否启用")
    is_owner: bool | None = Field(None, description="是否 owner/super")
    is_leader: bool | None = Field(None, description="是否组织负责人")


class OperationLogDeleteRequest(BaseSchema):
    """批量删除日志请求 / Batch delete logs request."""

    ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="日志 ID 列表"
    )


class LogStatsItem(BaseSchema):
    """日志统计项 / Log stats item."""

    name: str = Field(..., description="分类名称")
    count: int = Field(..., description="数量")


class LogStatsResponse(BaseSchema):
    """日志统计响应 / Log stats response."""

    by_module: list[LogStatsItem] = Field(
        default_factory=list, description="按模块统计"
    )
    by_action: list[LogStatsItem] = Field(
        default_factory=list, description="按操作类型统计"
    )
    total: int = Field(..., description="总数")


__all__ = [
    "OperationLogResponse",
    "OperationLogListResponse",
    "OperatorSelectItem",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
]
