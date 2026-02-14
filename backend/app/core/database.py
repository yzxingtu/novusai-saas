"""
数据库连接模块

提供异步数据库连接、会话管理和依赖注入
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.base_model import Base


# ============================================
# 异步数据库引擎
# ============================================

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # SQL 日志由 logging 模块统一管理，输出到 db.log
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # 连接前检查
)

# 异步会话工厂
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ============================================
# 只读数据库引擎（用于 AI Text-to-SQL）
# ============================================

_readonly_engine = None
_readonly_session_factory = None


def _get_readonly_engine():
    """延迟初始化只读引擎（仅在配置了 AI_READONLY_DB_URL 时才创建）"""
    global _readonly_engine
    if _readonly_engine is not None:
        return _readonly_engine

    readonly_url = settings.AI_READONLY_DB_URL_ASYNC
    if not readonly_url:
        return None

    _readonly_engine = create_async_engine(
        readonly_url,
        echo=False,
        pool_size=3,
        max_overflow=2,
        pool_timeout=10,
        pool_pre_ping=True,
    )
    return _readonly_engine


def get_readonly_session_factory():
    """获取只读会话工厂"""
    global _readonly_session_factory
    if _readonly_session_factory is not None:
        return _readonly_session_factory

    engine = _get_readonly_engine()
    if engine is None:
        return None

    _readonly_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return _readonly_session_factory


# ============================================
# 同步数据库引擎（用于 Alembic 迁移）
# ============================================

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=False,  # SQL 日志由 logging 模块统一管理，输出到 db.log
    pool_pre_ping=True,
)

sync_session_factory = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)


# ============================================
# 依赖注入
# ============================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（FastAPI 依赖注入）
    
    使用示例:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（上下文管理器）
    
    使用示例:
        async with get_db_context() as db:
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================
# 数据库管理函数
# ============================================

async def check_database_connection() -> bool:
    """
    检查数据库连接是否正常
    
    Returns:
        连接是否成功
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def create_database_if_not_exists() -> bool:
    """
    检查数据库是否存在，如果不存在则创建（同步函数）

    Returns:
        是否成功
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import ProgrammingError

    # 连接到 postgres 默认数据库来创建目标数据库
    admin_url = (
        f"postgresql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/postgres"
    )

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            # 检查数据库是否存在
            result = conn.execute(
                text(
                    "SELECT 1 FROM pg_database WHERE datname = :dbname"
                ),
                {"dbname": settings.DATABASE_NAME}
            )
            exists = result.scalar() is not None

            if not exists:
                print(f"Database '{settings.DATABASE_NAME}' does not exist, creating...")
                conn.execute(
                    text(f'CREATE DATABASE "{settings.DATABASE_NAME}"')
                )
                print(f"Database '{settings.DATABASE_NAME}' created successfully")
            else:
                print(f"Database '{settings.DATABASE_NAME}' already exists")

        return True
    except Exception as e:
        print(f"Database creation failed: {e}")
        return False
    finally:
        admin_engine.dispose()


def run_migrations() -> bool:
    """
    运行数据库迁移（同步方式，用于启动时）

    Returns:
        是否成功
    """
    from pathlib import Path

    try:
        from alembic.config import Config
        from alembic import command

        backend_dir = Path(__file__).parent.parent.parent
        alembic_ini = backend_dir / "alembic.ini"

        if not alembic_ini.exists():
            print("alembic.ini not found, skipping migrations")
            return True

        migrations_dir = backend_dir / "migrations" / "versions"
        if not migrations_dir.exists() or not any(migrations_dir.glob("*.py")):
            print("No migration files found, skipping migrations")
            return True

        print("Running database migrations...")

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option(
            "script_location", str(backend_dir / "migrations")
        )
        alembic_cfg.set_main_option(
            "sqlalchemy.url", settings.DATABASE_URL_SYNC
        )

        command.upgrade(alembic_cfg, "head")

        print("Database migrations completed")
        return True
    except ImportError:
        print("Alembic not installed, skipping migrations")
        return True
    except Exception as e:
        print(f"Database migration failed: {e}")
        return False


async def init_database() -> bool:
    """
    初始化数据库（启动时调用）
    
    1. 检查/创建数据库
    2. 运行迁移
    3. 验证连接
    
    Returns:
        是否成功
    """
    print("Initializing database...")

    # 1. 检查/创建数据库
    if not await asyncio.to_thread(create_database_if_not_exists):
        return False

    # 2. 运行迁移
    if not await asyncio.to_thread(run_migrations):
        return False

    # 3. 验证连接
    if not await check_database_connection():
        return False

    print("Database initialization complete")
    return True


async def close_database() -> None:
    """
    关闭数据库连接（关闭时调用）
    """
    await async_engine.dispose()
    sync_engine.dispose()
    if _readonly_engine is not None:
        await _readonly_engine.dispose()
    print("Database connections closed")


# 导出
__all__ = [
    "async_engine",
    "async_session_factory",
    "get_readonly_session_factory",
    "sync_engine",
    "sync_session_factory",
    "get_db",
    "get_db_context",
    "check_database_connection",
    "create_database_if_not_exists",
    "run_migrations",
    "init_database",
    "close_database",
    "Base",
]
