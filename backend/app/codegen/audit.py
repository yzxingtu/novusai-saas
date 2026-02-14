"""
批量生成审计日志

M58-T28: 记录 preview/generate/confirm/write/revert 全流程

审计事件结构：
- run_id: 生成运行唯一 ID
- event_type: preview/generate/confirm/write/revert/error
- actor: 操作者标识
- scope: tenant_id 或 admin
- timestamp: ISO8601
- duration_ms: 操作耗时
- summary: 操作摘要（截断，不含文件内容）

存储策略（dev-only v1）：
- 内存环形缓冲区（最近 N 条）
- 可选文件持久化
- 不写入主数据库（避免审计表污染）
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 枚举
# ============================================================


class AuditEventType(str, Enum):
    """审计事件类型"""

    PREVIEW = "preview"
    GENERATE = "generate"
    CONFIRM = "confirm"
    WRITE = "write"
    REVERT = "revert"
    VALIDATE = "validate"
    MERGE_PATCH = "merge_patch"
    ERROR = "error"


class AuditStatus(str, Enum):
    """审计事件状态"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


# ============================================================
# 审计事件
# ============================================================


class AuditSummary(BaseModel):
    """操作摘要（截断，不含文件内容）"""

    entity_count: int = Field(0)
    file_count: int = Field(0)
    entities: list[str] = Field(default_factory=list)
    conflicts: int = Field(0)
    written: int = Field(0)
    skipped: int = Field(0)
    merged: int = Field(0)
    errors: int = Field(0)
    warnings: int = Field(0)
    project_hash: str = Field("", description="项目配置指纹")
    extra: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    """审计事件"""

    run_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="生成运行 ID",
    )
    event_type: AuditEventType = Field(...)
    status: AuditStatus = Field(AuditStatus.SUCCESS)
    actor: str = Field("", description="操作者标识")
    scope: str = Field("", description="租户/admin 标识")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    duration_ms: int = Field(0, description="操作耗时(ms)")
    summary: AuditSummary = Field(default_factory=AuditSummary)
    error_message: str = Field("", description="错误信息（截断）")


# ============================================================
# 辅助函数
# ============================================================


def compute_project_hash(project_dict: dict[str, Any]) -> str:
    """计算项目配置指纹（用于审计关联）

    Args:
        project_dict: BatchCrudProject JSON

    Returns:
        短 hash（前 12 位）
    """
    content = json.dumps(project_dict, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def create_audit_event(
    event_type: AuditEventType,
    *,
    run_id: str = "",
    actor: str = "",
    scope: str = "",
    status: AuditStatus = AuditStatus.SUCCESS,
    duration_ms: int = 0,
    entity_count: int = 0,
    file_count: int = 0,
    entities: list[str] | None = None,
    conflicts: int = 0,
    written: int = 0,
    skipped: int = 0,
    merged: int = 0,
    errors: int = 0,
    warnings: int = 0,
    project_hash: str = "",
    error_message: str = "",
    extra: dict[str, Any] | None = None,
) -> AuditEvent:
    """创建审计事件的便捷工厂函数"""
    return AuditEvent(
        run_id=run_id or uuid.uuid4().hex[:12],
        event_type=event_type,
        status=status,
        actor=actor,
        scope=scope,
        duration_ms=duration_ms,
        summary=AuditSummary(
            entity_count=entity_count,
            file_count=file_count,
            entities=entities or [],
            conflicts=conflicts,
            written=written,
            skipped=skipped,
            merged=merged,
            errors=errors,
            warnings=warnings,
            project_hash=project_hash,
            extra=extra or {},
        ),
        error_message=error_message[:300] if error_message else "",
    )


# ============================================================
# 审计存储（内存环形缓冲区）
# ============================================================


_MAX_EVENTS = 500
"""最大保留事件数"""


class AuditStore:
    """审计事件存储

    Dev-only v1: 内存环形缓冲区。
    不写入主数据库，避免审计表污染。
    """

    def __init__(self, max_events: int = _MAX_EVENTS) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=max_events)

    def record(self, event: AuditEvent) -> None:
        """记录审计事件"""
        self._events.append(event)

    def query(
        self,
        *,
        event_type: AuditEventType | None = None,
        actor: str = "",
        run_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """查询审计事件

        Args:
            event_type: 按事件类型过滤
            actor: 按操作者过滤
            run_id: 按 run_id 过滤
            limit: 最大返回数
            offset: 偏移量

        Returns:
            匹配的审计事件列表（新→旧）
        """
        results = list(reversed(self._events))

        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor:
            results = [e for e in results if e.actor == actor]
        if run_id:
            results = [e for e in results if e.run_id == run_id]

        return results[offset:offset + limit]

    def count(self) -> int:
        """事件总数"""
        return len(self._events)

    def clear(self) -> None:
        """清空所有事件"""
        self._events.clear()

    def get_run_events(self, run_id: str) -> list[AuditEvent]:
        """获取同一 run 的所有事件（按时间顺序）"""
        return [e for e in self._events if e.run_id == run_id]


# 全局审计存储实例
_global_store = AuditStore()


def get_audit_store() -> AuditStore:
    """获取全局审计存储"""
    return _global_store


def record_event(event: AuditEvent) -> None:
    """记录审计事件到全局存储"""
    _global_store.record(event)


__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditStatus",
    "AuditStore",
    "AuditSummary",
    "compute_project_hash",
    "create_audit_event",
    "get_audit_store",
    "record_event",
]
