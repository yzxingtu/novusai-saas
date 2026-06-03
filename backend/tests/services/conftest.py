"""Service 单元测试共享 fixtures / Test.

提供 mock DB session、Redis、Celery 及模型/查询结果工厂辅助函数。
所有 tests/services/ 下的测试文件自动继承这些 fixtures。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Mock DB Session ──


@pytest.fixture()
def mock_db():
    """
    Mock AsyncSession，支持 execute/flush/commit/refresh。

    execute() 返回的 result 默认为 MagicMock，
    测试中可通过 mock_db.execute.return_value 自定义。
    """
    db = MagicMock()
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
    """Mock Redis client with common operations. / 说明"""
    redis = MagicMock()
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
    """Mock Celery app with inspect and send_task. / 说明"""
    celery = MagicMock()
    celery.send_task = MagicMock()
    celery.control.inspect.return_value.ping.return_value = {
        "worker@host": {"ok": "pong"}
    }
    return celery


# ── Mock Model Factory ──


def make_mock_model(**kwargs: Any) -> MagicMock:
    """创建 mock ORM model 对象。 / Create.

    Usage:
        admin = make_mock_model(id=1, username='admin', is_active=True)
        admin.id  # 1
        admin.to_dict()  # {'id': 1, 'username': 'admin', ...}"""
    obj = MagicMock()
    for key, value in kwargs.items():
        setattr(obj, key, value)
    obj.to_dict.return_value = kwargs
    return obj


# ── Mock Query Result ──


def make_scalar_result(value: Any) -> AsyncMock:
    """创建 mock db.execute() 返回值，使 .scalar() 返回指定值。 / Create.

    Usage:
        mock_db.execute.return_value = make_scalar_result(42)"""
    result = MagicMock()
    result.scalar.return_value = value
    result.scalar_one_or_none.return_value = value
    return result


def make_scalars_result(items: list[Any]) -> MagicMock:
    """创建 mock db.execute() 返回值，使 .scalars().all() 返回列表。 / Create.

    Usage:
        mock_db.execute.return_value = make_scalars_result([admin1, admin2])"""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None
    result.scalars.return_value = scalars_mock
    return result


def make_row_result(row_data: dict[str, Any]) -> MagicMock:
    """创建 mock db.execute() 返回值，模拟 .one() 返回命名 Row。 / Create.

    Usage:
        mock_db.execute.return_value = make_row_result(
            {"total_calls": 100, "total_tokens": 5000}
        )"""
    row = MagicMock()
    for key, value in row_data.items():
        setattr(row, key, value)
    result = MagicMock()
    result.one.return_value = row
    result.one_or_none.return_value = row
    return result
