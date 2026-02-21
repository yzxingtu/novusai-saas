"""
Celery 任务用异步 DB Session 工厂

解决 Windows --pool=solo 模式下 event loop 变化导致 engine 失效的问题。
缓存 engine 并检测 event loop 变化，仅在 loop 变化时重建，
避免每次调用都创建/销毁 engine + 连接池。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 模块级缓存：engine + 绑定的 event loop
_cached_engine = None
_cached_loop = None
_cached_session_factory = None


def _get_engine_and_factory():
    """
    获取（或重建）async engine 和 session factory。

    如果当前 event loop 与缓存的不同，销毁旧 engine 并重建。
    同一 event loop 内复用 engine，减少连接池创建开销。
    """
    global _cached_engine, _cached_loop, _cached_session_factory

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _cached_engine is not None and _cached_loop is current_loop:
        return _cached_engine, _cached_session_factory

    # Event loop 已变化或首次调用，重建 engine
    if _cached_engine is not None:
        # 同步关闭旧 engine（best-effort，旧 loop 可能已关闭）
        try:
            _cached_engine.sync_engine.dispose()
        except Exception:
            pass

    _cached_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    _cached_session_factory = async_sessionmaker(
        bind=_cached_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    _cached_loop = current_loop

    return _cached_engine, _cached_session_factory


@asynccontextmanager
async def task_async_session():
    """
    Celery 任务用异步 DB Session 上下文管理器。

    同一 event loop 内复用 engine，loop 变化时自动重建。
    用于替代各任务模块中重复的 _task_async_session()。
    """
    _, session_factory = _get_engine_and_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


__all__ = ["task_async_session"]
