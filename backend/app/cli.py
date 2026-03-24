"""
NovusAI SaaS 统一 CLI 入口 / NovusAI SaaS Unified CLI Entry

使用 click 构建命令组，整合 run / celery / db / plugin / license / check / info 等子命令。
Uses click to build command groups, integrating run / celery / db / plugin / license / check / info subcommands.

Usage:
    novusai --help
    novusai run --reload
    novusai celery worker
    novusai db upgrade heads
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from contextlib import contextmanager
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


@cli.group("db", help="Database migration (Alembic)")
def db_cmd() -> None:
    pass


def _discover_plugin_migration_paths() -> list[str]:
    """
    Resolve plugin migration paths from DB-registered plugins.
    / 仅从数据库已注册插件解析迁移路径。
    """
    from app.plugins.migration_paths import build_migration_version_locations

    version_locations = build_migration_version_locations(backend_dir=_BACKEND_DIR)
    return version_locations[1:]


def _get_alembic_config():
    """Build Alembic config with plugin migration paths injected / 构建含插件迁移路径的 Alembic 配置"""
    from alembic.config import Config

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    merged_paths: list[str] = []
    seen_paths: set[str] = set()

    for path in (
        cfg.get_version_locations_list() or []
    ) + _discover_plugin_migration_paths():
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        merged_paths.append(path)

    if merged_paths:
        cfg.set_main_option("version_locations", "\n".join(merged_paths))
    return cfg


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


@cli.group(
    "plugin",
    help="Plugin build / create / validate / pack / list / cleanup / sync / enable",
)
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
    """Run a plugin operator action inside a managed DB session / 在托管 DB 会话中执行插件运维动作。"""

    async def _do():
        from app.core.database import get_db_context
        from app.core.redis import RedisManager
        from app.services.system.plugin_service import PluginService

        if init_redis:
            await RedisManager.init()
        try:
            async with get_db_context() as db:
                service = PluginService(db)
                plugin = await service.get_by_name(plugin_name)
                if not plugin:
                    raise SystemExit(f"Plugin '{plugin_name}' not found")
                return await action(service, plugin)
        finally:
            if init_redis:
                await RedisManager.close()

    return _run_async(_do())


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
    """Generate Ed25519 keypair. Private key is printed to stdout. For dev only; use secure storage in production. / 生成 Ed25519 密钥对，私钥输出到 stdout，仅用于开发环境"""
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
# novusai codegen / CRUD 代码生成器
# ============================================================

_CODEGEN_PROJECT_ROOT = _BACKEND_DIR.parent


def _load_config_from_file(path: str) -> dict:
    """从 YAML 文件加载配置 / Load config from YAML file."""
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_config_stdin() -> dict:
    """从 stdin 读取 YAML 配置 / Load config from stdin."""
    import yaml

    data = sys.stdin.read()
    return yaml.safe_load(data) or {}


def _deep_merge(target: dict, source: dict) -> None:
    """Merge source into target (source values override). In-place."""
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


def _run_async(coro):
    """在同步上下文中运行异步协程 / Run async coroutine from sync context."""
    import asyncio

    return asyncio.run(coro)


def _echo_json(data: dict) -> None:
    import json

    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _json_error(
    message: str, *, code: str | None = None, data: dict | None = None
) -> dict:
    payload: dict = {
        "success": False,
        "data": data,
        "error": {
            "message": message,
        },
    }
    if code:
        payload["error"]["code"] = code
    return payload


def _json_success(data: dict | list | None = None) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
    }


def _codegen_delete_hint(reason_code: str | None, config_id: int) -> str | None:
    """Return human-readable delete guidance / 返回删除阻断的人类可读提示."""
    if reason_code in {
        "manifest_present",
        "generated_state",
        "generation_history_present",
    }:
        return "Hint: run `novusai codegen rollback --id {}` first.".format(config_id)
    return None


@contextmanager
def _suppress_logging(enabled: bool):
    if not enabled:
        yield
        return

    import logging

    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous_disable)


def _run_quietly(enabled: bool, func, *args, **kwargs):
    with _suppress_logging(enabled):
        return func(*args, **kwargs)


def _render_trace_text(payload: dict) -> str:
    lines: list[str] = []
    summary = payload.get("summary") or {}
    primary = payload.get("primary_error")
    operation_logs = payload.get("operation_logs") or []
    log_matches = payload.get("log_matches") or []
    lines.append(f"Trace ID: {payload.get('trace_id')}")
    lines.append(
        "Summary: operation_logs={} log_matches={} source={} redacted={}".format(
            summary.get("operation_logs", 0),
            summary.get("log_matches", 0),
            summary.get("source", "unknown"),
            payload.get("redacted", True),
        )
    )
    files = summary.get("log_files") or []
    if files:
        lines.append("Log files: {}".format(", ".join(files)))

    if primary:
        lines.append("")
        lines.append("Primary error:")
        lines.append(
            "  {}:{} ({}-{})".format(
                primary.get("file", ""),
                primary.get("line", 0),
                primary.get("start_line", 0),
                primary.get("end_line", 0),
            )
        )
        for row in primary.get("block", []):
            lines.append(f"  {row}")

    if operation_logs:
        lines.append("")
        lines.append("Operation logs:")
        for item in operation_logs:
            lines.append(
                "  [{created_at}] tenant={tenant_id} user={username} method={method} path={path} status={status_code} code={response_code} msg={response_message} duration={duration_ms}ms".format(
                    created_at=item.get("created_at", ""),
                    tenant_id=item.get("tenant_id"),
                    username=item.get("username"),
                    method=item.get("method"),
                    path=item.get("path"),
                    status_code=item.get("status_code"),
                    response_code=item.get("response_code"),
                    response_message=item.get("response_message"),
                    duration_ms=item.get("duration_ms"),
                )
            )

    if log_matches:
        lines.append("")
        lines.append("Other log hits:")
        for item in log_matches:
            lines.append(
                "  {}:{} ({}-{})".format(
                    item.get("file", ""),
                    item.get("line", 0),
                    item.get("start_line", 0),
                    item.get("end_line", 0),
                )
            )

    return "\n".join(lines)


@cli.group("trace", help="Trace lookup / 根据 trace_id 查询错误上下文")
def trace_cmd() -> None:
    pass


@trace_cmd.command("show")
@click.argument("trace_id", type=str)
@click.option(
    "--source",
    type=click.Choice(["auto", "db", "logs", "all"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Lookup source",
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
@click.option(
    "--context",
    type=int,
    default=20,
    show_default=True,
    help="Context lines around each log match",
)
@click.option(
    "--max-blocks",
    type=int,
    default=10,
    show_default=True,
    help="Maximum log blocks to return",
)
@click.option(
    "--since-hours",
    type=int,
    default=72,
    show_default=True,
    help="Only scan files modified within N hours (set <=0 to disable)",
)
@click.option(
    "--no-redact",
    is_flag=True,
    help="Disable redaction (blocked in production unless --unsafe + env gate)",
)
@click.option(
    "--unsafe",
    is_flag=True,
    help="Acknowledge unsafe output in production/staging",
)
def trace_show(
    trace_id: str,
    source: str,
    output_json: bool,
    context: int,
    max_blocks: int,
    since_hours: int,
    no_redact: bool,
    unsafe: bool,
) -> None:
    """Show trace context from operation logs and log files / 从操作日志与文件日志查询 trace 详情。"""
    os.chdir(_BACKEND_DIR)

    source = source.lower()
    since_hours_opt: int | None = since_hours if since_hours > 0 else None
    redact = not no_redact
    is_prod_like = settings.APP_ENV.lower() in {"production", "staging"}
    unsafe_allowed = os.getenv("NOVUSAI_ALLOW_UNSAFE_TRACE") == "1"

    if is_prod_like and no_redact and not (unsafe and unsafe_allowed):
        message = (
            "Unsafe trace output is blocked in production/staging. "
            "Use --unsafe and set NOVUSAI_ALLOW_UNSAFE_TRACE=1."
        )
        if output_json:
            _echo_json(_json_error(message, code="unsafe_output_blocked"))
        else:
            click.echo(f"Error: {message}", err=True)
        sys.exit(2)

    from app.services.system import TraceLookupService

    async def _lookup_with_db() -> dict:
        from app.core.database import get_db_context

        async with get_db_context() as db:
            service = TraceLookupService(
                db=db,
                log_dir=(_BACKEND_DIR / settings.LOG_DIR),
            )
            result = await service.lookup(
                trace_id,
                source=source,
                context=max(0, context),
                max_blocks=max(1, max_blocks),
                since_hours=since_hours_opt,
                redact=redact,
            )
            return result.to_dict()

    async def _lookup_logs_only() -> dict:
        service = TraceLookupService(
            db=None,
            log_dir=(_BACKEND_DIR / settings.LOG_DIR),
        )
        result = await service.lookup(
            trace_id,
            source=source,
            context=max(0, context),
            max_blocks=max(1, max_blocks),
            since_hours=since_hours_opt,
            redact=redact,
        )
        return result.to_dict()

    async def _lookup_auto() -> dict:
        if source == "logs":
            return await _lookup_logs_only()
        try:
            return await _lookup_with_db()
        except Exception:
            if source != "auto":
                raise
            return await _lookup_logs_only()

    payload = _run_async(_lookup_auto())
    found = bool(payload.get("operation_logs") or payload.get("log_matches"))

    if output_json:
        _echo_json(payload)
    else:
        click.echo(_render_trace_text(payload))

    sys.exit(0 if found else 1)


def _resolve_codegen_config_json(
    *,
    config_path: str | None,
    config_id: int | None,
    resource: str | None,
    stdin: bool = False,
    output_json: bool = False,
    error_message: str,
) -> dict:
    """Resolve codegen config from stdin/file/db / 从 stdin、文件或数据库解析 codegen 配置."""
    config_json = None
    if stdin:
        config_json = _load_config_stdin()
    elif config_path:
        config_json = _load_config_from_file(config_path)
    elif config_id is not None or resource:
        from app.core.database import get_db_context
        from app.services.system.codegen_service import CodegenService

        async def _do():
            async with get_db_context() as db:
                svc = CodegenService(db)
                if config_id is not None:
                    cfg = await svc.get_by_id(config_id)
                else:
                    cfg = await svc.get_by_resource(resource)
                if not cfg:
                    raise SystemExit("Config not found")
                return cfg.config_json or {}

        try:
            config_json = _run_quietly(output_json, _run_async, _do())
        except SystemExit as e:
            if output_json:
                _echo_json(_json_error(str(e), code="config_not_found"))
                sys.exit(1)
            raise

    if config_json:
        return config_json

    if output_json:
        _echo_json(_json_error(error_message, code="missing_config_source"))
    else:
        click.echo(f"Error: {error_message}", err=True)
    sys.exit(1)


@cli.group("codegen", help="CRUD code generation / 代码生成器")
def codegen_cmd() -> None:
    pass


# ----- 核心命令 -----


@codegen_cmd.command("generate")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True),
    help="YAML config file path",
)
@click.option(
    "--id", "config_id", type=int, default=None, help="Config ID (from database)"
)
@click.option(
    "--resource", "-r", default=None, help="Resource name (resolve config from DB)"
)
@click.option(
    "--stdin",
    is_flag=True,
    help="Read config from stdin (priority: stdin > config > id/resource)",
)
@click.option("--force", "-f", is_flag=True, help="Force overwrite existing files")
@click.option(
    "--auto-migrate/--no-auto-migrate",
    default=True,
    help="Run alembic autogenerate after generate (default: on)",
)
@click.option("--dry-run", is_flag=True, help="Preview only, do not write files")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def codegen_generate(
    config_path: str | None,
    config_id: int | None,
    resource: str | None,
    force: bool,
    auto_migrate: bool,
    dry_run: bool,
    stdin: bool,
    output_json: bool,
) -> None:
    """Generate CRUD code. Config source priority: --stdin > --config > --id/--resource. / 生成 CRUD 代码。配置来源优先级：stdin > config > id/resource"""
    os.chdir(_BACKEND_DIR)

    config_json = _resolve_codegen_config_json(
        config_path=config_path,
        config_id=config_id,
        resource=resource,
        stdin=stdin,
        output_json=output_json,
        error_message="Provide --config, --id, --resource, or --stdin",
    )

    if dry_run:
        from app.services.system.codegen_service import CodegenService

        svc = CodegenService.create_standalone()
        result = svc.preview(config_json, project_root=_CODEGEN_PROJECT_ROOT)
        if output_json:
            _echo_json(_json_success(result))
        else:
            for f in result.get("files", []):
                click.echo("  {} ({})".format(f.get("path", ""), f.get("type", "")))
            if result.get("conflicts"):
                click.echo(
                    "Conflicts: {}".format([c.get("path") for c in result["conflicts"]])
                )
        return

    from filelock import FileLock, Timeout

    from app.core.database import get_db_context
    from app.enums.codegen import CodegenConfigStatusEnum
    from app.services.system.codegen_service import CodegenService

    _lock_dir = _CODEGEN_PROJECT_ROOT / ".codegen_locks"
    _lock_dir.mkdir(parents=True, exist_ok=True)
    _codegen_lock = FileLock(_lock_dir / "_codegen_global.lock", timeout=60)
    try:
        _codegen_lock.acquire()
    except Timeout:
        click.echo(
            "Error: Another codegen operation is in progress (lock timeout).", err=True
        )
        sys.exit(1)

    use_config_id = config_id is not None or resource is not None

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            if use_config_id:
                if config_id is not None:
                    inp = config_id
                else:
                    cfg = await svc.get_by_resource(resource)
                    if not cfg:
                        raise SystemExit(
                            "Config not found for resource: {}".format(resource)
                        )
                    inp = cfg.id
            else:
                inp = config_json
            output = await svc.generate(
                inp, force=force, project_root=_CODEGEN_PROJECT_ROOT
            )
            return output

    try:
        json_payload: dict | None = None
        try:
            output = _run_quietly(output_json, _run_async, _do())
            result = output.result
            if output_json:
                json_payload = {
                    "files_created": result.files_created,
                    "files_modified": result.files_modified,
                    "errors": result.errors,
                    "resource": getattr(output, "resource", None),
                    "module": getattr(output, "module", None),
                    "table_name": getattr(output, "table_name", None),
                    "config_id": getattr(output, "config_id", None),
                }
                if not result.success:
                    _echo_json(
                        _json_error(
                            "; ".join(result.errors)
                            if result.errors
                            else "Generation failed",
                            code="generation_failed",
                            data=json_payload,
                        )
                    )
                    sys.exit(1)
            elif result.success:
                click.echo("[{}] Generated successfully".format(_STATUS_OK))
                for p in result.files_created:
                    click.echo("  + {}".format(p))
                for p in result.files_modified:
                    click.echo("  ~ {}".format(p))
            else:
                if output_json:
                    _echo_json(
                        _json_error(
                            "; ".join(result.errors)
                            if result.errors
                            else "Generation failed",
                            code="generation_failed",
                            data={
                                "errors": result.errors,
                                "files_created": result.files_created,
                                "files_modified": result.files_modified,
                            },
                        )
                    )
                else:
                    for e in result.errors:
                        click.echo("Error: {}".format(e), err=True)
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as e:
            if output_json:
                _echo_json(_json_error(str(e), code="generate_exception"))
            else:
                click.echo("Error: {}".format(e), err=True)
            sys.exit(1)

        if auto_migrate and result.success and output.resource:
            from app.codegen.manifest import ManifestManager

            _resource = output.resource
            mig_result = _run_quietly(
                output_json,
                CodegenService.run_auto_migrate,
                _resource,
                _CODEGEN_PROJECT_ROOT,
            )
            if mig_result.get("success"):
                if output_json:
                    assert json_payload is not None
                    json_payload["auto_migrate"] = mig_result
                else:
                    click.echo("[auto-migrate] " + str(mig_result.get("message", "OK")))
                if _resource and mig_result.get("migration_path"):
                    manifest = ManifestManager(_CODEGEN_PROJECT_ROOT)
                    manifest.update_migration_file(
                        _resource, mig_result["migration_path"]
                    )
                if output.config_id is not None:

                    async def _mark_applied():
                        async with get_db_context() as db:
                            svc = CodegenService(db)
                            await svc.update(
                                output.config_id,
                                {
                                    "status": CodegenConfigStatusEnum.APPLIED.value,
                                    "last_error": None,
                                },
                            )

                    _run_quietly(output_json, _run_async, _mark_applied())
            else:
                err_msg = "auto_migrate failed (phase={}): {}".format(
                    mig_result.get("phase", "unknown"),
                    mig_result.get("error", "unknown error"),
                )
                if output.config_id is not None:

                    async def _mark_generate_failed():
                        async with get_db_context() as db:
                            svc = CodegenService(db)
                            await svc.update(
                                output.config_id,
                                {
                                    "status": CodegenConfigStatusEnum.GENERATED.value,
                                    "last_error": (
                                        f"auto_migrate failed at {mig_result.get('phase', 'unknown')}: "
                                        f"{mig_result.get('error', 'unknown error')}"
                                    ),
                                },
                            )

                    _run_quietly(output_json, _run_async, _mark_generate_failed())
                if output_json:
                    assert json_payload is not None
                    json_payload["auto_migrate"] = mig_result
                    _echo_json(
                        _json_error(
                            err_msg, code="auto_migrate_failed", data=json_payload
                        )
                    )
                else:
                    click.echo(
                        "[auto-migrate] Failed (phase={}): {}".format(
                            mig_result.get("phase", "unknown"),
                            mig_result.get("error", "unknown error"),
                        ),
                        err=True,
                    )
                sys.exit(1)
        if output_json and json_payload is not None:
            _echo_json(_json_success(json_payload))
    finally:
        _codegen_lock.release()


@codegen_cmd.command("preview")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True))
@click.option("--id", "config_id", type=int, default=None)
@click.option(
    "--resource", "-r", default=None, help="Load config by resource name from DB"
)
@click.option("--stdin", is_flag=True, help="Read config from stdin")
@click.option(
    "--step",
    "-s",
    type=click.Choice(["model", "controller", "frontend"]),
    default=None,
    help="Partial preview: model | controller | frontend",
)
@click.option("--verbose", "-v", is_flag=True, help="Output full file content")
@click.option("--json", "output_json", is_flag=True)
def codegen_preview(
    config_path: str | None,
    config_id: int | None,
    resource: str | None,
    stdin: bool,
    step: str | None,
    verbose: bool,
    output_json: bool,
) -> None:
    """Preview generation (no write) / 预览生成（不写入）"""
    os.chdir(_BACKEND_DIR)

    config_json = _resolve_codegen_config_json(
        config_path=config_path,
        config_id=config_id,
        resource=resource,
        stdin=stdin,
        output_json=output_json,
        error_message="Provide --config, --id, --resource, or --stdin",
    )

    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    result = svc.preview(config_json, step=step, project_root=_CODEGEN_PROJECT_ROOT)

    if output_json:
        if not verbose:
            for f in result.get("files", []):
                f.pop("content", None)
                f.pop("original_content", None)
                f.pop("new_content", None)
        _echo_json(_json_success(result))
    else:
        for f in result.get("files", []):
            line = "  {} ({}): {} lines".format(
                f.get("path", ""), f.get("type", ""), f.get("line_count", 0)
            )
            click.echo(line)
            if verbose and f.get("content"):
                click.echo("    ---")
                for ln in f["content"].split("\n")[:20]:
                    click.echo("    {}".format(ln))
                if f["content"].count("\n") >= 20:
                    click.echo("    ...")
        conflicts = result.get("conflicts") or []
        if conflicts:
            click.echo("")
            click.echo("Conflicts (file exists):")
            for c in conflicts:
                click.echo("  ! {}".format(c.get("path", "")))


@codegen_cmd.command("validate")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True))
@click.option("--stdin", is_flag=True, help="Read config from stdin")
@click.option(
    "--mode",
    type=click.Choice(["draft", "generate"]),
    default="generate",
    help="Validation mode",
)
@click.option("--json", "output_json", is_flag=True)
def codegen_validate(
    config_path: str | None, stdin: bool, mode: str, output_json: bool
) -> None:
    """Validate config / 校验配置"""
    os.chdir(_BACKEND_DIR)

    if stdin:
        config_json = _load_config_stdin()
    elif config_path:
        config_json = _load_config_from_file(config_path)
    else:
        click.echo("Error: Provide --config or --stdin", err=True)
        sys.exit(1)
    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    result = svc.validate(config_json, mode=mode)

    if output_json:
        _echo_json(_json_success(result))
    else:
        if result.get("valid"):
            click.echo("[{}] Config is valid".format(_STATUS_OK))
        else:
            for e in result.get("errors", []):
                click.echo("Error: {}".format(e.get("message", e)), err=True)
            sys.exit(1)


@codegen_cmd.command("rollback")
@click.option("--resource", "-r", default=None)
@click.option("--id", "config_id", type=int, default=None)
@click.option("--force", "-f", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option(
    "--auto-migrate/--no-auto-migrate",
    default=True,
    help="Run alembic downgrade and delete migration file (default: on)",
)
@click.option("--json", "output_json", is_flag=True)
def codegen_rollback(
    resource: str | None,
    config_id: int | None,
    force: bool,
    dry_run: bool,
    auto_migrate: bool,
    output_json: bool,
) -> None:
    """Rollback generated code / 回滚生成代码"""
    os.chdir(_BACKEND_DIR)

    if not resource and config_id is None:
        click.echo("Error: Provide --resource or --id", err=True)
        sys.exit(1)
    if resource and config_id is not None:
        click.echo("Error: Use --resource OR --id, not both", err=True)
        sys.exit(1)

    from filelock import FileLock, Timeout

    from app.codegen.rollback import CodegenRollback
    from app.codegen.manifest import ManifestManager
    from app.codegen.migration_helper import run_rollback_migration_cleanup
    from app.core.database import get_db_context
    from app.core.i18n import _
    from app.enums.codegen import CodegenConfigStatusEnum
    from app.services.system.codegen_service import CodegenService

    _lock_dir = _CODEGEN_PROJECT_ROOT / ".codegen_locks"
    _lock_dir.mkdir(parents=True, exist_ok=True)
    _rb_lock = FileLock(_lock_dir / "_codegen_global.lock", timeout=60)
    try:
        _rb_lock.acquire()
    except Timeout:
        click.echo(
            "Error: Another codegen operation is in progress (lock timeout).", err=True
        )
        sys.exit(1)

    try:
        manifest = ManifestManager(_CODEGEN_PROJECT_ROOT)
        entry = None
        if resource:
            entry = manifest.get_entry(resource)
        elif config_id is not None:
            for e in manifest.list_entries():
                if e.config_id == config_id:
                    entry = e
                    break
        migration_file = entry.migration_file if entry else None
        _resource = resource or (entry.resource if entry else None)

        rb = CodegenRollback(_CODEGEN_PROJECT_ROOT)
        result = rb.rollback(
            resource=resource,
            config_id=config_id,
            force=force,
            dry_run=dry_run,
        )
        _migration_cleaned = False

        if auto_migrate and not dry_run and result.success and _resource:
            click.echo("[auto-migrate] Running downgrade and dropping table ...")
            _migration_cleaned = run_rollback_migration_cleanup(
                resource=_resource or "",
                migration_file=migration_file,
                project_root=_CODEGEN_PROJECT_ROOT,
                backend_dir=Path(__file__).parent.parent,
                force_drop=force,
            )
            if _migration_cleaned:
                click.echo("[auto-migrate] Migration cleaned and table dropped")

        overall_success = result.success
        errors = list(result.errors)
        cleanup_pending = False
        if auto_migrate and not dry_run and result.success and _resource:
            if _migration_cleaned:
                manifest.remove_entry(_resource)

                async def _mark_rolled_back():
                    async with get_db_context() as db:
                        svc = CodegenService(db)
                        cfg = await svc.get_by_resource(_resource)
                        if cfg:
                            await svc.update(
                                cfg.id,
                                {
                                    "status": CodegenConfigStatusEnum.ROLLED_BACK.value,
                                    "generated_files": None,
                                    "last_error": None,
                                },
                            )

                _run_async(_mark_rolled_back())
            else:
                overall_success = False
                rollback_err = _("codegen.rollback.cleanup_failed")
                errors.append(rollback_err)

                async def _mark_rollback_failed():
                    async with get_db_context() as db:
                        svc = CodegenService(db)
                        cfg = await svc.get_by_resource(_resource)
                        if cfg:
                            await svc.update(cfg.id, {"last_error": rollback_err})

                _run_async(_mark_rollback_failed())
        elif not auto_migrate and not dry_run and result.success and _resource:
            overall_success = False
            cleanup_pending = True
            rollback_err = _("codegen.rollback.cleanup_pending")
            errors.append(rollback_err)

            async def _mark_rollback_incomplete():
                async with get_db_context() as db:
                    svc = CodegenService(db)
                    cfg = await svc.get_by_resource(_resource)
                    if cfg:
                        await svc.update(cfg.id, {"last_error": rollback_err})

            _run_async(_mark_rollback_incomplete())

        if output_json:
            import json

            _out = {
                "success": overall_success,
                "files_deleted": result.files_deleted,
                "files_modified": result.files_modified,
                "errors": errors,
            }
            if not dry_run:
                _out["migration_cleaned"] = _migration_cleaned
            if cleanup_pending:
                _out["pending_migration_cleanup"] = True
            click.echo(json.dumps(_out, ensure_ascii=False, indent=2))
            if not overall_success:
                sys.exit(1)
        elif overall_success:
            click.echo("[{}] Rollback completed".format(_STATUS_OK))
            for p in result.files_deleted:
                click.echo("  - {}".format(p))
        elif _migration_cleaned:
            click.echo(
                "[{}] Migration cleanup completed (no manifest entry for file rollback)".format(
                    _STATUS_OK
                )
            )
        else:
            for e in errors:
                click.echo("Error: {}".format(e), err=True)
            sys.exit(1)
    finally:
        _rb_lock.release()


# ----- 配置管理 -----


@codegen_cmd.command("versions")
@click.option("--id", "config_id", required=True, type=int)
@click.option("--limit", "-n", type=int, default=50)
@click.option("--json", "output_json", is_flag=True)
def codegen_versions(config_id: int, limit: int, output_json: bool) -> None:
    """List config version history / 列出配置版本历史"""
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            return await svc.list_versions(config_id, limit=limit)

    items = _run_quietly(output_json, _run_async, _do())

    if output_json:
        _echo_json(_json_success({"versions": items}))
    else:
        for v in items:
            click.echo(
                "  {:>5}  {}  {}".format(
                    v.get("id", ""), (v.get("created_at") or "")[:19], v.get("note", "")
                )
            )


@codegen_cmd.command("restore")
@click.option("--id", "config_id", required=True, type=int)
@click.option("--version", "-v", "version_id", required=True, type=int)
@click.option("--json", "output_json", is_flag=True)
def codegen_restore(config_id: int, version_id: int, output_json: bool) -> None:
    """Restore config to a version / 恢复到指定版本"""
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            return await svc.restore_version(config_id, version_id)

    try:
        obj = _run_quietly(output_json, _run_async, _do())
        if not obj:
            if output_json:
                _echo_json(_json_error("Version not found", code="version_not_found"))
            else:
                click.echo("Error: Version not found", err=True)
            sys.exit(1)
        if output_json:
            _echo_json(_json_success({"message": "Restored"}))
        else:
            click.echo(
                "[{}] Restored config id={} to version {}".format(
                    _STATUS_OK, config_id, version_id
                )
            )
    except Exception as e:
        if output_json:
            _echo_json(_json_error(str(e), code="restore_failed"))
        else:
            click.echo("Error: {}".format(e), err=True)
        sys.exit(1)


@codegen_cmd.command("list")
@click.option("--status", "-s", default=None)
@click.option("--json", "output_json", is_flag=True)
def codegen_list(status: str | None, output_json: bool) -> None:
    """List configs / 列出配置"""
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            if status:
                items = await svc.get_by_status(status)
            else:
                items = await svc.get_list(limit=1000)
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "resource": c.resource,
                    "module": c.module,
                    "display_name": c.display_name,
                    "display_name_en": c.display_name_en,
                    "status": c.status,
                    "generation_count": c.generation_count,
                    "last_generated_at": c.last_generated_at.isoformat()
                    if c.last_generated_at
                    else None,
                }
                for c in items
            ]

    items = _run_quietly(output_json, _run_async, _do())

    if output_json:
        _echo_json(_json_success({"items": items}))
    else:
        for c in items:
            click.echo(
                "  {:>5}  {:20}  {:15}  {}".format(
                    c["id"], c["name"], c["resource"], c["status"]
                )
            )


@codegen_cmd.command("show")
@click.option("--id", "config_id", type=int, default=None)
@click.option("--resource", "-r", default=None)
@click.option("--json", "output_json", is_flag=True)
def codegen_show(
    config_id: int | None, resource: str | None, output_json: bool
) -> None:
    """Show config detail / 显示配置详情"""
    os.chdir(_BACKEND_DIR)

    if config_id is None and not resource:
        if output_json:
            _echo_json(
                _json_error(
                    "Provide --id or --resource", code="missing_config_selector"
                )
            )
        else:
            click.echo("Error: Provide --id or --resource", err=True)
        sys.exit(1)
    if config_id is not None and resource:
        if output_json:
            _echo_json(
                _json_error("Use --id OR --resource, not both", code="invalid_selector")
            )
        else:
            click.echo("Error: Use --id OR --resource, not both", err=True)
        sys.exit(1)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            cfg = await (
                svc.get_by_id(config_id)
                if config_id is not None
                else svc.get_by_resource(resource)
            )
            if not cfg:
                return None
            return {
                "id": cfg.id,
                "name": cfg.name,
                "resource": cfg.resource,
                "module": cfg.module,
                "status": cfg.status,
                "config_json": cfg.config_json,
            }

    data = _run_quietly(output_json, _run_async, _do())
    if not data:
        if output_json:
            _echo_json(_json_error("Config not found", code="config_not_found"))
        else:
            click.echo("Config not found", err=True)
        sys.exit(1)

    if output_json:
        _echo_json(_json_success(data))
    else:
        click.echo("ID: {}".format(data["id"]))
        click.echo("Name: {}".format(data["name"]))
        click.echo("Resource: {}".format(data["resource"]))


@codegen_cmd.command("import")
@click.option(
    "--config", "-c", "config_path", required=True, type=click.Path(exists=True)
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON only (id)")
def codegen_import_cmd(config_path: str, output_json: bool) -> None:
    """Import YAML config to database / 导入 YAML 配置到数据库"""
    os.chdir(_BACKEND_DIR)

    config_json = _load_config_from_file(config_path)
    name = config_json.get("display_name") or config_json.get("resource", "imported")
    resource = config_json.get("resource", "unknown")
    module = config_json.get("module", "system")
    display_name = config_json.get("display_name", name)
    display_name_en = config_json.get("display_name_en", resource)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            cfg = await svc.create(
                {
                    "name": name,
                    "resource": resource,
                    "module": module,
                    "display_name": display_name,
                    "display_name_en": display_name_en,
                    "config_json": config_json,
                }
            )
            return cfg.id

    cid = _run_quietly(output_json, _run_async, _do())
    if output_json:
        _echo_json(_json_success({"id": cid}))
    else:
        click.echo("Imported as config id={}".format(cid))


@codegen_cmd.command("export")
@click.option("--id", "config_id", type=int, default=None)
@click.option("--resource", "-r", default=None)
@click.option("--output", "-o", type=click.Path(), default=None)
def codegen_export(
    config_id: int | None, resource: str | None, output: str | None
) -> None:
    """Export config to YAML / 导出配置为 YAML"""
    os.chdir(_BACKEND_DIR)

    if not config_id and not resource:
        click.echo("Error: Provide --id or --resource", err=True)
        sys.exit(1)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            if config_id:
                cfg = await svc.get_by_id(config_id)
            else:
                cfg = await svc.get_by_resource(resource)
            if not cfg:
                return None
            return cfg.config_json

    config_json = _run_async(_do())
    if not config_json:
        click.echo("Config not found", err=True)
        sys.exit(1)

    import yaml

    out = yaml.dump(
        config_json, allow_unicode=True, default_flow_style=False, sort_keys=False
    )
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(out)
        click.echo("Exported to {}".format(output))
    else:
        click.echo(out)


@codegen_cmd.command("delete")
@click.option("--id", "config_id", required=True, type=int)
@click.option(
    "--yes", "-y", "skip_confirm", is_flag=True, help="Skip confirmation prompt"
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON only")
def codegen_delete(config_id: int, skip_confirm: bool, output_json: bool) -> None:
    """Delete config / 删除配置"""
    if not skip_confirm and not click.confirm(
        "Delete codegen config id={}?".format(config_id)
    ):
        return
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.exceptions import AppException
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            await svc.assert_can_delete(config_id, project_root=_CODEGEN_PROJECT_ROOT)
            await svc.delete(config_id)

    try:
        _run_quietly(output_json, _run_async, _do())
    except AppException as e:
        reason_code = e.data.get("reason_code") if isinstance(e.data, dict) else None
        if output_json:
            _echo_json(
                _json_error(
                    e.message,
                    code="delete_blocked",
                    data=e.data if isinstance(e.data, dict) else None,
                )
            )
        else:
            click.echo("Error: {}".format(e.message), err=True)
            hint = _codegen_delete_hint(reason_code, config_id)
            if hint:
                click.echo(hint, err=True)
        sys.exit(1)
    if output_json:
        _echo_json(_json_success({"deleted_id": config_id}))
    else:
        click.echo("Deleted config id={}".format(config_id))


@codegen_cmd.command("duplicate")
@click.option("--id", "config_id", required=True, type=int)
@click.option("--json", "output_json", is_flag=True, help="Output JSON only (id)")
def codegen_duplicate(config_id: int, output_json: bool) -> None:
    """Duplicate config / 复制配置"""
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.exceptions import AppException
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            cfg = await svc.duplicate(config_id)
            return {"id": cfg.id, "resource": cfg.resource, "name": cfg.name}

    try:
        payload = _run_quietly(output_json, _run_async, _do())
    except AppException as e:
        if output_json:
            _echo_json(_json_error(e.message, code="duplicate_failed"))
        else:
            click.echo("Error: {}".format(e.message), err=True)
        sys.exit(1)
    if output_json:
        _echo_json(_json_success(payload))
    else:
        click.echo("Duplicated as config id={}".format(payload["id"]))


# ----- DB 反射 -----


@codegen_cmd.group("db", help="DB introspection")
def codegen_db_cmd() -> None:
    pass


@codegen_db_cmd.command("tables")
@click.option("--json", "output_json", is_flag=True)
def codegen_db_tables(output_json: bool) -> None:
    """List DB tables / 列出数据库表"""
    os.chdir(_BACKEND_DIR)

    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    items = _run_quietly(output_json, svc.introspect_tables)

    if output_json:
        _echo_json(_json_success({"items": items}))
    else:
        for t in items:
            click.echo(
                "  {}  (has_model: {})".format(t["name"], t.get("has_model", False))
            )


@codegen_db_cmd.command("columns")
@click.option("--table", "-t", required=True)
@click.option("--json", "output_json", is_flag=True)
def codegen_db_columns(table: str, output_json: bool) -> None:
    """Get table columns / 获取表列定义"""
    os.chdir(_BACKEND_DIR)

    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    items = _run_quietly(output_json, svc.introspect_columns, table)

    if output_json:
        _echo_json(_json_success({"items": items}))
    else:
        for c in items:
            click.echo(
                "  {}  {}  nullable={}".format(c["name"], c["type"], c["nullable"])
            )


@codegen_db_cmd.command("import")
@click.option("--table", "-t", required=True)
@click.option("--output", "-o", type=click.Path(), default=None)
def codegen_db_import(table: str, output: str | None) -> None:
    """Import from table to YAML / 从表导入为 YAML"""
    os.chdir(_BACKEND_DIR)

    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    data = svc.import_from_table(table)

    import yaml

    out = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(out)
        click.echo("Exported to {}".format(output))
    else:
        click.echo(out)


# ----- 辅助 -----


@codegen_cmd.group("presets", help="Preset discovery / 预设发现")
def codegen_presets_cmd() -> None:
    pass


@codegen_presets_cmd.command("list")
@click.option("--json", "output_json", is_flag=True)
def codegen_presets_list(output_json: bool) -> None:
    """List available presets / 列出可用预设."""
    from app.codegen.preset_loader import list_presets

    items = list_presets()
    if output_json:
        _echo_json(_json_success({"items": items}))
    else:
        for item in items:
            click.echo(
                "  {name:20}  {category:12}  {label}".format(
                    name=item.get("name", ""),
                    category=item.get("category", ""),
                    label=item.get("label_en")
                    or item.get("label_zh")
                    or item.get("name", ""),
                )
            )


@codegen_presets_cmd.command("show")
@click.option("--name", "preset_name", required=True)
@click.option("--json", "output_json", is_flag=True)
def codegen_presets_show(preset_name: str, output_json: bool) -> None:
    """Show a preset / 查看单个预设."""
    from app.codegen.preset_loader import get_preset

    preset = get_preset(preset_name)
    if not preset:
        if output_json:
            _echo_json(_json_error("Preset not found", code="preset_not_found"))
        else:
            click.echo("Preset not found", err=True)
        sys.exit(1)
    if output_json:
        _echo_json(_json_success(preset))
    else:
        click.echo(preset["content"])


@codegen_cmd.command("init")
@click.option("--template", "-t", default="simple")
@click.option("--output", "-o", type=click.Path(), default=None)
def codegen_init(template: str, output: str | None) -> None:
    """Init from template / 从模板初始化配置"""
    os.chdir(_BACKEND_DIR)

    from app.codegen.preset_loader import get_preset

    preset = get_preset(template)
    if not preset:
        click.echo("Template not found: {}".format(template), err=True)
        sys.exit(1)

    content = str(preset["content"])
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        click.echo("Initialized: {}".format(output))
    else:
        click.echo(content)


@codegen_cmd.command("history")
@click.option("--resource", "-r", default=None)
@click.option("--json", "output_json", is_flag=True)
def codegen_history(resource: str | None, output_json: bool) -> None:
    """Show generation history / 显示生成历史"""
    os.chdir(_BACKEND_DIR)

    from app.codegen.manifest import ManifestManager

    manifest = ManifestManager(_CODEGEN_PROJECT_ROOT)
    entries = manifest.list_entries()
    if resource:
        entries = [e for e in entries if e.resource == resource]

    if output_json:
        data = [
            {
                "resource": e.resource,
                "module": e.module,
                "config_id": e.config_id,
                "generated_at": e.generated_at,
            }
            for e in entries
        ]
        _echo_json(_json_success({"entries": data}))
    else:
        for e in entries:
            click.echo(
                "  {}  {}  config_id={}  {}".format(
                    e.resource, e.module, e.config_id, e.generated_at
                )
            )


@codegen_cmd.command("download")
@click.option("--id", "config_id", type=int, default=None)
@click.option("--resource", "-r", default=None)
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), default=None
)
@click.option("--stdin", is_flag=True, help="Read config from stdin")
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--json", "output_json", is_flag=True)
def codegen_download(
    config_id: int | None,
    resource: str | None,
    config_path: str | None,
    stdin: bool,
    output: str,
    output_json: bool,
) -> None:
    """Download generated code as ZIP / 下载生成代码为 ZIP"""
    os.chdir(_BACKEND_DIR)

    zip_bytes = None
    if (
        sum(
            [
                1 if config_id is not None else 0,
                1 if resource else 0,
                1 if config_path else 0,
                1 if stdin else 0,
            ]
        )
        != 1
    ):
        if output_json:
            _echo_json(
                _json_error(
                    "Provide exactly one of --id, --resource, --config, or --stdin",
                    code="invalid_source_selector",
                )
            )
        else:
            click.echo(
                "Error: Provide exactly one of --id, --resource, --config, or --stdin",
                err=True,
            )
        sys.exit(1)

    if config_id is not None or resource:
        from app.core.database import get_db_context
        from app.exceptions import AppException
        from app.services.system.codegen_service import CodegenService

        async def _do():
            async with get_db_context() as db:
                svc = CodegenService(db)
                cfg = await (
                    svc.get_by_id(config_id)
                    if config_id is not None
                    else svc.get_by_resource(resource)
                )
                if not cfg:
                    raise SystemExit("Config not found")
                return await svc.download(cfg.id, project_root=_CODEGEN_PROJECT_ROOT)

        try:
            zip_bytes = _run_quietly(output_json, _run_async, _do())
        except SystemExit as e:
            if output_json:
                _echo_json(_json_error(str(e), code="config_not_found"))
            else:
                click.echo(str(e), err=True)
            sys.exit(1)
        except AppException as e:
            if output_json:
                _echo_json(
                    _json_error(
                        e.message,
                        code="download_failed",
                        data=e.data if isinstance(e.data, dict) else None,
                    )
                )
            else:
                click.echo("Error: {}".format(e.message), err=True)
            sys.exit(1)
    elif config_path:
        config_json = _load_config_from_file(config_path)
        from app.services.system.codegen_service import CodegenService

        svc = CodegenService.create_standalone()
        zip_bytes = svc.preview_zip(config_json)
    elif stdin:
        config_json = _load_config_stdin()
        from app.services.system.codegen_service import CodegenService

        svc = CodegenService.create_standalone()
        zip_bytes = svc.preview_zip(config_json)
    else:
        if output_json:
            _echo_json(
                _json_error(
                    "Provide --id, --resource, --config, or --stdin",
                    code="missing_config_source",
                )
            )
        else:
            click.echo(
                "Error: Provide --id, --resource, --config, or --stdin", err=True
            )
        sys.exit(1)

    with open(output, "wb") as f:
        f.write(zip_bytes)
    if output_json:
        _echo_json(_json_success({"output": output}))
    else:
        click.echo("Saved to {}".format(output))


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
        status = (
            click.style(_STATUS_OK, fg="green")
            if ok
            else click.style(_STATUS_FAIL, fg="red")
        )
        click.echo("{}: {}".format(name, status))
    failed = sum(1 for _, fn in checks if not fn())
    if failed:
        sys.exit(1)


@check_cmd.command()
def db() -> None:
    """Check database connection / 检查数据库连接"""
    ok = _check_db()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
    click.echo("{}: {}".format(_CHECK_DB, status))
    sys.exit(0 if ok else 1)


@check_cmd.command()
def redis() -> None:
    """Check Redis connection / 检查 Redis 连接"""
    ok = _check_redis()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
    click.echo("{}: {}".format(_CHECK_REDIS, status))
    sys.exit(0 if ok else 1)


@check_cmd.command()
def celery() -> None:
    """Check Celery broker connection / 检查 Celery Broker 连接"""
    ok = _check_celery()
    status = (
        click.style(_STATUS_OK, fg="green")
        if ok
        else click.style(_STATUS_FAIL, fg="red")
    )
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
    click.echo(
        "  Database: {}:{}/{}".format(
            settings.DATABASE_HOST,
            settings.DATABASE_PORT,
            settings.DATABASE_NAME,
        )
    )
    click.echo("  Redis:    {}:{}".format(settings.REDIS_HOST, settings.REDIS_PORT))


if __name__ == "__main__":
    cli()
