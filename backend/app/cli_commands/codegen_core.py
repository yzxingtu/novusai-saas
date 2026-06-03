"""Codegen core command domain."""

from __future__ import annotations

import os
import sys

import click

from app.cli_commands import state as S

_BACKEND_DIR = S._BACKEND_DIR
_CODEGEN_PROJECT_ROOT = S._CODEGEN_PROJECT_ROOT
_STATUS_OK = S._STATUS_OK
_echo_json = S._echo_json
_json_error = S._json_error
_json_success = S._json_success
_load_config_from_file = S._load_config_from_file
_load_config_stdin = S._load_config_stdin
_run_async = S._run_async
_run_quietly = S._run_quietly


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


@click.group("codegen", help="CRUD code generation / 代码生成器")
def codegen_cmd() -> None:
    pass


# ----- 核心命令 / Core commands -----


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
                        raise SystemExit(f"Config not found for resource: {resource}")
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
                click.echo(f"[{_STATUS_OK}] Generated successfully")
                for p in result.files_created:
                    click.echo(f"  + {p}")
                for p in result.files_modified:
                    click.echo(f"  ~ {p}")
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
                        click.echo(f"Error: {e}", err=True)
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as e:
            if output_json:
                _echo_json(_json_error(str(e), code="generate_exception"))
            else:
                click.echo(f"Error: {e}", err=True)
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
                    click.echo(f"    {ln}")
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
            click.echo(f"[{_STATUS_OK}] Config is valid")
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

    from app.codegen.manifest import ManifestManager
    from app.codegen.migration_helper import run_rollback_migration_cleanup
    from app.codegen.rollback import CodegenRollback
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
                backend_dir=_BACKEND_DIR,
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
            click.echo(f"[{_STATUS_OK}] Rollback completed")
            for p in result.files_deleted:
                click.echo(f"  - {p}")
        elif _migration_cleaned:
            click.echo(
                f"[{_STATUS_OK}] Migration cleanup completed (no manifest entry for file rollback)"
            )
        else:
            for e in errors:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    finally:
        _rb_lock.release()


# ----- 配置管理 / Configuration -----
