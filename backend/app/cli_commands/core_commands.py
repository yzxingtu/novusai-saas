"""Core CLI command domains: run/celery/db/plugin/license."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from pathlib import Path

import click

from app import cli_runtime_helpers as runtime_helpers
from app.cli_commands import state as S
from app.core.config import settings

logger = S.logger
_BACKEND_DIR = S._BACKEND_DIR
_CELERY_APP = S._CELERY_APP
_ALL_QUEUES = S._ALL_QUEUES
_STATUS_OK = S._STATUS_OK
_STATUS_FAIL = S._STATUS_FAIL
_run_async = S._run_async


def _celery_broker_hint() -> str:
    broker_url = runtime_helpers.redact_url(settings.celery_broker_url)
    return (
        f"Celery broker is not reachable: {broker_url}\n\n"
        "Start the local development Redis service first from the repository root:\n"
        "  docker compose -f docker-compose.dev.yml up -d redis\n\n"
        "Then retry your Celery command, for example:\n"
        "  novusai celery dev\n\n"
        "If you use a different broker, update CELERY_BROKER_URL in backend/.env."
    )


def _ensure_celery_broker_available() -> None:
    if runtime_helpers.check_celery_broker_url(settings.celery_broker_url, logger):
        return
    raise click.ClickException(_celery_broker_hint())


@click.command("run")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", type=int, default=8000, help="Port to listen")
@click.option(
    "--reload/--no-reload",
    default=None,
    help="Enable auto-reload (default: on in development)",
)
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


@click.group("celery", help="Celery worker / beat / flower management")
def celery_cmd() -> None:
    pass


def _get_venv_python() -> str:
    """Use backend .venv Python for consistent env / 使用 backend .venv Python 保证环境一致。"""
    return runtime_helpers.get_venv_python(_BACKEND_DIR)


def _run_celery(args: list[str]) -> None:
    _ensure_celery_broker_available()
    runtime_helpers.run_celery(_BACKEND_DIR, _CELERY_APP, args)


@celery_cmd.command()
@click.option(
    "-Q", "--queues", default=None, help="Comma-separated queues (default: all)"
)
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
    _ensure_celery_broker_available()
    if platform.system() == "Windows":
        python_exe = _get_venv_python()

        def _worker() -> None:
            subprocess.run(
                [
                    python_exe,
                    "-m",
                    "celery",
                    "-A",
                    _CELERY_APP,
                    "worker",
                    "-Q",
                    _ALL_QUEUES,
                    f"--loglevel={loglevel}",
                    "--pool=solo",
                ],
                cwd=str(_BACKEND_DIR),
            )

        def _beat() -> None:
            subprocess.run(
                [
                    python_exe,
                    "-m",
                    "celery",
                    "-A",
                    _CELERY_APP,
                    "beat",
                    f"--loglevel={loglevel}",
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
        _run_celery(
            [
                "worker",
                "--beat",
                "-Q",
                _ALL_QUEUES,
                f"--loglevel={loglevel}",
                "-c",
                "2",
            ]
        )


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


@click.group("db", help="Database migration (Alembic)")
def db_cmd() -> None:
    pass


def _discover_plugin_migration_paths() -> list[str]:
    """
    Resolve plugin migration paths from DB-registered plugins.
    / 仅从数据库已注册插件解析迁移路径。
    """
    return runtime_helpers.discover_plugin_migration_paths(_BACKEND_DIR)


def _get_alembic_config():
    """Build Alembic config with plugin migration paths injected / 构建含插件迁移路径的 Alembic 配置。"""
    return runtime_helpers.get_alembic_config(_BACKEND_DIR)


@db_cmd.command("upgrade")
@click.argument("revision", default="heads")
def db_upgrade(revision: str) -> None:
    """Run migrations up to revision (default: heads) / 执行迁移至指定版本（默认 heads，与启动自动迁移一致）"""
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
@click.argument("revision", default="heads")
def db_stamp(revision: str) -> None:
    """Stamp database to revision without running migrations / 标记数据库版本（不执行迁移，默认 heads）"""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    command.stamp(cfg, revision)
    logger.info("Database stamped to revision={}", revision)


@db_cmd.command("merge")
@click.option("-m", "--message", default="merge", help="Message for merge revision")
@click.option(
    "-r",
    "--revisions",
    default="heads",
    help="Revisions to merge (default: heads). Use 'heads' to merge all current heads, or comma-separated IDs",
)
def db_merge(message: str, revisions: str) -> None:
    """Merge multiple heads into one / 合并多个 head 为单一版本."""
    os.chdir(_BACKEND_DIR)
    from alembic import command

    cfg = _get_alembic_config()
    revs = [r.strip() for r in revisions.replace(",", " ").split() if r.strip()]
    if not revs:
        revs = ["heads"]
    command.merge(cfg, revisions=revs, message=message)


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


@click.group(
    "plugin",
    help="Plugin build / create / validate / pack / list / cleanup / sync / enable",
)
def plugin_cmd() -> None:
    pass


def _load_plugin_cli() -> None:
    """Ensure scripts dir on path and load plugin_cli module / 确保 scripts 在路径中并加载 plugin_cli。"""
    runtime_helpers.load_plugin_cli(_BACKEND_DIR)


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


@plugin_cmd.command("build")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
def plugin_build(path: str) -> None:
    """Build plugin frontend release assets / 构建插件前端发布产物"""
    os.chdir(_BACKEND_DIR)
    _load_plugin_cli()
    import plugin_cli as pc

    class Args:
        pass

    args = Args()
    args.dir = path
    pc.cmd_build(args)


@plugin_cmd.command("pack")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--output", type=click.Path(), default=None)
@click.option("--release", is_flag=True, default=False)
@click.option("--source", is_flag=True, default=False)
def plugin_pack(
    path: str,
    output: str | None,
    release: bool,
    source: bool,
) -> None:
    """Pack plugin to .zip / 打包插件为 zip"""
    os.chdir(_BACKEND_DIR)
    _load_plugin_cli()
    import plugin_cli as pc

    class Args:
        pass

    args = Args()
    args.dir = path
    args.output = output
    args.release = release
    args.source = source
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
@click.option(
    "--plugin", "-p", required=True, help="Plugin name (e.g. novus-crud-code)"
)
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


def _run_plugin_operator_action(
    plugin_name: str,
    action,
    *,
    init_redis: bool = False,
):
    """Run plugin operator action in managed DB session / 在托管 DB 会话中执行插件运维动作。"""
    return runtime_helpers.run_plugin_operator_action(
        _BACKEND_DIR,
        plugin_name,
        action,
        init_redis=init_redis,
        run_async=_run_async,
    )


@plugin_cmd.command("sync-manifest")
@click.option("--plugin", "-p", "plugin_name", required=True, help="Plugin name")
def plugin_sync_manifest(plugin_name: str) -> None:
    """Sync disk plugin.yaml into DB snapshot / 同步磁盘 plugin.yaml 到数据库快照"""

    async def _action(service, plugin):
        synced = await service.sync_manifest(plugin.id)
        return {
            "name": synced.name,
            "version": synced.version,
        }

    result = _run_plugin_operator_action(plugin_name, _action)
    click.echo(
        "Manifest synced: {}@{}".format(
            result["name"],
            result["version"] or "unknown",
        )
    )


@plugin_cmd.command("activate-license")
@click.option("--plugin", "-p", "plugin_name", required=True, help="Plugin name")
@click.option("--key", "license_key", required=True, help="License key to activate")
def plugin_activate_license(plugin_name: str, license_key: str) -> None:
    """Activate a plugin license in the local DB / 在本地数据库中激活插件授权"""

    async def _action(service, plugin):
        await service.activate_license(plugin.id, license_key)
        return {"name": plugin.name}

    result = _run_plugin_operator_action(plugin_name, _action)
    click.echo("License activated: {}".format(result["name"]))


@plugin_cmd.command("enable")
@click.option("--plugin", "-p", "plugin_name", required=True, help="Plugin name")
def plugin_enable(plugin_name: str) -> None:
    """Enable an installed plugin / 启用已安装插件"""

    async def _action(service, plugin):
        await service.enable_plugin(plugin.id)
        return {"name": plugin.name}

    result = _run_plugin_operator_action(plugin_name, _action, init_redis=True)
    click.echo("Plugin enabled: {}".format(result["name"]))
    click.echo(
        "Note: if the backend server is already running in another process, restart it or use the admin API enable path there to load runtime extensions."
    )


@plugin_cmd.command("assign-tenant")
@click.option("--plugin", "-p", "plugin_name", required=True, help="Plugin name")
@click.option(
    "--tenant-id",
    "tenant_ids",
    type=int,
    multiple=True,
    required=True,
    help="Tenant ID to assign; repeat the option for multiple tenants",
)
def plugin_assign_tenant(plugin_name: str, tenant_ids: tuple[int, ...]) -> None:
    """Assign a plugin to one or more tenants / 将插件分配给一个或多个企业"""

    async def _action(service, plugin):
        assigned = await service.assign_tenants(plugin.id, list(tenant_ids))
        return {
            "name": plugin.name,
            "assigned": assigned,
        }

    result = _run_plugin_operator_action(plugin_name, _action)
    click.echo(
        "Assigned {} tenant(s): {}".format(
            result["assigned"],
            result["name"],
        )
    )


# ============================================================
# novusai license / License 管理
# ============================================================


@click.group("license", help="License key generate / verify / keygen")
def license_cmd() -> None:
    pass


def _get_key_dir() -> Path:
    d = Path.home() / ".novusai" / "license-keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _generate_keypair() -> tuple[str, str]:
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pk = Ed25519PrivateKey.generate()
    priv = base64.b64encode(pk.private_bytes_raw()).decode()
    pub = base64.b64encode(pk.public_key().public_bytes_raw()).decode()
    return priv, pub


@license_cmd.command("generate")
@click.option("--plugin", required=True, help="Plugin name")
@click.option("--email", default="", help="Buyer email")
@click.option(
    "--days", type=int, default=None, help="Validity in days (default: perpetual)"
)
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
            click.echo(f"Keys saved to: {key_dir}")

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
    click.echo(f"Plugin:  {plugin}")
    click.echo("Email:   {}".format(email or "N/A"))
    click.echo(f"Scope:   {scope}")
    click.echo(f"Expires: {days} days" if days else "Never (perpetual)")


@license_cmd.command("verify")
@click.option("--plugin", required=True)
@click.option("--key", "license_key", required=True)
def license_verify(plugin: str, license_key: str) -> None:
    """Verify a license key / 校验 License 密钥"""
    from app.plugins.license import verify_license_key

    result = verify_license_key(license_key, plugin)
    if result:
        click.echo(f"[{_STATUS_OK}] License key is valid!")
        click.echo("  Plugin:    {}".format(result.get("plugin")))
        click.echo("  Buyer:     {}".format(result.get("buyer", "N/A")))
        click.echo("  Issued at: {}".format(result.get("issued_at")))
        expires = result.get("expires_at")
        if expires:
            import datetime

            dt = datetime.datetime.fromtimestamp(expires, tz=datetime.timezone.utc)
            click.echo(f"  Expires:   {dt.isoformat()}")
        else:
            click.echo("  Expires:   Never (perpetual)")
    else:
        click.echo(f"[{_STATUS_FAIL}] License key verification failed!")
        sys.exit(1)


@license_cmd.command("keygen")
def license_keygen() -> None:
    """Generate Ed25519 keypair. Private key is printed to stdout. For dev only; use secure storage in production. / 生成 Ed25519 密钥对，私钥输出到 stdout，仅用于开发环境"""
    priv, pub = _generate_keypair()
    key_dir = _get_key_dir()
    (key_dir / "private.key").write_text(priv)
    (key_dir / "public.key").write_text(pub)
    (key_dir / "private.key").chmod(0o600)
    click.echo(f"Private key: {priv}")
    click.echo(f"Public key:  {pub}")
    click.echo()
    click.echo(f"Keys saved to: {key_dir}")
    click.echo()
    click.echo("Set environment variable for backend:")
    click.echo(f"  NOVUSAI_LICENSE_PUBLIC_KEY={pub}")
