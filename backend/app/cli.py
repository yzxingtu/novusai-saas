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
            if not d.is_dir() or d.name.startswith("."):
                continue
            versions = d / "backend" / "migrations" / "versions"
            if versions.is_dir():
                paths.append(str(versions))
    return paths


def _get_alembic_config():
    """Build Alembic config with plugin migration paths injected / 构建含插件迁移路径的 Alembic 配置"""
    from alembic.config import Config

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    merged_paths: list[str] = []
    seen_paths: set[str] = set()

    for path in (cfg.get_version_locations_list() or []) + _discover_plugin_migration_paths():
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


@cli.group("codegen", help="CRUD code generation / 代码生成器")
def codegen_cmd() -> None:
    pass


# ----- 核心命令 -----


@codegen_cmd.command("generate")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="YAML config file path")
@click.option("--id", "config_id", type=int, default=None, help="Config ID (from database)")
@click.option("--resource", "-r", default=None, help="Resource name (resolve config from DB)")
@click.option("--stdin", is_flag=True, help="Read config from stdin (priority: stdin > config > id/resource)")
@click.option("--template-type", "-t", type=click.Choice(["single", "tree", "master-sub"]), default=None, help="Template: single|tree|master-sub")
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
    template_type: str | None,
    force: bool,
    auto_migrate: bool,
    dry_run: bool,
    stdin: bool,
    output_json: bool,
) -> None:
    """Generate CRUD code. Config source priority: --stdin > --config > --id/--resource. / 生成 CRUD 代码。配置来源优先级：stdin > config > id/resource"""
    os.chdir(_BACKEND_DIR)

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
                _echo_json({"success": False, "error": str(e)})
                sys.exit(1)
            raise

    # When template_type specified, merge preset as base (config overrides preset)
    if template_type and config_json:
        preset_map = {"single": "simple", "tree": "tree", "master-sub": "dual_scope"}
        preset_name = preset_map.get(template_type)
        if preset_name:
            preset_path = _BACKEND_DIR / "app" / "codegen" / "templates" / "presets" / "{}.yaml".format(preset_name)
            if preset_path.exists():
                import copy
                preset = _load_config_from_file(str(preset_path))
                merged = copy.deepcopy(preset)
                _deep_merge(merged, config_json)
                config_json = merged

    if not config_json:
        _err = "Provide --config, --id, --resource, or --stdin"
        if output_json:
            import json
            click.echo(json.dumps({"success": False, "error": _err}, ensure_ascii=False, indent=2))
        else:
            click.echo("Error: {}".format(_err), err=True)
        sys.exit(1)

    if dry_run:
        from app.services.system.codegen_service import CodegenService

        svc = CodegenService.create_standalone()
        result = svc.preview(config_json, project_root=_CODEGEN_PROJECT_ROOT)
        if output_json:
            import json
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for f in result.get("files", []):
                click.echo("  {} ({})".format(f.get("path", ""), f.get("type", "")))
            if result.get("conflicts"):
                click.echo("Conflicts: {}".format([c.get("path") for c in result["conflicts"]]))
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
        click.echo("Error: Another codegen operation is in progress (lock timeout).", err=True)
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
                        raise SystemExit("Config not found for resource: {}".format(resource))
                    inp = cfg.id
            else:
                inp = config_json
            output = await svc.generate(inp, force=force, project_root=_CODEGEN_PROJECT_ROOT)
            return output

    try:
        json_result: dict | None = None
        try:
            output = _run_quietly(output_json, _run_async, _do())
            result = output.result
            if output_json:
                json_result = {
                    "success": result.success,
                    "files_created": result.files_created,
                    "files_modified": result.files_modified,
                    "errors": result.errors,
                }
                if not result.success:
                    _echo_json(json_result)
                    sys.exit(1)
            elif result.success:
                click.echo("[{}] Generated successfully".format(_STATUS_OK))
                for p in result.files_created:
                    click.echo("  + {}".format(p))
                for p in result.files_modified:
                    click.echo("  ~ {}".format(p))
            else:
                if output_json:
                    import json
                    click.echo(json.dumps({
                        "success": False,
                        "error": "; ".join(result.errors) if result.errors else "Generation failed",
                        "errors": result.errors,
                        "files_created": result.files_created,
                        "files_modified": result.files_modified,
                    }, ensure_ascii=False, indent=2))
                else:
                    for e in result.errors:
                        click.echo("Error: {}".format(e), err=True)
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as e:
            if output_json:
                import json
                click.echo(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))
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
                    assert json_result is not None
                    json_result["auto_migrate"] = mig_result
                else:
                    click.echo("[auto-migrate] " + str(mig_result.get("message", "OK")))
                if _resource and mig_result.get("migration_path"):
                    manifest = ManifestManager(_CODEGEN_PROJECT_ROOT)
                    manifest.update_migration_file(_resource, mig_result["migration_path"])
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
                    assert json_result is not None
                    json_result["success"] = False
                    json_result["error"] = err_msg
                    json_result["auto_migrate"] = mig_result
                    _echo_json(json_result)
                else:
                    click.echo(
                        "[auto-migrate] Failed (phase={}): {}".format(
                            mig_result.get("phase", "unknown"),
                            mig_result.get("error", "unknown error"),
                        ),
                        err=True,
                    )
                sys.exit(1)
        if output_json and json_result is not None:
            _echo_json(json_result)
    finally:
        _codegen_lock.release()


@codegen_cmd.command("preview")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True))
@click.option("--id", "config_id", type=int, default=None)
@click.option("--resource", "-r", default=None, help="Load config by resource name from DB")
@click.option("--step", "-s", type=click.Choice(["model", "controller", "frontend"]), default=None, help="Partial preview: model | controller | frontend")
@click.option("--verbose", "-v", is_flag=True, help="Output full file content")
@click.option("--json", "output_json", is_flag=True)
def codegen_preview(
    config_path: str | None,
    config_id: int | None,
    resource: str | None,
    step: str | None,
    verbose: bool,
    output_json: bool,
) -> None:
    """Preview generation (no write) / 预览生成（不写入）"""
    os.chdir(_BACKEND_DIR)

    config_json = None
    if config_path:
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
                _echo_json({"success": False, "error": str(e)})
                sys.exit(1)
            raise

    if not config_json:
        _err_msg = "Provide --config, --id, or --resource"
        if output_json:
            import json
            click.echo(json.dumps({"success": False, "error": _err_msg}, ensure_ascii=False, indent=2))
        else:
            click.echo("Error: {}".format(_err_msg), err=True)
        sys.exit(1)

    from app.services.system.codegen_service import CodegenService

    svc = CodegenService.create_standalone()
    result = svc.preview(config_json, step=step, project_root=_CODEGEN_PROJECT_ROOT)

    if output_json:
        import json
        if not verbose:
            for f in result.get("files", []):
                f.pop("content", None)
                f.pop("original_content", None)
                f.pop("new_content", None)
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for f in result.get("files", []):
            line = "  {} ({}): {} lines".format(f.get("path", ""), f.get("type", ""), f.get("line_count", 0))
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
@click.option("--json", "output_json", is_flag=True)
def codegen_validate(config_path: str | None, stdin: bool, output_json: bool) -> None:
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
    result = svc.validate(config_json)

    if output_json:
        import json
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
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
    from app.enums.codegen import CodegenConfigStatusEnum
    from app.services.system.codegen_service import CodegenService

    _lock_dir = _CODEGEN_PROJECT_ROOT / ".codegen_locks"
    _lock_dir.mkdir(parents=True, exist_ok=True)
    _rb_lock = FileLock(_lock_dir / "_codegen_global.lock", timeout=60)
    try:
        _rb_lock.acquire()
    except Timeout:
        click.echo("Error: Another codegen operation is in progress (lock timeout).", err=True)
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
                rollback_err = (
                    "File rollback completed but migration cleanup failed. "
                    "Manifest entry preserved for retry."
                )
                errors.append(rollback_err)

                async def _mark_rollback_failed():
                    async with get_db_context() as db:
                        svc = CodegenService(db)
                        cfg = await svc.get_by_resource(_resource)
                        if cfg:
                            await svc.update(cfg.id, {"last_error": rollback_err})

                _run_async(_mark_rollback_failed())

        if output_json:
            import json
            _out = {"success": overall_success, "files_deleted": result.files_deleted, "files_modified": result.files_modified, "errors": errors}
            if auto_migrate and not dry_run:
                _out["migration_cleaned"] = _migration_cleaned
            click.echo(json.dumps(_out, ensure_ascii=False, indent=2))
        elif overall_success:
            click.echo("[{}] Rollback completed".format(_STATUS_OK))
            for p in result.files_deleted:
                click.echo("  - {}".format(p))
        elif _migration_cleaned:
            click.echo("[{}] Migration cleanup completed (no manifest entry for file rollback)".format(_STATUS_OK))
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
        import json
        click.echo(json.dumps({"versions": items}, ensure_ascii=False, indent=2))
    else:
        for v in items:
            click.echo("  {:>5}  {}  {}".format(v.get("id", ""), (v.get("created_at") or "")[:19], v.get("note", "")))


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
                import json
                click.echo(json.dumps({"success": False, "error": "Version not found"}, ensure_ascii=False, indent=2))
            else:
                click.echo("Error: Version not found", err=True)
            sys.exit(1)
        if output_json:
            import json
            click.echo(json.dumps({"success": True, "message": "Restored"}, ensure_ascii=False, indent=2))
        else:
            click.echo("[{}] Restored config id={} to version {}".format(_STATUS_OK, config_id, version_id))
    except Exception as e:
        if output_json:
            import json
            click.echo(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))
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
            return [{
                "id": c.id,
                "name": c.name,
                "resource": c.resource,
                "module": c.module,
                "display_name": c.display_name,
                "display_name_en": c.display_name_en,
                "status": c.status,
                "generation_count": c.generation_count,
                "last_generated_at": c.last_generated_at.isoformat() if c.last_generated_at else None,
            } for c in items]

    items = _run_quietly(output_json, _run_async, _do())

    if output_json:
        import json
        click.echo(json.dumps({"items": items}, ensure_ascii=False, indent=2))
    else:
        for c in items:
            click.echo("  {:>5}  {:20}  {:15}  {}".format(c["id"], c["name"], c["resource"], c["status"]))


@codegen_cmd.command("show")
@click.option("--id", "config_id", required=True, type=int)
@click.option("--json", "output_json", is_flag=True)
def codegen_show(config_id: int, output_json: bool) -> None:
    """Show config detail / 显示配置详情"""
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            cfg = await svc.get_by_id(config_id)
            if not cfg:
                return None
            return {"id": cfg.id, "name": cfg.name, "resource": cfg.resource, "config_json": cfg.config_json}

    data = _run_quietly(output_json, _run_async, _do())
    if not data:
        if output_json:
            _echo_json({"success": False, "error": "Config not found"})
        else:
            click.echo("Config not found", err=True)
        sys.exit(1)

    if output_json:
        _echo_json(data)
    else:
        click.echo("ID: {}".format(data["id"]))
        click.echo("Name: {}".format(data["name"]))
        click.echo("Resource: {}".format(data["resource"]))


@codegen_cmd.command("import")
@click.option("--config", "-c", "config_path", required=True, type=click.Path(exists=True))
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
            cfg = await svc.create({
                "name": name,
                "resource": resource,
                "module": module,
                "display_name": display_name,
                "display_name_en": display_name_en,
                "config_json": config_json,
            })
            return cfg.id

    cid = _run_quietly(output_json, _run_async, _do())
    if output_json:
        import json
        click.echo(json.dumps({"id": cid}, ensure_ascii=False))
    else:
        click.echo("Imported as config id={}".format(cid))


@codegen_cmd.command("export")
@click.option("--id", "config_id", type=int, default=None)
@click.option("--resource", "-r", default=None)
@click.option("--output", "-o", type=click.Path(), default=None)
def codegen_export(config_id: int | None, resource: str | None, output: str | None) -> None:
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
    out = yaml.dump(config_json, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(out)
        click.echo("Exported to {}".format(output))
    else:
        click.echo(out)


@codegen_cmd.command("delete")
@click.option("--id", "config_id", required=True, type=int)
@click.option("--yes", "-y", "skip_confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "output_json", is_flag=True, help="Output JSON only")
def codegen_delete(config_id: int, skip_confirm: bool, output_json: bool) -> None:
    """Delete config / 删除配置"""
    if not skip_confirm and not click.confirm("Delete codegen config id={}?".format(config_id)):
        return
    os.chdir(_BACKEND_DIR)

    from app.core.database import get_db_context
    from app.exceptions import AppException
    from app.services.system.codegen_service import CodegenService

    async def _do():
        async with get_db_context() as db:
            svc = CodegenService(db)
            await svc.delete(config_id)

    try:
        _run_quietly(output_json, _run_async, _do())
    except AppException as e:
        if output_json:
            import json

            click.echo(
                json.dumps({"success": False, "error": e.message}, ensure_ascii=False)
            )
        else:
            click.echo("Error: {}".format(e.message), err=True)
        sys.exit(1)
    if output_json:
        import json
        click.echo(json.dumps({"success": True, "deleted_id": config_id}, ensure_ascii=False))
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
            return cfg.id

    try:
        new_id = _run_quietly(output_json, _run_async, _do())
    except AppException as e:
        if output_json:
            import json

            click.echo(
                json.dumps({"success": False, "error": e.message}, ensure_ascii=False)
            )
        else:
            click.echo("Error: {}".format(e.message), err=True)
        sys.exit(1)
    if output_json:
        import json
        click.echo(json.dumps({"id": new_id}, ensure_ascii=False))
    else:
        click.echo("Duplicated as config id={}".format(new_id))


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
        import json
        click.echo(json.dumps({"tables": items}, ensure_ascii=False, indent=2))
    else:
        for t in items:
            click.echo("  {}  (has_model: {})".format(t["name"], t.get("has_model", False)))


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
        import json
        click.echo(json.dumps({"columns": items}, ensure_ascii=False, indent=2))
    else:
        for c in items:
            click.echo("  {}  {}  nullable={}".format(c["name"], c["type"], c["nullable"]))


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


@codegen_cmd.command("init")
@click.option("--template", "-t", type=click.Choice(["simple", "tree", "dual_scope", "workflow"]), default="simple")
@click.option("--output", "-o", type=click.Path(), default=None)
def codegen_init(template: str, output: str | None) -> None:
    """Init from template / 从模板初始化配置"""
    os.chdir(_BACKEND_DIR)

    presets_dir = _BACKEND_DIR / "app" / "codegen" / "templates" / "presets"
    path = presets_dir / "{}.yaml".format(template)
    if not path.exists():
        click.echo("Template not found: {}".format(path), err=True)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
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
        import json
        data = [{"resource": e.resource, "module": e.module, "config_id": e.config_id, "generated_at": e.generated_at} for e in entries]
        click.echo(json.dumps({"entries": data}, ensure_ascii=False, indent=2))
    else:
        for e in entries:
            click.echo("  {}  {}  config_id={}  {}".format(e.resource, e.module, e.config_id, e.generated_at))


@codegen_cmd.command("download")
@click.option("--id", "config_id", type=int, default=None)
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None)
@click.option("--output", "-o", type=click.Path(), required=True)
def codegen_download(config_id: int | None, config_path: str | None, output: str) -> None:
    """Download generated code as ZIP / 下载生成代码为 ZIP"""
    os.chdir(_BACKEND_DIR)

    zip_bytes = None
    if config_id is not None:
        from app.core.database import get_db_context
        from app.services.system.codegen_service import CodegenService

        async def _do():
            async with get_db_context() as db:
                svc = CodegenService(db)
                return await svc.download(config_id, project_root=_CODEGEN_PROJECT_ROOT)

        zip_bytes = _run_async(_do())
    elif config_path:
        config_json = _load_config_from_file(config_path)
        from app.services.system.codegen_service import CodegenService

        svc = CodegenService.create_standalone()
        zip_bytes = svc.preview_zip(config_json)
    else:
        click.echo("Error: Provide --id or --config", err=True)
        sys.exit(1)

    with open(output, "wb") as f:
        f.write(zip_bytes)
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
