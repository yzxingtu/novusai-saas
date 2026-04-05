"""
数据库连接模块 / Database Connection Module

提供异步数据库连接、会话管理和依赖注入
Provides async database connections, session management and dependency injection.
"""

import asyncio
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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


@dataclass(frozen=True)
class MainSchemaCoverage:
    """Main app schema coverage snapshot. / 主应用 schema 覆盖率快照。"""

    model_table_count: int
    total_model_column_count: int
    missing_tables: tuple[str, ...]
    missing_columns_by_table: dict[str, tuple[str, ...]]

    @property
    def missing_column_count(self) -> int:
        """Total missing model columns. / 缺失模型列总数。"""
        return sum(len(cols) for cols in self.missing_columns_by_table.values())

    @property
    def column_coverage(self) -> float:
        """Column coverage ratio. / 模型列覆盖率。"""
        if self.total_model_column_count <= 0:
            return 1.0
        return 1.0 - (self.missing_column_count / self.total_model_column_count)


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


_ALEMBIC_REVISION_RE = re.compile(
    r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


def _collect_revision_ids_from_dir(directory: Path) -> set[str]:
    """Collect revision IDs from one versions dir. / 收集单个 versions 目录的 revision ID。"""
    revisions: set[str] = set()
    if not directory.is_dir():
        return revisions

    for file_path in directory.iterdir():
        if file_path.suffix != ".py" or file_path.name == "__init__.py":
            continue
        try:
            src = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Cannot read migration file {}: {}", file_path, exc)
            continue
        match = _ALEMBIC_REVISION_RE.search(src)
        if match:
            revisions.add(match.group(1))
    return revisions


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


def _inspect_main_schema_coverage(db_url: str) -> MainSchemaCoverage:
    """Inspect current DB coverage against main models. / 对照主应用模型检查当前 DB 覆盖率。"""
    import app.models  # noqa: F401
    from app.core.base_model import Base

    engine = create_engine(db_url, echo=False)
    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names(schema="public"))
        model_tables = set(Base.metadata.tables.keys())
        missing_tables = tuple(sorted(model_tables - actual_tables))

        total_model_column_count = 0
        missing_columns_by_table: dict[str, tuple[str, ...]] = {}

        for table_name in sorted(model_tables):
            model_cols = tuple(
                col.name for col in Base.metadata.tables[table_name].columns
            )
            total_model_column_count += len(model_cols)

            if table_name in missing_tables:
                missing_columns_by_table[table_name] = model_cols
                continue

            actual_cols = {
                str(column["name"])
                for column in inspector.get_columns(table_name, schema="public")
            }
            missing_cols = tuple(sorted(set(model_cols) - actual_cols))
            if missing_cols:
                missing_columns_by_table[table_name] = missing_cols

        return MainSchemaCoverage(
            model_table_count=len(model_tables),
            total_model_column_count=total_model_column_count,
            missing_tables=missing_tables,
            missing_columns_by_table=missing_columns_by_table,
        )
    finally:
        engine.dispose()


def should_auto_recover_missing_main_branch_stamp(
    *,
    current_stamps: list[str],
    main_revision_ids: set[str],
    coverage: MainSchemaCoverage,
    max_missing_columns: int = 3,
) -> tuple[bool, str]:
    """Decide whether missing main stamp can be auto-recovered. / 判断是否可自动恢复缺失的主分支 stamp。"""
    if not current_stamps:
        return False, "no existing alembic_version rows"

    if any(stamp in main_revision_ids for stamp in current_stamps):
        return False, "main branch stamp already present"

    if coverage.missing_tables:
        sample = ", ".join(coverage.missing_tables[:5])
        return False, f"missing main tables: {sample}"

    if coverage.missing_column_count > max_missing_columns:
        return (
            False,
            f"missing too many model columns: {coverage.missing_column_count}",
        )

    return True, (
        "main branch stamp missing while schema is already mostly present; "
        f"column_coverage={coverage.column_coverage:.4f}"
    )


def _resolve_main_head_revision(cfg, main_revision_ids: set[str]) -> str | None:
    """Resolve the current main-app head revision. / 解析当前主应用 head revision。"""
    from alembic.script import ScriptDirectory

    main_heads = [
        revision
        for revision in ScriptDirectory.from_config(cfg).get_heads()
        if revision in main_revision_ids
    ]
    if len(main_heads) != 1:
        return None
    return str(main_heads[0])


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


def maybe_recover_missing_main_branch_stamp(
    *,
    cfg,
    db_url: str,
    main_versions_dir: str | Path,
) -> tuple[bool, str]:
    """Attempt to restore missing main branch stamp. / 尝试恢复缺失的主分支 stamp。"""
    main_revision_ids = _collect_revision_ids_from_dir(Path(main_versions_dir))
    current_stamps = _read_alembic_version_rows(db_url)
    coverage = _inspect_main_schema_coverage(db_url)
    can_recover, reason = should_auto_recover_missing_main_branch_stamp(
        current_stamps=current_stamps,
        main_revision_ids=main_revision_ids,
        coverage=coverage,
    )
    if not can_recover:
        return False, reason

    main_head = _resolve_main_head_revision(cfg, main_revision_ids)
    if not main_head:
        return False, "expected exactly one main-app head revision"

    from alembic import command

    command.stamp(cfg, main_head)
    return True, (
        f"Recovered missing main branch stamp by stamping '{main_head}' "
        f"(existing non-main stamps: {', '.join(current_stamps)})"
    )


def purge_orphaned_alembic_stamps(backend_dir: Path | None = None) -> bool:
    """
    清除 alembic_version 中无法对应到迁移文件的孤立版本戳。
    Purge orphaned version stamps in alembic_version that have no corresponding migration file.

    用于 codegen auto-migrate 前清理插件残留（如 sm_001_init），避免 alembic revision 报错。
    Used before codegen auto-migrate to clean plugin residuals.
    """
    import re

    backend = backend_dir or Path(__file__).resolve().parent.parent.parent
    versions_path = backend / "migrations" / "versions"
    if not versions_path.exists():
        return True

    known_revs: set[str] = set()
    _failed_reads: list[str] = []
    rev_pat = re.compile(
        r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']', re.MULTILINE
    )

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
            except Exception as e:
                _failed_reads.append(str(f))
                logger.warning("Cannot read migration file {}: {}", f, e)

    db_url = settings.DATABASE_URL_SYNC.replace("\\", "/")
    for version_location in build_migration_version_locations(
        backend_dir=backend,
        db_url=db_url,
    ):
        _collect(Path(version_location))

    if _failed_reads:
        logger.warning(
            "Skipping stamp purge: {} migration file(s) unreadable ({})",
            len(_failed_reads),
            ", ".join(_failed_reads[:5]),
        )
        return True

    if not known_revs:
        return True

    # 临时抑制 SQLAlchemy SQL 日志，避免 codegen rollback/generate 时控制台刷屏
    import logging as _log

    _sa_log = _log.getLogger("sqlalchemy.engine")
    _old_level = _sa_log.level
    _sa_log.setLevel(_log.WARNING)
    engine = None
    try:
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchall()
            for (stamp,) in rows:
                if stamp not in known_revs:
                    logger.info("Purging orphaned alembic stamp: {}", stamp)
                    conn.execute(
                        text("DELETE FROM alembic_version WHERE version_num = :v"),
                        {"v": stamp},
                    )
            conn.commit()
    finally:
        _sa_log.setLevel(_old_level)
        if engine is not None:
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

        versions_path = str(backend_dir / "migrations" / "versions")

        # 将迁移脚本写入临时文件 / Write migration script to temp file to avoid complex one-liner escaping
        import tempfile

        migration_script = f"""
import sys
import os
import re
from pathlib import Path
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

backend_dir = {str(backend_dir)!r}
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Step 1: 清除 alembic_version 中不存在于迁移文件的孤立 stamp
# 兼容迁移写法：
#   - revision = 'xxx'
#   - revision: str = 'xxx'
# 并同时扫描主应用 + plugins/* 的迁移目录，避免误删合法插件 revision。
versions_dir = {versions_path!r}
db_url = {db_url!r}
version_locations = {version_locations!r}
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

for _version_dir in version_locations:
    _collect_revisions_from_dir(_version_dir)

print(
    f'[migration] Version locations: {{len(version_locations)}}, '
    f'known revisions: {{len(known_revs)}}'
)

# 安全检查：若 known_revs 为空（regex 未匹配到任何文件），跳过清理，避免误删合法 stamp
if known_revs:
    engine = create_engine(db_url)
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
cfg.set_main_option('script_location', {str(backend_dir / "migrations")!r})
cfg.set_main_option('sqlalchemy.url', db_url)

# 关键：command.upgrade 在创建 ScriptDirectory 时就会读取 version_locations，
# 不能只依赖 env.py 里后置 set_main_option（那时已太晚）。
cfg.set_main_option('version_locations', '\\n'.join(version_locations))

try:
    command.upgrade(cfg, 'heads')
except Exception as e:
    err_str = str(e)
    # 仅在 alembic_version 中无任何记录时，DuplicateTable 才视为「表已手工建好、缺 stamp」。
    # 若已有 revision 记录仍报 DuplicateTable，多为卡在某条迁移上；此时 stamp heads 会跳过后续 ALTER，
    # 导致 ORM（如 owner_tenant_id）与真实库列不一致——禁止自动 stamp。
    if 'already exists' in err_str or 'DuplicateTable' in type(e).__name__:
        eng = create_engine(db_url)
        stamp_count = -1
        try:
            with eng.connect() as c:
                r = c.execute(text('SELECT COUNT(*) FROM alembic_version')).fetchone()
            stamp_count = int(r[0]) if r else 0
        except Exception as ver_exc:
            print(
                '[migration] Cannot read alembic_version: '
                + str(ver_exc)
                + '; refusing unsafe stamp.'
            )
            raise e from ver_exc
        finally:
            eng.dispose()
        if stamp_count == 0:
            print(
                '[migration] Tables exist but stamps missing, stamping heads to recover...'
            )
            command.stamp(cfg, 'heads')
        else:
            from app.core.database import maybe_recover_missing_main_branch_stamp

            recovered, recover_msg = maybe_recover_missing_main_branch_stamp(
                cfg=cfg,
                db_url=db_url,
                main_versions_dir=Path(versions_dir),
            )
            if recovered:
                print('[migration] ' + recover_msg)
                command.upgrade(cfg, 'heads')
            else:
                print(
                    '[migration] DuplicateTable/already exists but alembic_version is nonempty; '
                    + recover_msg
                    + '. Fix the DB conflict or run: python -m app.cli db upgrade heads'
                )
                raise
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
    "get_db",
    "get_db_context",
    "check_database_connection",
    "create_database_if_not_exists",
    "purge_orphaned_alembic_stamps",
    "get_last_db_init_failure_reason",
    "run_migrations",
    "init_database",
    "close_database",
]
