"""
Async DB Session factory for Celery tasks / Celery 任务用异步 DB Session 工厂

Solves engine invalidation caused by event loop changes in Windows --pool=solo mode.
解决 Windows --pool=solo 模式下 event loop 变化导致 engine 失效的问题。
Caches engine and detects event loop changes; rebuilds only when loop changes,
avoiding engine + connection pool creation/destruction on every call.
缓存 engine 并检测 event loop 变化，仅在 loop 变化时重建，
避免每次调用都创建/销毁 engine + 连接池。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Module-level cache: engine + bound event loop / 模块级缓存：engine + 绑定的 event loop
_cached_engine = None
_cached_loop = None
_cached_session_factory = None
_active_session_count = 0


def _get_engine_and_factory():
    """
    获取（或重建）async engine 和 session factory / Get (or rebuild) async engine and session factory.

    Destroys and rebuilds the old engine if the current event loop differs from the cached one.
    如果当前 event loop 与缓存的不同，销毁旧 engine 并重建。
    Reuses engine within the same event loop to reduce connection pool creation overhead.
    同一 event loop 内复用 engine，减少连接池创建开销。
    """
    global _cached_engine, _cached_loop, _cached_session_factory

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _cached_engine is not None and _cached_loop is current_loop:
        return _cached_engine, _cached_session_factory, current_loop

    _cached_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=False,
        poolclass=NullPool,
    )
    _cached_session_factory = async_sessionmaker(
        bind=_cached_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    _cached_loop = current_loop

    return _cached_engine, _cached_session_factory, current_loop


@asynccontextmanager
async def task_async_session():
    """
    Celery 任务用异步 DB Session 上下文管理器 / Async DB Session context manager for Celery tasks.

    Reuses engine within the same event loop; auto-rebuilds when loop changes.
    同一 event loop 内复用 engine，loop 变化时自动重建。
    Replaces repetitive _task_async_session() in each task module.
    用于替代各任务模块中重复的 _task_async_session()。
    """
    global _active_session_count, _cached_engine, _cached_loop, _cached_session_factory

    engine, session_factory, current_loop = _get_engine_and_factory()
    _active_session_count += 1
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
            _active_session_count -= 1
            if (
                _active_session_count == 0
                and _cached_engine is engine
                and _cached_loop is current_loop
            ):
                await engine.dispose()
                _cached_engine = None
                _cached_loop = None
                _cached_session_factory = None


__all__ = ["task_async_session"]
