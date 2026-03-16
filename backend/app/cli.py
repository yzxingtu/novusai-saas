"""
NovusAI SaaS 统一 CLI 入口 / NovusAI SaaS Unified CLI Entry

使用 click 构建命令组，整合 run / celery / db / plugin / license / check / info 等子命令。
Uses click to build command groups, integrating run / celery / db / plugin / license / check / info subcommands.

Usage:
    novusai --help
    novusai run --reload
    novusai celery worker
    novusai db upgrade head
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from pathlib import Path

import click

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("cli")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_CELERY_APP = "app.celery_app:celery_app"
_ALL_QUEUES = "default,high_priority,ai_gateway,scheduled,notification"

# Check command output labels / 检查命令输出标签
_STATUS_OK = "OK"
_STATUS_FAIL = "FAIL"
_CHECK_DB = "Database"
_CHECK_REDIS = "Redis"
_CHECK_CELERY = "Celery"
_CHECK_CELERY_BROKER = "Celery Broker"


# ============================================================
# Main CLI group / 主命令组
# ============================================================


@click.group()
@click.version_option(
    version=settings.APP_VERSION,
    prog_name="NovusAI",
)
def cli() -> None:
    """NovusAI SaaS Management CLI / NovusAI SaaS 管理命令行工具"""
    pass


# ============================================================
# novusai run / 启动 FastAPI
# ============================================================


@cli.command("run")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", type=int, default=8000, help="Port to listen")
@click.option("--reload/--no-reload", default=None, help="Enable auto-reload (default: on in development)")
@click.option("--workers", type=int, default=1, help="Number of workers")
def run_cmd(
    host: str,
    port: int,
    reload: bool | None,
    workers: int,
) -> None:
    """Start FastAPI server via uvicorn / 通过 uvicorn 启动 FastAPI 服务"""
    os.chdir(_BACKEND_DIR)
    do_reload = reload if reload is not None else (settings.APP_ENV == "development")
    python_exe = _get_venv_python()
    cmd = [
        python_exe,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if do_reload:
        cmd.extend(["--reload", "--reload-dir", "app"])
    if workers > 1 and not do_reload:
        cmd.extend(["--workers", str(workers)])
    logger.info("Starting uvicorn: host={} port={} reload={}", host, port, do_reload)
    subprocess.run(cmd, check=True)


# ============================================================
# novusai celery / Celery 管理
# ============================================================


@cli.group("celery", help="Celery worker / beat / flower management")
def celery_cmd() -> None:
    pass


def _get_venv_python() -> str:
    """Use backend .venv Python for consistent env (like run) / 使用 backend .venv 的 Python 保证环境一致"""
    _venv_dir = _BACKEND_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    _venv_py = _venv_dir / ("python.exe" if os.name == "nt" else "python")
    return str(_venv_py) if _venv_py.exists() else sys.executable


def _run_celery(args: list[str]) -> None:
    os.chdir(_BACKEND_DIR)
    python_exe = _get_venv_python()
    cmd = [python_exe, "-m", "celery", "-A", _CELERY_APP] + args
    subprocess.run(cmd, check=True)


@celery_cmd.command()
@click.option("-Q", "--queues", default=None, help="Comma-separated queues (default: all)")
@click.option("-c", "--concurrency", type=int, default=None)
@click.option("-l", "--loglevel", default="info")
def worker(queues: str | None, concurrency: int | None, loglevel: str) -> None:
    """Start Celery worker / 启动 Celery Worker"""
    args = ["worker", f"--loglevel={loglevel}"]
    if queues:
        args.extend(["-Q", queues])
    if concurrency:
        args.extend(["-c", str(concurrency)])
    _run_celery(args)


@celery_cmd.command()
@click.option("-l", "--loglevel", default="info")
def beat(loglevel: str) -> None:
    """Start Celery Beat scheduler / 启动 Celery Beat 定时调度器"""
    _run_celery(["beat", f"--loglevel={loglevel}"])


@celery_cmd.command()
@click.option("-l", "--loglevel", default="info")
def dev(loglevel: str) -> None:
    """Start Worker + Beat (development mode) / 启动 Worker + Beat（开发模式）"""
    os.chdir(_BACKEND_DIR)
    if platform.system() == "Windows":
        python_exe = _get_venv_python()

        def _worker() -> None:
            subprocess.run(
                [
                    python_exe, "-m", "celery", "-A", _CELERY_APP,
                    "worker", "-Q", _ALL_QUEUES,
                    f"--loglevel={loglevel}",
                    "--pool=solo",
                ],
                cwd=str(_BACKEND_DIR),
            )

        def _beat() -> None:
            subprocess.run(
                [
                    python_exe, "-m", "celery", "-A", _CELERY_APP,
                    "beat", f"--loglevel={loglevel}",
                ],
                cwd=str(_BACKEND_DIR),
            )

        click.echo("Starting Celery Worker + Beat (Windows mode)...")
        wt = threading.Thread(target=_worker, daemon=True)
        bt = threading.Thread(target=_beat, daemon=True)
        wt.start()
        bt.start()
        try:
            wt.join()
        except KeyboardInterrupt:
            click.echo("\nStopping...")
    else:
        _run_celery([
            "worker", "--beat", "-Q", _ALL_QUEUES,
            f"--loglevel={loglevel}", "-c", "2",
        ])


@celery_cmd.command()
@click.option("-l", "--loglevel", default="info")
def flower(loglevel: str) -> None:
    """Start Flower monitoring UI / 启动 Flower 监控界面"""
    _run_celery(["flower", f"--loglevel={loglevel}"])


@celery_cmd.command()
def purge() -> None:
    """Purge all queues / 清空所有队列"""
    _run_celery(["purge", "-f"])


# ============================================================
# novusai db / 数据库迁移
# ============================================================


@cli.group("db", help="Database migration (Alembic)")
def db_cmd() -> None:
    pass


def _discover_plugin_migration_paths() -> list[str]:
    """Scan plugins/*/backend/migrations/versions/ for plugin migration paths / 扫描插件 migrations 路径"""
    plugins_dir = _BACKEND_DIR / "plugins"
    paths: list[str] = []
    if plugins_dir.exists():
        for d in sorted(plugins_dir.iterdir()):
            versions = d / "backend" / "migrations" / "versions"
            if versions.is_dir():
                paths.append(str(versions))
    return paths


def _get_alembic_config():
    """Build Alembic config with plugin migration paths injected / 构建含插件迁移路径的 Alembic 配置"""
    from alembic.config import Config

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    base = cfg.get_main_option("version_locations") or ""
    plugin_paths = _discover_plugin_migration_paths()
    if plugin_paths:
        cfg.set_main_option("version_locations", f"{base} {' '.join(plugin_paths)}")
    return cfg


@db_cmd.command("upgrade")
@click.argument("revision", default="head")
def db_upgrade(revision: str) -> None:
    """Run migrations up to revision (default: head) / 执行迁移至指定版本（默认 head）"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.upgrade(cfg, revision)
    logger.info("Database upgraded to revision={}", revision)


@db_cmd.command("revision")
@click.option("-m", "--message", required=True, help="Revision message")
@click.option("--autogenerate", is_flag=True, help="Autogenerate from model changes")
def db_revision(message: str, autogenerate: bool) -> None:
    """Generate new migration file / 生成新迁移文件"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.revision(cfg, message=message, autogenerate=autogenerate)


@db_cmd.command("current")
def db_current() -> None:
    """Show current revision / 显示当前迁移版本"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.current(cfg)


@db_cmd.command("heads")
def db_heads() -> None:
    """Show all head revisions / 显示所有 head 版本"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.heads(cfg)


@db_cmd.command("history")
@click.option("--verbose", "-v", is_flag=True)
def db_history(verbose: bool) -> None:
    """Show migration history / 显示迁移历史"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.history(cfg, verbose=verbose)


@db_cmd.command("stamp")
@click.argument("revision", default="head")
def db_stamp(revision: str) -> None:
    """Stamp database to revision without running migrations / 标记数据库版本（不执行迁移）"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.stamp(cfg, revision)
    logger.info("Database stamped to revision={}", revision)


@db_cmd.command("merge")
@click.option("-m", "--message", default="merge")
def db_merge(message: str) -> None:
    """Merge multiple heads into one / 合并多个 head 为单一版本"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.merge(cfg, message=message)


@db_cmd.command("autogenerate")
@click.option("-m", "--message", required=True, help="Revision message")
def db_autogenerate(message: str) -> None:
    """Autogenerate migration from model changes / 根据模型变更自动生成迁移"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.revision(cfg, message=message, autogenerate=True)


# ============================================================
# novusai plugin / 插件管理
# ============================================================


@cli.group("plugin", help="Plugin create / validate / pack / list / cleanup")
def plugin_cmd() -> None:
    pass


def _load_plugin_cli() -> None:
    """Ensure scripts dir on path and load plugin_cli module / 确保 scripts 在路径中并加载 plugin_cli"""
    scripts_dir = str(_BACKEND_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))
        sys.path.insert(0, scripts_dir)


@plugin_cmd.command("create")
@click.argument("name")
@click.option(
    "--template",
    type=click.Choice(["minimal", "skill", "full-module", "storage"]),
    default="minimal",
)
@click.option("--output", type=click.Path(), default=None)
def plugin_create(name: str, template: str, output: str | None) -> None:
    """Create plugin skeleton / 创建插件骨架"""
    os.chdir(_BACKEND_DIR)
    _load_plugin_cli()
    import plugin_cli as pc

    class Args:
        pass

    args = Args()
    args.name = name
    args.template = template
    args.output = output
    pc.cmd_create(args)


@plugin_cmd.command("validate")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
def plugin_validate(path: str) -> None:
    """Validate plugin directory / 校验插件目录"""
    os.chdir(_BACKEND_DIR)
    _load_plugin_cli()
    import plugin_cli as pc

    class Args:
        pass

    args = Args()
    args.dir = path
    pc.cmd_validate(args)


@plugin_cmd.command("pack")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--output", type=click.Path(), default=None)
def plugin_pack(path: str, output: str | None) -> None:
    """Pack plugin to .zip / 打包插件为 zip"""
    os.chdir(_BACKEND_DIR)
    _load_plugin_cli()
    import plugin_cli as pc

    class Args:
        pass

    args = Args()
    args.dir = path
    args.output = output
    pc.cmd_pack(args)


@plugin_cmd.command("list")
def plugin_list() -> None:
    """List installed plugins (from plugins/ directory) / 列出已安装插件"""
    os.chdir(_BACKEND_DIR)
    from app.plugins.loader import PluginLoader

    loader = PluginLoader()
    names = loader.discover_plugins()
    if not names:
        click.echo("No plugins installed.")
        return
    for n in names:
        click.echo(n)


@plugin_cmd.command("cleanup")
@click.option("--plugin", "-p", required=True, help="Plugin name (e.g. novus-crud-code)")
@click.option(
    "--revision",
    "-r",
    default=None,
    help="Alembic version_num(s) to remove from alembic_version (comma-separated, e.g. ncc_001)",
)
def plugin_cleanup(plugin: str, revision: str | None) -> None:
    """Full cleanup: DB records + Alembic downgrade + build artifacts / 完整清理：DB 记录 + 迁移回退 + 构建产物"""
    os.chdir(_BACKEND_DIR)
    python_exe = _get_venv_python()
    script_path = _BACKEND_DIR / "scripts" / "cleanup_plugin.py"
    cmd = [python_exe, str(script_path), "--plugin", plugin]
    if revision:
        cmd.extend(["--revision", revision])
    subprocess.run(cmd, check=True)


# ============================================================
# novusai license / License 管理
# ============================================================


@cli.group("license", help="License key generate / verify / keygen")
def license_cmd() -> None:
    pass


def _get_key_dir() -> Path:
    d = Path.home() / ".novusai" / "license-keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _generate_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64

    pk = Ed25519PrivateKey.generate()
    priv = base64.b64encode(pk.private_bytes_raw()).decode()
    pub = base64.b64encode(pk.public_key().public_bytes_raw()).decode()
    return priv, pub


@license_cmd.command("generate")
@click.option("--plugin", required=True, help="Plugin name")
@click.option("--email", default="", help="Buyer email")
@click.option("--days", type=int, default=None, help="Validity in days (default: perpetual)")
@click.option("--scope", default="*", help="Version scope")
@click.option("--private-key", default=None, help="Ed25519 private key (base64)")
def license_generate(
    plugin: str,
    email: str,
    days: int | None,
    scope: str,
    private_key: str | None,
) -> None:
    """Generate license key / 生成 License 密钥"""
    from app.plugins.license import generate_license_key

    priv = private_key
    if not priv:
        key_dir = _get_key_dir()
        priv_f = key_dir / "private.key"
        if priv_f.exists():
            priv = priv_f.read_text().strip()
        else:
            click.echo("Generating new Ed25519 keypair...")
            p, pub = _generate_keypair()
            (key_dir / "private.key").write_text(p)
            (key_dir / "public.key").write_text(pub)
            (key_dir / "private.key").chmod(0o600)
            priv = p
            click.echo("Keys saved to: {}".format(key_dir))

    key = generate_license_key(
        plugin_name=plugin,
        version_scope=scope,
        buyer_email=email,
        private_key_b64=priv,
        expires_days=days,
    )
    click.echo("=" * 60)
    click.echo("Generated License Key:")
    click.echo("=" * 60)
    click.echo(key)
    click.echo("=" * 60)
    click.echo("Plugin:  {}".format(plugin))
    click.echo("Email:   {}".format(email or "N/A"))
    click.echo("Scope:   {}".format(scope))
    click.echo("Expires: {} days".format(days) if days else "Never (perpetual)")


@license_cmd.command("verify")
@click.option("--plugin", required=True)
@click.option("--key", "license_key", required=True)
def license_verify(plugin: str, license_key: str) -> None:
    """Verify a license key / 校验 License 密钥"""
    from app.plugins.license import verify_license_key

    result = verify_license_key(license_key, plugin)
    if result:
        click.echo("[{}] License key is valid!".format(_STATUS_OK))
        click.echo("  Plugin:    {}".format(result.get("plugin")))
        click.echo("  Buyer:     {}".format(result.get("buyer", "N/A")))
        click.echo("  Issued at: {}".format(result.get("issued_at")))
        expires = result.get("expires_at")
        if expires:
            import datetime
            dt = datetime.datetime.fromtimestamp(expires, tz=datetime.timezone.utc)
            click.echo("  Expires:   {}".format(dt.isoformat()))
        else:
            click.echo("  Expires:   Never (perpetual)")
    else:
        click.echo("[{}] License key verification failed!".format(_STATUS_FAIL))
        sys.exit(1)


@license_cmd.command("keygen")
def license_keygen() -> None:
    """Generate Ed25519 keypair / 生成 Ed25519 密钥对"""
    priv, pub = _generate_keypair()
    key_dir = _get_key_dir()
    (key_dir / "private.key").write_text(priv)
    (key_dir / "public.key").write_text(pub)
    (key_dir / "private.key").chmod(0o600)
    click.echo("Private key: {}".format(priv))
    click.echo("Public key:  {}".format(pub))
    click.echo()
    click.echo("Keys saved to: {}".format(key_dir))
    click.echo()
    click.echo("Set environment variable for backend:")
    click.echo("  NOVUSAI_LICENSE_PUBLIC_KEY={}".format(pub))


# ============================================================
# novusai check / 环境检查
# ============================================================

def _check_db() -> bool:
    try:
        from sqlalchemy import text

        from app.core.database import sync_session_factory

        session = sync_session_factory()
        session.execute(text("SELECT 1"))
        session.close()
        return True
    except Exception as e:
        logger.debug("DB check failed: {}", e)
        return False


def _check_redis() -> bool:
    try:
        from redis import Redis
        from app.core.config import settings
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        return True
    except Exception as e:
        logger.debug("Redis check failed: {}", e)
        return False


def _check_celery() -> bool:
    try:
        from app.celery_app import celery_app
        celery_app.connection().connect()
        return True
    except Exception as e:
        logger.debug("Celery check failed: {}", e)
        return False


@cli.group("check", help="Environment connectivity check", invoke_without_command=True)
@click.pass_context
def check_cmd(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(check_all)


@check_cmd.command("all")
def check_all() -> None:
    """Check all services (DB, Redis, Celery) / 检查所有服务（DB、Redis、Celery）"""
    os.chdir(_BACKEND_DIR)
    checks = [
        (_CHECK_DB, _check_db),
        (_CHECK_REDIS, _check_redis),
        (_CHECK_CELERY_BROKER, _check_celery),
    ]
    for name, fn in checks:
        ok = fn()
        status = click.style(_STATUS_OK, fg="green") if ok else click.style(_STATUS_FAIL, fg="red")
        click.echo("{}: {}".format(name, status))
    failed = sum(1 for _, fn in checks if not fn())
    if failed:
        sys.exit(1)


@check_cmd.command()
def db() -> None:
    """Check database connection / 检查数据库连接"""
    ok = _check_db()
    status = click.style(_STATUS_OK, fg="green") if ok else click.style(_STATUS_FAIL, fg="red")
    click.echo("{}: {}".format(_CHECK_DB, status))
    sys.exit(0 if ok else 1)


@check_cmd.command()
def redis() -> None:
    """Check Redis connection / 检查 Redis 连接"""
    ok = _check_redis()
    status = click.style(_STATUS_OK, fg="green") if ok else click.style(_STATUS_FAIL, fg="red")
    click.echo("{}: {}".format(_CHECK_REDIS, status))
    sys.exit(0 if ok else 1)


@check_cmd.command()
def celery() -> None:
    """Check Celery broker connection / 检查 Celery Broker 连接"""
    ok = _check_celery()
    status = click.style(_STATUS_OK, fg="green") if ok else click.style(_STATUS_FAIL, fg="red")
    click.echo("{}: {}".format(_CHECK_CELERY, status))
    sys.exit(0 if ok else 1)


# ============================================================
# novusai info / 系统信息
# ============================================================


@cli.command("info")
def info() -> None:
    """Show version, environment, and config summary (sensitive values masked) / 显示版本、环境与配置摘要（敏感项脱敏）"""
    def _mask(s: str, visible: int = 4) -> str:
        if len(s) <= visible:
            return "****"
        return s[:2] + "*" * min(8, len(s) - 4) + s[-2:]

    click.echo("NovusAI SaaS")
    click.echo("  Version:  {}".format(settings.APP_VERSION))
    click.echo("  Env:      {}".format(settings.APP_ENV))
    click.echo("  Python:   {}".format(sys.version.split()[0]))
    click.echo("  Database: {}:{}/{}".format(
        settings.DATABASE_HOST,
        settings.DATABASE_PORT,
        settings.DATABASE_NAME,
    ))
    click.echo("  Redis:    {}:{}".format(settings.REDIS_HOST, settings.REDIS_PORT))


if __name__ == "__main__":
    cli()
