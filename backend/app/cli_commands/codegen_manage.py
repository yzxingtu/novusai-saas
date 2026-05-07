"""Codegen management and utility commands."""

from __future__ import annotations

import os
import sys

import click

from app.cli_commands import state as S
from app.cli_commands.codegen_core import codegen_cmd

_BACKEND_DIR = S._BACKEND_DIR
_CODEGEN_PROJECT_ROOT = S._CODEGEN_PROJECT_ROOT
_STATUS_OK = S._STATUS_OK
_codegen_delete_hint = S._codegen_delete_hint
_echo_json = S._echo_json
_json_error = S._json_error
_json_success = S._json_success
_load_config_from_file = S._load_config_from_file
_load_config_stdin = S._load_config_stdin
_run_async = S._run_async
_run_quietly = S._run_quietly


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
                f"[{_STATUS_OK}] Restored config id={config_id} to version {version_id}"
            )
    except Exception as e:
        if output_json:
            _echo_json(_json_error(str(e), code="restore_failed"))
        else:
            click.echo(f"Error: {e}", err=True)
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
        click.echo(f"Imported as config id={cid}")


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
        click.echo(f"Exported to {output}")
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
    if not skip_confirm and not click.confirm(f"Delete codegen config id={config_id}?"):
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
            click.echo(f"Error: {e.message}", err=True)
            hint = _codegen_delete_hint(reason_code, config_id)
            if hint:
                click.echo(hint, err=True)
        sys.exit(1)
    if output_json:
        _echo_json(_json_success({"deleted_id": config_id}))
    else:
        click.echo(f"Deleted config id={config_id}")


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
            click.echo(f"Error: {e.message}", err=True)
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
        click.echo(f"Exported to {output}")
    else:
        click.echo(out)


# ----- 辅助 / Utilities -----


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
        click.echo(f"Template not found: {template}", err=True)
        sys.exit(1)

    content = str(preset["content"])
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        click.echo(f"Initialized: {output}")
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
                f"  {e.resource}  {e.module}  config_id={e.config_id}  {e.generated_at}"
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
                click.echo(f"Error: {e.message}", err=True)
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
        click.echo(f"Saved to {output}")
