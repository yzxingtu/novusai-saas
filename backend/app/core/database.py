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

logger = LogManager.get_logger("db")

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


# ============================================
# 只读数据库引擎（用于 AI Text-to-SQL） / Read-only DB Engine (for AI Text-to-SQL)
# ============================================

_readonly_engine = None
_readonly_session_factory = None


def _get_readonly_engine():
    """延迟初始化只读引擎 / Lazily initialize read-only engine (only created when AI_READONLY_DB_URL is configured)"""
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
    """获取只读会话工厂 / Get read-only session factory"""
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
    获取数据库会话（上下文管理器） / Get database session (context manager)

    使用示例 / Usage:
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
            f"  PowerShell（管理员）/ PowerShell (Administrator):\n"
            f"    net start postgresql-x64-16\n"
            f"  或 / Or: 打开 services.msc → 找到 PostgreSQL 服务 → 启动"
            f"  (Open services.msc → Find PostgreSQL service → Start)"
        )
    elif system == "Darwin":
        start_cmd = (
            f"  brew services start postgresql\n"
            f"  或 / Or: pg_ctl -D /usr/local/var/postgresql@16 start"
        )
    else:
        start_cmd = (
            f"  sudo systemctl start postgresql\n"
            f"  或 / Or: sudo service postgresql start"
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
                text(
                    "SELECT 1 FROM pg_database WHERE datname = :dbname"
                ),
                {"dbname": settings.DATABASE_NAME}
            )
            exists = result.scalar() is not None

            if not exists:
                logger.info("Database '{}' does not exist, creating...", settings.DATABASE_NAME)
                conn.execute(
                    text(f'CREATE DATABASE "{settings.DATABASE_NAME}"')
                )
                logger.info("Database '{}' created successfully", settings.DATABASE_NAME)
            else:
                logger.debug("Database '{}' already exists", settings.DATABASE_NAME)

        return True
    except Exception as e:
        _warn_if_pg_not_running(e)
        logger.error("Database creation failed: {}", e)
        return False
    finally:
        admin_engine.dispose()


def purge_orphaned_alembic_stamps(backend_dir: Path | None = None) -> bool:
    """
    清除 alembic_version 中无法对应到迁移文件的孤立版本戳。
    Purge orphaned version stamps in alembic_version that have no corresponding migration file.

    用于 codegen auto-migrate 前清理插件残留（如 sm_001_init），避免 alembic revision 报错。
    Used before codegen auto-migrate to clean plugin residuals.
    """
    import os
    import re

    backend = backend_dir or Path(__file__).resolve().parent.parent.parent
    versions_path = backend / "migrations" / "versions"
    if not versions_path.exists():
        return True

    known_revs: set[str] = set()
    rev_pat = re.compile(r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']', re.MULTILINE)

    def _collect(d: Path) -> None:
        if not d.is_dir():
            return
        for f in d.iterdir():
            if f.suffix != ".py" or f.name == "__init__.py":
                continue
            try:
                m = rev_pat.search(f.read_text(encoding="utf-8", errors="replace"))
                if m:
                    known_revs.add(m.group(1))
            except Exception:
                pass

    _collect(versions_path)
    plugins_root = backend.parent / "plugins"
    if plugins_root.is_dir():
        for p in plugins_root.iterdir():
            if p.name.startswith("."):
                continue
            _collect(p / "backend" / "migrations" / "versions")

    if not known_revs:
        return True

    db_url = settings.DATABASE_URL_SYNC.replace("\\", "/")
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            for (stamp,) in rows:
                if stamp not in known_revs:
                    logger.info("Purging orphaned alembic stamp: {}", stamp)
                    conn.execute(text("DELETE FROM alembic_version WHERE version_num = :v"), {"v": stamp})
            conn.commit()
    finally:
        engine.dispose()
    return True


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

        versions_path = str(backend_dir / "migrations" / "versions")

        # 将迁移脚本写入临时文件 / Write migration script to temp file to avoid complex one-liner escaping
        import tempfile
        migration_script = f"""
import os
import re
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

# Step 1: 清除 alembic_version 中不存在于迁移文件的孤立 stamp
# 兼容迁移写法：
#   - revision = 'xxx'
#   - revision: str = 'xxx'
# 并同时扫描主应用 + plugins/* 的迁移目录，避免误删合法插件 revision。
versions_dir = {versions_path!r}
known_revs = set()
_rev_pat = re.compile(r'^revision\\s*(?::[^=]*)?=\\s*[\"\\']([^\"\\']+)[\"\\']', re.MULTILINE)

def _collect_revisions_from_dir(_dir: str) -> None:
    if not os.path.isdir(_dir):
        return
    for _f in os.listdir(_dir):
        if not _f.endswith('.py') or _f == '__init__.py':
            continue
        try:
            with open(os.path.join(_dir, _f), encoding='utf-8') as _fh:
                _src = _fh.read()
            _m = _rev_pat.search(_src)
            if _m:
                known_revs.add(_m.group(1))
        except Exception:
            pass

# 主应用迁移
_collect_revisions_from_dir(versions_dir)

# 插件迁移（全部插件目录；跳过隐藏目录）
plugins_root = os.path.join(os.path.dirname(os.path.dirname(versions_dir)), 'plugins')
if os.path.isdir(plugins_root):
    for _plugin_name in os.listdir(plugins_root):
        if _plugin_name.startswith('.'):
            continue
        _plugin_versions_dir = os.path.join(
            plugins_root, _plugin_name, 'backend', 'migrations', 'versions'
        )
        _collect_revisions_from_dir(_plugin_versions_dir)

print(f'[migration] Known revisions (main+plugins): {{len(known_revs)}}')

# 安全检查：若 known_revs 为空（regex 未匹配到任何文件），跳过清理，避免误删合法 stamp
if known_revs:
    engine = create_engine({db_url!r})
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT version_num FROM alembic_version')).fetchall()
        for row in rows:
            stamp = row[0]
            if stamp not in known_revs:
                print(f'[migration] Purging orphaned stamp: {{stamp}}')
                conn.execute(text('DELETE FROM alembic_version WHERE version_num = :v'), {{'v': stamp}})
        conn.commit()
    engine.dispose()
else:
    print('[migration] WARNING: no revisions found in migration files, skipping stamp purge')

# Step 2: 运行迁移（主应用 + 插件 revision 可解析）
cfg = Config({str(alembic_ini)!r})
cfg.set_main_option('script_location', {str(backend_dir / 'migrations')!r})
cfg.set_main_option('sqlalchemy.url', {db_url!r})

# 关键：command.upgrade 在创建 ScriptDirectory 时就会读取 version_locations，
# 不能只依赖 env.py 里后置 set_main_option（那时已太晚）。
_version_locations = [versions_dir]
if os.path.isdir(plugins_root):
    for _plugin_name in os.listdir(plugins_root):
        if _plugin_name.startswith('.'):
            continue
        _plugin_versions_dir = os.path.join(
            plugins_root, _plugin_name, 'backend', 'migrations', 'versions'
        )
        if os.path.isdir(_plugin_versions_dir):
            _version_locations.append(_plugin_versions_dir)
cfg.set_main_option('version_locations', ' '.join(_version_locations))

try:
    command.upgrade(cfg, 'heads')
except Exception as e:
    err_str = str(e)
    # 若 upgrade 失败原因是"表已存在"（DuplicateTable），说明表结构完整但 stamp 缺失
    # 用 stamp heads 恢复一致性，而非报错
    if 'already exists' in err_str or 'DuplicateTable' in type(e).__name__:
        print('[migration] Tables exist but stamps missing, stamping heads to recover...')
        command.stamp(cfg, 'heads')
    else:
        raise
"""

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
            raise RuntimeError(err)

        logger.info("Database migrations completed")
        return True
    except FileNotFoundError:
        logger.warning("Alembic not installed, skipping migrations")
        return True
    except Exception as e:
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

    # 1. 检查/创建数据库 / Check/create database
    if not await asyncio.to_thread(create_database_if_not_exists):
        return False

    # 2. 运行迁移 / Run migrations
    if not await asyncio.to_thread(run_migrations):
        return False

    # 3. 验证连接 / Verify connection
    if not await check_database_connection():
        return False

    logger.info("Database initialization complete")
    return True


async def close_database() -> None:
    """关闭数据库连接（关闭时调用） / Close database connections (called at shutdown)"""
    await async_engine.dispose()
    sync_engine.dispose()
    if _readonly_engine is not None:
        await _readonly_engine.dispose()
    logger.info("Database connections closed")


# 导出 / Exports
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
    "purge_orphaned_alembic_stamps",
    "run_migrations",
    "init_database",
    "close_database",
    "Base",
]
