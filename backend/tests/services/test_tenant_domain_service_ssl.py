"""TenantDomainService SSL flow unit tests / TenantDomainService SSL 流程单元测试."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.domain import DomainSslStatus
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException
from tests.services.conftest import make_mock_model


@pytest.mark.asyncio
async def test_start_ssl_provision_rejects_when_already_provisioning(mock_db) -> None:
    """重复触发签发时应阻断 / Reject duplicate provisioning when already provisioning."""
    from app.services.system.tenant_domain_service import TenantDomainService

    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.get_by_id = AsyncMock(
        return_value=make_mock_model(
            id=1,
            is_verified=True,
            ssl_status=DomainSslStatus.PROVISIONING.value,
        )
    )
    service.update = AsyncMock()

    with pytest.raises(BusinessException) as exc_info:
        await service.start_ssl_provision(1)

    assert exc_info.value.code == ErrorCode.CONFLICT
    service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_ssl_provision_updates_status_and_enqueues_with_delay(
    mock_db,
    mock_celery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """签发启动应先校验，再设置 provisioning 并延迟入队 / Start provisioning should validate, set status, and enqueue with delay."""
    from app.services.system.tenant_domain_service import TenantDomainService

    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.get_by_id = AsyncMock(
        return_value=make_mock_model(
            id=1,
            tenant_id=5,
            is_verified=True,
            ssl_status=DomainSslStatus.NONE.value,
        )
    )
    service.ensure_custom_domain_entitled = AsyncMock()
    updated = make_mock_model(
        id=1,
        tenant_id=5,
        is_verified=True,
        ssl_status=DomainSslStatus.PROVISIONING.value,
    )
    service.update = AsyncMock(return_value=updated)

    monkeypatch.setattr(
        "app.services.system.dns_provider.ensure_dns_provider_ready",
        AsyncMock(return_value="cloudflare"),
    )
    monkeypatch.setattr("app.celery_app.celery_app", mock_celery, raising=False)

    result = await service.start_ssl_provision(1)

    assert result is updated
    service.ensure_custom_domain_entitled.assert_awaited_once()
    service.update.assert_awaited_once_with(
        1,
        {"ssl_status": DomainSslStatus.PROVISIONING.value},
    )
    mock_celery.send_task.assert_called_once_with(
        "app.tasks.ssl_tasks.task_provision_ssl",
        args=[1],
        queue="default",
        countdown=2,
    )


@pytest.mark.asyncio
async def test_batch_provision_ssl_rejects_custom_domain_when_plan_inactive(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """批量签发也必须复核当前套餐 / Batch provisioning must honor current plan."""
    from app.services.system.tenant_domain_service import TenantDomainService

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    class _DomainResult:
        def scalars(self):
            return _Scalars(
                [
                    SimpleNamespace(
                        id=9,
                        tenant_id=5,
                        domain="custom.example.com",
                    )
                ]
            )

    class _TenantResult:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=True,
                is_deleted=False,
                plan_id=7,
                quota={"allow_custom_domain": True, "max_custom_domains": 5},
                tenant_plan=SimpleNamespace(is_active=False),
            )

    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.update = AsyncMock()
    service._send_ssl_provision_task = MagicMock()
    service._get_domain_suffix = AsyncMock(return_value=".tenant.example")
    mock_db.execute = AsyncMock(side_effect=[_DomainResult(), _TenantResult()])

    monkeypatch.setattr(
        "app.services.system.dns_provider.ensure_dns_provider_ready",
        AsyncMock(return_value="cloudflare"),
    )

    with pytest.raises(BusinessException) as exc_info:
        await service.batch_provision_ssl(5)

    assert exc_info.value.code == ErrorCode.FORBIDDEN
    service.update.assert_not_awaited()
    service._send_ssl_provision_task.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_auto_start_ssl_after_verify_skips_when_readiness_not_ready(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS 不可用时验证后不应自动签发 / Skip auto provisioning when DNS readiness is not ready."""
    from app.services.system.tenant_domain_service import TenantDomainService

    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.start_ssl_provision = AsyncMock()
    service._should_auto_provision_after_verify = MagicMock(return_value=True)

    monkeypatch.setattr(
        "app.services.system.dns_provider.audit_dns_provider_config",
        AsyncMock(return_value={"ready": False}),
    )

    result = await service.maybe_auto_start_ssl_after_verify(9)

    assert result is None
    service.start_ssl_provision.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_auto_start_ssl_after_verify_starts_when_ready(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS 就绪时验证后应自动触发签发 / Auto provisioning should start after verify when DNS readiness is ready."""
    from app.services.system.tenant_domain_service import TenantDomainService

    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db
    service.repo = AsyncMock()
    service._should_auto_provision_after_verify = MagicMock(return_value=True)
    provisioned = make_mock_model(id=12, ssl_status=DomainSslStatus.PROVISIONING.value)
    service.start_ssl_provision = AsyncMock(return_value=provisioned)

    monkeypatch.setattr(
        "app.services.system.dns_provider.audit_dns_provider_config",
        AsyncMock(return_value={"ready": True}),
    )

    result = await service.maybe_auto_start_ssl_after_verify(12)

    assert result is provisioned
    service.start_ssl_provision.assert_awaited_once_with(12)
