"""Serialization helpers for operation logs."""

from __future__ import annotations

from typing import Any

from app.models.system.operation_log import OperationLog
from app.schemas.system.operation_log import (
    OperationLogListResponse,
    OperationLogResponse,
)

from .identity import _OperationLogIdentityFacade


class _OperationLogSerializerFacade:
    """Snapshot-aware serializers for operation log detail and list payloads."""

    def __init__(self, identity: _OperationLogIdentityFacade):
        self.identity = identity

    async def serialize_log(self, log: OperationLog) -> dict[str, Any]:
        ref = self.identity.identity_ref(log.user_type, log.user_id)
        identity_meta_map = await self.identity.load_identity_meta_map(
            {ref} if ref else set()
        )
        return OperationLogResponse.from_model(
            log,
            identity_meta=identity_meta_map.get(ref, {}),
        ).model_dump(mode="python")

    async def serialize_logs(self, logs: list[OperationLog]) -> list[dict[str, Any]]:
        refs = {
            ref
            for log in logs
            if (ref := self.identity.identity_ref(log.user_type, log.user_id))
            is not None
        }
        identity_meta_map = await self.identity.load_identity_meta_map(refs)
        return [
            OperationLogListResponse.from_model(
                log,
                identity_meta=identity_meta_map.get(
                    self.identity.identity_ref(log.user_type, log.user_id),
                    {},
                ),
            ).model_dump(mode="python")
            for log in logs
        ]


__all__ = ["_OperationLogSerializerFacade"]
