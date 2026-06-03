"""
AI 调用日志服务 / AI Call Log Service

使用 Celery 异步记录 AI 调用日志，不阻塞主请求
Uses Celery to asynchronously record AI call logs without blocking main requests.
"""

from __future__ import annotations

from app.core.base_service import BaseService
from app.core.identity_snapshot import load_identity_snapshot
from app.models.ai import AICallLog
from app.repositories.ai import AICallLogRepository
from app.services.ai.call_log_projection_service import CallLogProjectionMixin
from app.services.ai.call_log_read_service import CallLogReadServiceMixin
from app.services.ai.call_log_write_service import CallLogWriteServiceMixin


class CallLogService(
    CallLogWriteServiceMixin,
    CallLogReadServiceMixin,
    CallLogProjectionMixin,
    BaseService[AICallLog, AICallLogRepository],
):
    model = AICallLog
    repository_class = AICallLogRepository

    @staticmethod
    def _load_identity_snapshot():
        return load_identity_snapshot


__all__ = ["CallLogService"]
