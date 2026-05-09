"""
数据库连接模块 / Database Connection Module

提供异步数据库连接、会话管理和依赖注入
Provides async database connections, session management and dependency injection.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging import LogManager
from app.plugins.migration_paths import (
    build_migration_version_locations,
    purge_migration_bytecode,
    should_purge_migration_bytecode_for_startup,
)

logger = LogManager.get_logger("db")

# 最近一次 init_database 失败原因（供 main 抛出可读 RuntimeError）/ Last init_database failure detail
_db_init_failure_reason: str | None = None


def get_last_db_init_failure_reason() -> str | None:
    """返回最近一次数据库初始化失败摘要；成功或未调用时为 None。"""
    return _db_init_failure_reason


def _set_db_init_failure(reason: str) -> None:
    global _db_init_failure_reason
    _db_init_failure_reason = reason


def _clear_db_init_failure() -> None:
    global _db_init_failure_reason
    _db_init_failure_reason = None


# ============================================
# 异步数据库引擎 / Async Database Engine
# ============================================

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # SQL 日志由 logging 模块统一管理，输出到 db.log / SQL logs managed by logging module, output to db.log
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # 连接前检查 / Pre-ping connection check
)

# 异步会话工厂 / Async session factory
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def managed_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    托管异步数据库会话 / Managed async database session.

    请求或上下文正常结束时提交事务；任何异常或取消都会走回滚路径，
    包括 Ctrl+C 关闭开发服务时抛出的 asyncio.CancelledError。
    Commit on normal completion; rollback on any exception or cancellation,
    including asyncio.CancelledError during Ctrl+C shutdown in development.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            if session.in_transaction():
                await session.rollback()
            raise


# ============================================
# 同步数据库引擎（用于 Alembic 迁移） / Sync DB Engine (for Alembic migrations)
# ============================================

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=False,  # SQL 日志由 logging 模块统一管理，输出到 db.log / SQL logs managed by logging module, output to db.log
    pool_pre_ping=True,
)

sync_session_factory = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)


def dispose_database_engines_after_fork() -> None:
    """中文: Celery prefork 子进程启动后重建数据库连接池。

    EN: Recreate database pools after a Celery prefork worker child starts.
    """
    sync_engine.dispose(close=False)
    async_engine.sync_engine.dispose(close=False)


# ============================================
# 依赖注入 / Dependency Injection
# ============================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（FastAPI 依赖注入） / Get database session (FastAPI dependency injection)

    使用示例 / Usage:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with managed_async_session() as session:
        yield session


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（上下文管理器） / Get database session (context manager)

    使用示例 / Usage:
        async with get_db_context() as db:
            ...
    """
    async with managed_async_session() as session:
        yield session


# ============================================
# 数据库管理函数 / Database Management Functions
# ============================================


def _warn_if_pg_not_running(exc: Exception) -> None:
    """
    检测到 PostgreSQL 未启动时，在控制台输出清晰的启动指引 / When PostgreSQL is not running, print clear startup instructions to the console.

    仅当错误信息包含 "Connection refused" 时触发
    Triggered only when the error message contains "Connection refused"
    """
    import platform

    err_msg = str(exc)
    if "Connection refused" not in err_msg and "connection refused" not in err_msg:
        return

    host = settings.DATABASE_HOST
    port = settings.DATABASE_PORT
    system = platform.system()

    if system == "Windows":
        start_cmd = (
            "  PowerShell（管理员）/ PowerShell (Administrator):\n"
            "    net start postgresql-x64-16\n"
            "  或 / Or: 打开 services.msc → 找到 PostgreSQL 服务 → 启动"
            "  (Open services.msc → Find PostgreSQL service → Start)"
        )
    elif system == "Darwin":
        start_cmd = (
            "  brew services start postgresql\n"
            "  或 / Or: pg_ctl -D /usr/local/var/postgresql@16 start"
        )
    else:
        start_cmd = (
            "  sudo systemctl start postgresql\n"
            "  或 / Or: sudo service postgresql start"
        )

    logger.warning(
        "\n"
        "╔══════════════════════════════════════════════════════════════════╗\n"
        "║  ⚠  PostgreSQL 未启动 / PostgreSQL is NOT running               ║\n"
        "╚══════════════════════════════════════════════════════════════════╝\n"
        "\n"
        "  无法连接到 PostgreSQL 服务器 / Cannot connect to PostgreSQL server\n"
        "  地址 / Address: %s:%s\n"
        "\n"
        "  请启动 PostgreSQL 后重试 / Please start PostgreSQL and retry:\n"
        "%s\n",
        host,
        port,
        start_cmd,
    )


async def check_database_connection() -> bool:
    """
    检查数据库连接是否正常 / Check if database connection is healthy

    Returns:
        连接是否成功 / Whether connection was successful
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        _warn_if_pg_not_running(e)
        _set_db_init_failure(f"check_database_connection: {e}")
        logger.error("Database connection failed: {}", e)
        return False


def create_database_if_not_exists() -> bool:
    """
    检查数据库是否存在，不存在则创建 / Check if database exists, create if not (sync function)

    Returns:
        是否成功 / Whether successful
    """
    from sqlalchemy import create_engine, text

    # 连接到 postgres 默认数据库来创建目标数据库 / Connect to default postgres DB to create target database
    admin_url = (
        f"postgresql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/postgres"
    )

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            # 检查数据库是否存在 / Check if database exists

            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": settings.DATABASE_NAME},
            )
            exists = result.scalar() is not None

            if not exists:
                logger.info(
                    "Database '{}' does not exist, creating...", settings.DATABASE_NAME
                )
                conn.execute(text(f'CREATE DATABASE "{settings.DATABASE_NAME}"'))
                logger.info(
                    "Database '{}' created successfully", settings.DATABASE_NAME
                )
            else:
                logger.debug("Database '{}' already exists", settings.DATABASE_NAME)

        return True
    except Exception as e:
        _warn_if_pg_not_running(e)
        _set_db_init_failure(f"create_database_if_not_exists: {e}")
        logger.error("Database creation failed: {}", e)
        return False
    finally:
        admin_engine.dispose()


def _read_alembic_version_rows(db_url: str) -> list[str]:
    """Read current alembic stamps. / 读取当前 alembic_version 版本戳。"""
    engine = create_engine(db_url, echo=False)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchall()
        return [str(row[0]) for row in rows]
    except Exception:
        return []
    finally:
        engine.dispose()


def resolve_expected_alembic_heads(
    *,
    alembic_ini: Path,
    backend_dir: Path,
    db_url: str,
    version_locations: list[str],
) -> list[str]:
    """Resolve expected Alembic heads for current migration graph. / 解析当前迁移图的预期 heads。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("version_locations", "\n".join(version_locations))
    return sorted(str(head) for head in ScriptDirectory.from_config(cfg).get_heads())


def should_skip_migration_subprocess(
    *,
    current_stamps: list[str],
    expected_heads: list[str],
) -> tuple[bool, str]:
    """Decide whether startup can skip Alembic subprocess. / 判断启动阶段是否可跳过 Alembic 子进程。"""
    normalized_current = sorted(
        {str(stamp) for stamp in current_stamps if str(stamp or "").strip()}
    )
    normalized_heads = sorted(
        {str(head) for head in expected_heads if str(head or "").strip()}
    )

    if not normalized_heads:
        return False, "expected heads unresolved"

    if not normalized_current:
        return False, "database has no alembic stamps yet"

    if normalized_current != normalized_heads:
        return (
            False,
            "database stamps differ from current heads "
            f"(current={normalized_current}, expected={normalized_heads})",
        )

    return True, f"database already at current heads {normalized_heads}"


def run_migrations() -> bool:
    """
    运行数据库迁移 / Run database migrations (sync, called at startup)

    使用子进程 + PYTHONUTF8=1 运行 Alembic，避免 Windows GBK 环境下编码错误。
    Uses subprocess + PYTHONUTF8=1 to run Alembic, avoiding Windows GBK encoding errors
    when Alembic reads UTF-8 migration files with system default encoding.

    Returns:
        是否成功 / Whether successful
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    try:
        backend_dir = Path(__file__).parent.parent.parent
        alembic_ini = backend_dir / "alembic.ini"

        if not alembic_ini.exists():
            logger.warning("alembic.ini not found, skipping migrations")
            return True

        migrations_dir = backend_dir / "migrations" / "versions"
        if not migrations_dir.exists() or not any(migrations_dir.glob("*.py")):
            logger.warning("No migration files found, skipping migrations")
            return True

        logger.info("Running database migrations...")

        # 通过子进程运行 Alembic，设置 PYTHONUTF8=1 强制 UTF-8 文件 I/O。
        # Run Alembic via subprocess with PYTHONUTF8=1 to force UTF-8 file I/O.
        # 直接调用 Python API（command.upgrade）时，Alembic 内部用系统默认编码打开迁移文件，
        # When calling Python API directly, Alembic uses system default encoding to open migration files,
        # 在 Windows GBK 环境下若迁移文件含 em dash 等 UTF-8 字符会报 'gbk' codec can't decode 错误。
        # causing 'gbk' codec can't decode errors on Windows GBK environments with UTF-8 chars.
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"

        db_url = settings.DATABASE_URL_SYNC.replace("\\", "/")
        version_locations = build_migration_version_locations(
            backend_dir=backend_dir,
            db_url=db_url,
        )
        if should_purge_migration_bytecode_for_startup(debug=settings.DEBUG):
            purged_bytecode = purge_migration_bytecode(version_locations)
            if purged_bytecode:
                logger.info(
                    "Purged {} cached migration bytecode file(s) before Alembic run",
                    len(purged_bytecode),
                )
        else:
            logger.info(
                "Skipping migration bytecode purge during DEBUG startup to avoid reload interrupting Alembic"
            )

        expected_heads = resolve_expected_alembic_heads(
            alembic_ini=alembic_ini,
            backend_dir=backend_dir,
            db_url=db_url,
            version_locations=version_locations,
        )
        current_stamps = _read_alembic_version_rows(db_url)
        should_skip_upgrade, skip_reason = should_skip_migration_subprocess(
            current_stamps=current_stamps,
            expected_heads=expected_heads,
        )
        if should_skip_upgrade:
            logger.info("Skipping Alembic subprocess: {}", skip_reason)
            return True

        # 将迁移脚本写入临时文件 / Write migration script to temp file to avoid complex one-liner escaping
        import tempfile

        # 中文: 这里生成受控的临时 Python 迁移脚本，脚本内 SQL 仍使用绑定参数。
        # EN: This builds a controlled temporary Python migration script; SQL inside still uses bound parameters.
        migration_script = (  # nosec B608
            f"""
import sys
import os
from alembic.config import Config
from alembic import command

backend_dir = {str(backend_dir)!r}
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Step 1: 准备迁移图；启动期不自动删除或补写 alembic_version。
# Step 1: Prepare the migration graph; startup never deletes or stamps alembic_version automatically.
db_url = {db_url!r}
version_locations = {version_locations!r}

print(
    f'[migration] Version locations: {{len(version_locations)}}'
)

# Step 2: 运行迁移（主应用 + 插件 revision 可解析）
cfg = Config({str(alembic_ini)!r})
cfg.set_main_option('script_location', {str(backend_dir / "migrations")!r})
cfg.set_main_option('sqlalchemy.url', db_url)

# 关键：command.upgrade 在创建 ScriptDirectory 时就会读取 version_locations，
# 不能只依赖 env.py 里后置 set_main_option（那时已太晚）。
cfg.set_main_option('version_locations', '\\n'.join(version_locations))
command.upgrade(cfg, 'heads')
"""  # nosec B608
        )

        # 写入临时文件并执行 / Write to temp file and execute
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(migration_script)
            tmp_script = tf.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                cwd=str(backend_dir),
                env=env,
            )
        finally:
            with suppress(Exception):
                os.unlink(tmp_script)

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error").strip()
            _set_db_init_failure(
                f"alembic subprocess (exit {result.returncode}): {err[:4000]}"
            )
            raise RuntimeError(err)

        out = (result.stdout or "").strip()
        if out:
            # 子进程里的 print 默认不进 app 日志；raw 避免 Alembic 输出中的 {} 触发 Loguru 格式化
            tail = out[-6000:] if len(out) > 6000 else out
            logger.opt(raw=True).info(
                "Database migrations subprocess output:\n" + tail + "\n"
            )
        logger.info("Database migrations completed")
        return True
    except FileNotFoundError:
        logger.warning("Alembic not installed, skipping migrations")
        return True
    except Exception as e:
        if _db_init_failure_reason is None:
            _set_db_init_failure(f"run_migrations: {e}")
        logger.error("Database migration failed: {}", e)
        return False


async def init_database() -> bool:
    """
    初始化数据库（启动时调用） / Initialize database (called at startup)

    1. 检查/创建数据库 / Check/create database
    2. 运行迁移 / Run migrations
    3. 验证连接 / Verify connection

    Returns:
        是否成功 / Whether successful
    """
    logger.info("Initializing database...")
    _clear_db_init_failure()

    # 1. 检查/创建数据库 / Check/create database
    if not await asyncio.to_thread(create_database_if_not_exists):
        if _db_init_failure_reason is None:
            _set_db_init_failure("create_database_if_not_exists returned False")
        logger.error(
            "Database init failed at step: create_database_if_not_exists "
            "(see preceding logs)"
        )
        return False

    # 2. 运行迁移 / Run migrations
    if not await asyncio.to_thread(run_migrations):
        if _db_init_failure_reason is None:
            _set_db_init_failure(
                "run_migrations returned False (see db.log for migration subprocess output)",
            )
        logger.error(
            "Database init failed at step: run_migrations — "
            "run manually: cd backend && python -m app.cli db upgrade heads"
        )
        return False

    # 3. 验证连接 / Verify connection
    if not await check_database_connection():
        if _db_init_failure_reason is None:
            _set_db_init_failure("check_database_connection returned False")
        logger.error("Database init failed at step: check_database_connection")
        return False

    _clear_db_init_failure()
    logger.info("Database initialization complete")
    return True


async def close_database() -> None:
    """关闭数据库连接（关闭时调用） / Close database connections (called at shutdown)"""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connections closed")


# 导出 / Exports
__all__ = [
    "async_engine",
    "async_session_factory",
    "sync_engine",
    "sync_session_factory",
    "dispose_database_engines_after_fork",
    "managed_async_session",
    "get_db",
    "get_db_context",
    "check_database_connection",
    "create_database_if_not_exists",
    "get_last_db_init_failure_reason",
    "run_migrations",
    "init_database",
    "close_database",
]
