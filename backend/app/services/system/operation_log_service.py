"""
操作日志服务 / Operation Log Service

提供操作日志的业务逻辑
Provides operation log business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import GlobalService
from app.models.system.operation_log import OperationLog
from app.repositories.system.operation_log_repository import OperationLogRepository
from app.schemas.common.query import QuerySpec
from app.services.system.operation_log_service_parts import (
    _OperationLogIdentityFacade,
    _OperationLogOperatorFacade,
    _OperationLogPermissionFacade,
    _OperationLogSerializerFacade,
    build_operation_log_payload,
    create_log_async,
)
from app.services.system.operation_log_service_parts.async_writer import (
    _fetch_user_info as _async_writer_fetch_user_info,
)
from app.services.system.operation_log_service_parts.async_writer import (
    _write_log_async as _async_writer_write_log_async,
)

if TYPE_CHECKING:
    from app.models.system.admin import Admin
    from app.models.tenant.tenant_admin import TenantAdmin

_fetch_user_info = _async_writer_fetch_user_info
_write_log_async = _async_writer_write_log_async


class OperationLogService(GlobalService[OperationLog, OperationLogRepository]):
    """
    操作日志服务 / Operation log service.

    提供操作日志的业务方法，包括：
    - 异步写入日志
    - 平台端日志查询
    - 企业端日志查询（自动隔离）
    - 批量删除日志
    """

    model = OperationLog
    repository_class = OperationLogRepository

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._identity_facade = _OperationLogIdentityFacade(db)
        self._operator_facade = _OperationLogOperatorFacade(
            db,
            self._identity_facade,
        )
        self._permission_facade = _OperationLogPermissionFacade(db, self.repo)
        self._serializer_facade = _OperationLogSerializerFacade(
            self._identity_facade
        )

    def _get_identity_facade(self) -> _OperationLogIdentityFacade:
        facade = getattr(self, "_identity_facade", None)
        if facade is None:
            facade = _OperationLogIdentityFacade(self.db)
            self._identity_facade = facade
        return facade

    def _get_operator_facade(self) -> _OperationLogOperatorFacade:
        facade = getattr(self, "_operator_facade", None)
        if facade is None:
            facade = _OperationLogOperatorFacade(
                self.db,
                self._get_identity_facade(),
            )
            self._operator_facade = facade
        return facade

    def _get_permission_facade(self) -> _OperationLogPermissionFacade:
        facade = getattr(self, "_permission_facade", None)
        if facade is None:
            facade = _OperationLogPermissionFacade(self.db, self.repo)
            self._permission_facade = facade
        return facade

    def _get_serializer_facade(self) -> _OperationLogSerializerFacade:
        facade = getattr(self, "_serializer_facade", None)
        if facade is None:
            facade = _OperationLogSerializerFacade(self._get_identity_facade())
            self._serializer_facade = facade
        return facade

    async def create_log(
        self,
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
    ) -> OperationLog:
        data = build_operation_log_payload(
            tenant_id=tenant_id,
            user_type=user_type,
            user_id=user_id,
            username=username,
            module=module,
            action=action,
            resource=resource,
            method=method,
            path=path,
            query_params=query_params,
            request_body=request_body,
            status_code=status_code,
            response_code=response_code,
            response_message=response_message,
            ip=ip,
            user_agent=user_agent,
            duration_ms=duration_ms,
            nickname=nickname,
            trace_id=trace_id,
            identity_snapshot=identity_snapshot,
        )
        return await self.repo.create_log(data)

    async def query_admin_logs(
        self,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        return await self.query_list(spec, scope="admin")

    async def query_tenant_logs(
        self,
        tenant_id: int,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        return await self.repo.query_tenant_logs(tenant_id, spec)

    async def delete_logs(
        self,
        ids: list[int],
        soft: bool = True,
    ) -> int:
        return await self.repo.delete_logs_by_ids(ids, soft=soft)

    async def get_stats_by_module(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.get_stats_by_module(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_stats_by_action(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.get_stats_by_action(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def query_admin_logs_by_permission(
        self,
        admin: Admin,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        return await self._get_permission_facade().query_admin_logs_by_permission(
            admin,
            spec,
        )

    async def query_tenant_logs_by_permission(
        self,
        tenant_admin: TenantAdmin,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        return await self._get_permission_facade().query_tenant_logs_by_permission(
            tenant_admin,
            spec,
        )

    async def serialize_log(self, log: OperationLog) -> dict[str, Any]:
        return await self._get_serializer_facade().serialize_log(log)

    async def serialize_logs(self, logs: list[OperationLog]) -> list[dict[str, Any]]:
        return await self._get_serializer_facade().serialize_logs(logs)

    async def get_admin_operators(self) -> list[dict[str, Any]]:
        return await self._get_operator_facade().get_admin_operators()

    async def get_admin_operators_select(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        return await self._get_operator_facade().get_admin_operators_select(
            search=search,
            page=page,
            page_size=page_size,
        )

    async def get_tenant_operators(self, tenant_id: int) -> list[dict[str, Any]]:
        return await self._get_operator_facade().get_tenant_operators(tenant_id)

    async def get_tenant_operators_select(
        self,
        tenant_id: int,
        search: str | None = None,
        user_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        return await self._get_operator_facade().get_tenant_operators_select(
            tenant_id=tenant_id,
            search=search,
            user_type=user_type,
            page=page,
            page_size=page_size,
        )

    async def _get_subordinate_admin_ids(self, admin: Admin) -> list[int]:
        return await self._get_permission_facade().get_subordinate_admin_ids(admin)

    async def _get_subordinate_tenant_admin_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[int]:
        return await self._get_permission_facade().get_subordinate_tenant_admin_ids(
            tenant_admin
        )


__all__ = [
    "OperationLogService",
    "create_log_async",
]
