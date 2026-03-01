"""
Service 单元测试共享 fixtures

提供 mock DB session、Redis、Celery 及常用测试数据工厂。
所有 tests/services/ 下的测试文件自动继承这些 fixtures。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Mock DB Session ──

@pytest.fixture()
def mock_db():
    """
    Mock AsyncSession，支持 execute/flush/commit/refresh。

    execute() 返回的 result 默认为 MagicMock，
    测试中可通过 mock_db.execute.return_value 自定义。
    """
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


# ── Mock Redis ──

@pytest.fixture()
def mock_redis():
    """Mock Redis client with common operations."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


# ── Mock Celery ──

@pytest.fixture()
def mock_celery():
    """Mock Celery app with inspect and send_task."""
    celery = MagicMock()
    celery.send_task = MagicMock()
    celery.control.inspect.return_value.ping.return_value = {"worker@host": {"ok": "pong"}}
    return celery


# ── Sample Data Factories ──

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def sample_admin_data() -> dict[str, Any]:
    """平台管理员样本数据"""
    return {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "display_name": "Admin User",
        "is_active": True,
        "is_super": True,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


@pytest.fixture()
def sample_tenant_data() -> dict[str, Any]:
    """租户样本数据"""
    return {
        "id": 1,
        "name": "Test Tenant",
        "slug": "test-tenant",
        "status": "active",
        "plan_id": 1,
        "is_active": True,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


@pytest.fixture()
def sample_tenant_admin_data() -> dict[str, Any]:
    """租户管理员样本数据"""
    return {
        "id": 1,
        "tenant_id": 1,
        "username": "tenant_admin",
        "email": "admin@tenant.com",
        "display_name": "Tenant Admin",
        "is_active": True,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


@pytest.fixture()
def sample_agent_data() -> dict[str, Any]:
    """AI 智能体样本数据"""
    return {
        "id": 1,
        "tenant_id": 1,
        "name": "Test Agent",
        "description": "A test agent",
        "model_id": 1,
        "system_prompt": "You are a helpful assistant.",
        "is_active": True,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


@pytest.fixture()
def sample_call_log_data() -> dict[str, Any]:
    """AI 调用日志样本数据"""
    return {
        "id": 1,
        "tenant_id": 1,
        "agent_id": 1,
        "provider_id": 1,
        "model_name": "gpt-4",
        "request_type": "chat",
        "status": "success",
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
        "cost": 0.01,
        "latency_ms": 500,
        "created_at": _utc_now(),
    }


# ── Mock Model Factory ──

def make_mock_model(**kwargs: Any) -> MagicMock:
    """
    创建 mock ORM model 对象。

    Usage:
        admin = make_mock_model(id=1, username='admin', is_active=True)
        admin.id  # 1
        admin.to_dict()  # {'id': 1, 'username': 'admin', ...}
    """
    obj = MagicMock()
    for key, value in kwargs.items():
        setattr(obj, key, value)
    obj.to_dict.return_value = kwargs
    return obj


# ── Mock Query Result ──

def make_scalar_result(value: Any) -> AsyncMock:
    """
    创建 mock db.execute() 返回值，使 .scalar() 返回指定值。

    Usage:
        mock_db.execute.return_value = make_scalar_result(42)
    """
    result = MagicMock()
    result.scalar.return_value = value
    result.scalar_one_or_none.return_value = value
    return result


def make_scalars_result(items: list[Any]) -> MagicMock:
    """
    创建 mock db.execute() 返回值，使 .scalars().all() 返回列表。

    Usage:
        mock_db.execute.return_value = make_scalars_result([admin1, admin2])
    """
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None
    result.scalars.return_value = scalars_mock
    return result


def make_row_result(row_data: dict[str, Any]) -> MagicMock:
    """
    创建 mock db.execute() 返回值，模拟 .one() 返回命名 Row。

    Usage:
        mock_db.execute.return_value = make_row_result(
            {"total_calls": 100, "total_tokens": 5000}
        )
    """
    row = MagicMock()
    for key, value in row_data.items():
        setattr(row, key, value)
    result = MagicMock()
    result.one.return_value = row
    result.one_or_none.return_value = row
    return result
