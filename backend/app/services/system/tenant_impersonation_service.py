"""Tenant impersonation workflow service. / 企业后台一键登录工作流服务。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.i18n import _
from app.core.logging import ImpersonateLoggerMixin
from app.core.security import (
    IMPERSONATE_TOKEN_EXPIRE_SECONDS,
    TOKEN_SCOPE_TENANT_ADMIN,
    create_impersonate_token,
)
from app.schemas.system import TenantImpersonateResponse
from app.services.system.tenant_service import TenantService


class TenantImpersonationService(ImpersonateLoggerMixin):
    """Owns tenant impersonation issuance outside the controller file."""

    def __init__(self, db) -> None:
        self._db = db

    async def issue_tenant_admin_token(
        self,
        *,
        current_admin: Any,
        role_id: int | None,
        tenant_id: int,
    ) -> TenantImpersonateResponse:
        service = TenantService(self._db)
        tenant = await service.get_by_id(tenant_id)

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_("tenant.not_found"),
            )

        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_("tenant.disabled"),
            )

        if role_id:
            await service.validate_impersonation_role(tenant_id, role_id)

        token = create_impersonate_token(
            admin_id=current_admin.id,
            target_scope=TOKEN_SCOPE_TENANT_ADMIN,
            target_tenant_id=tenant_id,
            target_role_id=role_id,
        )

        self.logger.info(
            "Admin impersonate initiated | admin_id={} | admin_username={} | "
            "target_tenant_id=%s | target_tenant_code=%s | target_role_id=%s",
            current_admin.id,
            current_admin.username,
            tenant_id,
            tenant.code,
            role_id,
        )

        return TenantImpersonateResponse(
            impersonate_token=token,
            tenant_code=tenant.code,
            tenant_name=tenant.name,
            expires_in=IMPERSONATE_TOKEN_EXPIRE_SECONDS,
        )


__all__ = ["TenantImpersonationService"]
