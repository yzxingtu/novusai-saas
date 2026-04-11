"""Payload helpers for operation log writes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_operation_log_payload(
    *,
    tenant_id: int | None,
    user_type: str,
    user_id: int | None,
    username: str | None,
    module: str | None,
    action: str | None,
    resource: str | None,
    method: str,
    path: str,
    query_params: dict | None = None,
    request_body: dict | None = None,
    status_code: int | None = None,
    response_code: int | None = None,
    response_message: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    duration_ms: int | None = None,
    nickname: str | None = None,
    trace_id: str | None = None,
    identity_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the repository payload for an operation-log row."""
    return {
        "tenant_id": tenant_id,
        "user_type": user_type,
        "user_id": user_id,
        "username": username,
        "nickname": nickname,
        "module": module,
        "action": action,
        "resource": resource,
        "method": method,
        "path": path,
        "query_params": query_params,
        "request_body": request_body,
        "status_code": status_code,
        "response_code": response_code,
        "response_message": response_message,
        "ip": ip,
        "user_agent": user_agent,
        "duration_ms": duration_ms,
        "trace_id": trace_id,
        "identity_snapshot": identity_snapshot,
    }


def clone_operation_log_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Clone a caller payload into a mutable mapping for async enrichment."""
    return dict(payload or {})


__all__ = [
    "build_operation_log_payload",
    "clone_operation_log_payload",
]
