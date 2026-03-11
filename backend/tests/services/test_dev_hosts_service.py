"""
Dev Hosts 服务单元测试 / Dev Hosts Service Unit Tests

覆盖场景 / Coverage:
1. 正常流程：get_dev_hosts_status() 返回运行时信息和域名状态
2. 未验证域名返回 not_required 且 eligible=False
3. 手动条目识别：domain 在 hosts 中但非系统托管
4. sync_dev_host() 对未验证域名抛 BusinessException
5. non-DEBUG 环境：enabled=False，sync 不写文件
6. remove_dev_host() 调用 async_remove_host_entry（受 _should_inject_hosts 控制）
7. _get_owned_domain 跨租户访问返回 NotFoundException
8. sync_all_dev_hosts() 正确计算 synced/skipped 数量
9. TenantDomainTenantService._should_inject_hosts() 返回 False（租户端隔离）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import BusinessException, NotFoundException
from app.services.system.tenant_domain_service import (
    TenantDomainService,
    TenantDomainTenantService,
)
from tests.services.conftest import make_mock_model


# ──────────────────────────────────────────────
# Fixtures / 测试夹具
# ──────────────────────────────────────────────

@pytest.fixture()
def service(mock_db):
    """构造 TenantDomainService 实例（跳过 __init__，手动注入 DB 和 repo）
    Build TenantDomainService instance (bypassing __init__, inject db and repo manually)"""
    svc = TenantDomainService.__new__(TenantDomainService)
    svc.db = mock_db
    svc.repo = MagicMock()
    return svc


@pytest.fixture()
def tenant_service(mock_db):
    """构造 TenantDomainTenantService 实例（租户端，_should_inject_hosts = False）
    Build TenantDomainTenantService instance (tenant side, _should_inject_hosts = False)"""
    svc = TenantDomainTenantService.__new__(TenantDomainTenantService)
    svc.db = mock_db
    svc.tenant_id = 1
    svc.repo = MagicMock()
    return svc


@pytest.fixture()
def verified_domain():
    """已验证的域名 mock 对象 / Verified domain mock object"""
    return make_mock_model(
        id=10,
        tenant_id=1,
        domain="app.example.local",
        is_verified=True,
        is_primary=True,
    )


@pytest.fixture()
def unverified_domain():
    """未验证的域名 mock 对象 / Unverified domain mock object"""
    return make_mock_model(
        id=20,
        tenant_id=1,
        domain="unverified.example.local",
        is_verified=False,
        is_primary=False,
    )


@pytest.fixture()
def runtime_enabled():
    """模拟 DEBUG=True 的运行时信息 / Runtime info mock for DEBUG=True"""
    return {
        "enabled": True,
        "debug": True,
        "supported": True,
        "os_name": "Linux",
        "hosts_path": "/etc/hosts",
        "requires_elevation": False,
        "can_write_hint": True,
    }


@pytest.fixture()
def runtime_disabled():
    """模拟 DEBUG=False 的运行时信息 / Runtime info mock for DEBUG=False"""
    return {
        "enabled": False,
        "debug": False,
        "supported": True,
        "os_name": "Linux",
        "hosts_path": "/etc/hosts",
        "requires_elevation": False,
        "can_write_hint": True,
    }


@pytest.fixture()
def entry_managed():
    """系统托管条目状态 / Managed entry status"""
    return {
        "domain": "app.example.local",
        "status": "managed_present",
        "matched_ip": "127.0.0.1",
        "managed": True,
    }


@pytest.fixture()
def entry_manual():
    """手动条目状态 / Manual entry status"""
    return {
        "domain": "app.example.local",
        "status": "manual_present",
        "matched_ip": "192.168.1.10",
        "managed": False,
    }


@pytest.fixture()
def entry_missing():
    """未写入 hosts 状态 / Missing entry status"""
    return {
        "domain": "app.example.local",
        "status": "missing",
        "matched_ip": None,
        "managed": False,
    }


# ──────────────────────────────────────────────
# Tests / 测试用例
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_dev_hosts_status_normal(
    service, verified_domain, runtime_enabled, entry_managed
):
    """场景1：正常流程 - get_dev_hosts_status 返回运行时信息和域名状态
    Scenario 1: Normal flow - get_dev_hosts_status returns runtime info and domain status"""
    service.repo.get_tenant_domains = AsyncMock(return_value=[verified_domain])

    with (
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_enabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_managed),
        ),
    ):
        result = await service.get_dev_hosts_status(tenant_id=1)

    assert result["runtime"]["enabled"] is True
    assert result["runtime"]["os_name"] == "Linux"
    assert len(result["domains"]) == 1
    domain_status = result["domains"][0]
    assert domain_status["domain_id"] == 10
    assert domain_status["eligible"] is True
    assert domain_status["status"] == "managed_present"
    assert domain_status["managed"] is True
    assert domain_status["matched_ip"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_get_dev_hosts_status_unverified_returns_not_required(
    service, unverified_domain, runtime_enabled, entry_missing
):
    """场景2：未验证域名返回 not_required，eligible=False
    Scenario 2: Unverified domain returns not_required, eligible=False"""
    service.repo.get_tenant_domains = AsyncMock(return_value=[unverified_domain])

    with (
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_enabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_missing),
        ),
    ):
        result = await service.get_dev_hosts_status(tenant_id=1)

    domain_status = result["domains"][0]
    assert domain_status["eligible"] is False
    assert domain_status["status"] == "not_required"
    assert domain_status["managed"] is False
    assert domain_status["reason"] == "unverified"


@pytest.mark.asyncio
async def test_get_dev_hosts_status_manual_entry_identified(
    service, verified_domain, runtime_enabled, entry_manual
):
    """场景3：手动条目正确识别为 manual_present，managed=False
    Scenario 3: Manual entry correctly identified as manual_present, managed=False"""
    service.repo.get_tenant_domains = AsyncMock(return_value=[verified_domain])

    with (
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_enabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_manual),
        ),
    ):
        result = await service.get_dev_hosts_status(tenant_id=1)

    domain_status = result["domains"][0]
    assert domain_status["status"] == "manual_present"
    assert domain_status["managed"] is False
    assert domain_status["matched_ip"] == "192.168.1.10"
    assert domain_status["eligible"] is True


@pytest.mark.asyncio
async def test_sync_dev_host_unverified_raises_exception(
    service, unverified_domain, runtime_enabled
):
    """场景4：sync_dev_host() 对未验证域名抛 BusinessException
    Scenario 4: sync_dev_host() raises BusinessException for unverified domain"""
    service.get_by_id = AsyncMock(return_value=unverified_domain)

    with pytest.raises(BusinessException):
        await service.sync_dev_host(tenant_id=1, domain_id=20)


@pytest.mark.asyncio
async def test_sync_dev_host_non_debug_no_file_write(
    service, verified_domain, runtime_disabled, entry_missing
):
    """场景5：non-DEBUG 环境，_should_inject_hosts=True 但 add_host_entry 因 is_dev_local()=False 不写文件
    Scenario 5: non-DEBUG env, _should_inject_hosts=True but add_host_entry is a no-op due to is_dev_local()=False"""
    service.get_by_id = AsyncMock(return_value=verified_domain)

    mock_add = AsyncMock(return_value=False)
    with (
        patch(
            "app.services.system.tenant_domain_service.async_add_host_entry",
            new=mock_add,
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_disabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_missing),
        ),
    ):
        result = await service.sync_dev_host(tenant_id=1, domain_id=10)

    mock_add.assert_awaited_once_with("app.example.local")
    assert result["runtime"]["enabled"] is False
    assert result["domain"]["status"] == "missing"


@pytest.mark.asyncio
async def test_remove_dev_host_calls_remove_entry(
    service, verified_domain, runtime_enabled, entry_missing
):
    """场景6：remove_dev_host() 调用 async_remove_host_entry，并返回更新后的状态
    Scenario 6: remove_dev_host() calls async_remove_host_entry and returns updated status"""
    service.get_by_id = AsyncMock(return_value=verified_domain)

    mock_remove = AsyncMock(return_value=True)
    with (
        patch(
            "app.services.system.tenant_domain_service.async_remove_host_entry",
            new=mock_remove,
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_enabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_missing),
        ),
    ):
        result = await service.remove_dev_host(tenant_id=1, domain_id=10)

    mock_remove.assert_awaited_once_with("app.example.local")
    assert result["domain"]["status"] == "missing"
    assert result["domain"]["managed"] is False


@pytest.mark.asyncio
async def test_get_owned_domain_cross_tenant_raises_not_found(
    service, verified_domain
):
    """场景7：跨租户访问域名抛出 NotFoundException
    Scenario 7: Cross-tenant domain access raises NotFoundException"""
    # domain.tenant_id=1 but we request with tenant_id=999
    service.get_by_id = AsyncMock(return_value=verified_domain)

    with pytest.raises(NotFoundException):
        await service._get_owned_domain(tenant_id=999, domain_id=10)


@pytest.mark.asyncio
async def test_sync_all_dev_hosts_counts_synced_and_skipped(
    service, verified_domain, unverified_domain, runtime_enabled, entry_managed
):
    """场景8：sync_all_dev_hosts() 正确计算 synced/skipped，已验证域名同步，未验证域名跳过
    Scenario 8: sync_all_dev_hosts() correctly counts synced/skipped; verified domains synced, unverified skipped"""
    service.repo.get_tenant_domains = AsyncMock(
        return_value=[verified_domain, unverified_domain]
    )

    mock_add = AsyncMock(return_value=True)
    with (
        patch(
            "app.services.system.tenant_domain_service.async_add_host_entry",
            new=mock_add,
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_runtime_info",
            new=AsyncMock(return_value=runtime_enabled),
        ),
        patch(
            "app.services.system.tenant_domain_service.async_get_domain_entry_status",
            new=AsyncMock(return_value=entry_managed),
        ),
    ):
        result = await service.sync_all_dev_hosts(tenant_id=1)

    assert result["synced"] == 1
    assert result["skipped"] == 1
    mock_add.assert_awaited_once_with("app.example.local")


def test_tenant_domain_service_should_inject_hosts_true(service):
    """场景9a：TenantDomainService（管理端）_should_inject_hosts 返回 True
    Scenario 9a: TenantDomainService (admin side) _should_inject_hosts returns True"""
    assert service._should_inject_hosts() is True


def test_tenant_domain_tenant_service_should_inject_hosts_false(tenant_service):
    """场景9b：TenantDomainTenantService（租户端）_should_inject_hosts 返回 False，防止误写 hosts
    Scenario 9b: TenantDomainTenantService (tenant side) _should_inject_hosts returns False, preventing hosts writes"""
    assert tenant_service._should_inject_hosts() is False
