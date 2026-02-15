"""
CRUD Generator — CLI 命令行工具

支持从终端直接调用代码生成，无需启动 Web 服务。

用法::

    python -m app.codegen.cli --help
    python -m app.codegen.cli generate -c config.json
    python -m app.codegen.cli preview -c config.json
    python -m app.codegen.cli batch -c project.json
    python -m app.codegen.cli validate -c config.json
    python -m app.codegen.cli init -o my_module.json
    python -m app.codegen.cli rollback --record-id 42
    python -m app.codegen.cli delete -c config.json
    python -m app.codegen.cli list-records
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

# Project root: 4 levels up from this file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================
# Helpers
# ============================================================

def _load_config_file(path: str) -> dict:
    """Load a JSON or YAML config file."""
    p = Path(path)
    if not p.exists():
        raise click.BadParameter(f"Config file not found: {path}")

    content = p.read_text(encoding="utf-8")

    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            raise click.UsageError("PyYAML is required for YAML config files: pip install pyyaml")
    else:
        return json.loads(content)


def _track_record_sync(
    config: object,
    files: dict[str, str],
    operation_type: str,
    write_result: dict | None = None,
    duration_ms: int = 0,
    verbose: bool = False,
) -> None:
    """Best-effort sync wrapper for async track_generation. Silently skips on failure."""
    try:
        import asyncio
        from app.codegen.record_tracker import track_generation
        from app.core.database import get_db_context

        async def _track() -> int | None:
            async with get_db_context() as db:
                return await track_generation(
                    db,
                    config=config,  # type: ignore[arg-type]
                    files=files,
                    operation_type=operation_type,
                    operator_name="CLI",
                    write_result=write_result,
                    duration_ms=duration_ms,
                )

        record_id = asyncio.run(_track())
        if verbose and record_id:
            click.echo(f"  Record: #{record_id}")
    except Exception as exc:
        if verbose:
            click.secho(f"  ⚠ Record tracking failed: {exc}", fg="yellow")


def _print_json(data: dict, compact: bool = False) -> None:
    """Pretty-print JSON to stdout."""
    indent = None if compact else 2
    click.echo(json.dumps(data, ensure_ascii=False, indent=indent, default=str))


def _print_table(rows: list[dict], columns: list[str]) -> None:
    """Print a simple ASCII table."""
    if not rows:
        click.echo("(no data)")
        return

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    # Header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    sep = "-+-".join("-" * widths[col] for col in columns)
    click.echo(header)
    click.echo(sep)

    # Rows
    for row in rows:
        line = " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        click.echo(line)


# ============================================================
# CLI Group
# ============================================================

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default=None,
    help="Override project root directory (default: auto-detected).",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table", "text"]),
    default="text",
    help="Output format (default: text).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, output_dir: str | None, output_format: str) -> None:
    """CRUD Generator CLI — Generate full-stack CRUD code from config files.

    \b
    Commands:
      generate       Generate code from a single-table config and write to disk
      preview        Preview generated files without writing
      batch          Batch generate from a multi-table project config
      validate       Validate a config file
      init           Create a config file template interactively
      rollback       Rollback a previous generation by record ID
      delete         Delete generated files for a config
      list-records   Show generation history
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["output_dir"] = output_dir or str(_PROJECT_ROOT)
    ctx.obj["format"] = output_format


# ============================================================
# generate — Single-table generation
# ============================================================

@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to CrudConfig JSON/YAML file.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview only, do not write files.")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option(
    "--conflict", "conflict_action",
    type=click.Choice(["skip", "overwrite", "merge"]),
    default="skip",
    help="Conflict resolution strategy (default: skip).",
)
@click.pass_context
def generate(ctx: click.Context, config: str, dry_run: bool, force: bool, conflict_action: str) -> None:
    """Generate code from a single-table CrudConfig and write to disk."""
    from app.codegen.generator import CrudGenerator
    from app.codegen.schemas import CrudConfig
    from app.codegen.writer import ConflictAction, CrudWriter

    verbose = ctx.obj["verbose"]
    root = ctx.obj["output_dir"]

    config_data = _load_config_file(config)
    crud_config = CrudConfig(**config_data)

    if verbose:
        click.echo(f"Module: {crud_config.module}")
        click.echo(f"Table: {crud_config.table_name}")
        click.echo(f"Scope: {crud_config.scope}")
        click.echo(f"Fields: {len(crud_config.fields)}")

    gen = CrudGenerator()
    files = gen.generate(crud_config)

    writer = CrudWriter(root)

    if dry_run:
        preview_result = writer.preview(files, include_content=False)
        click.echo(f"\n  Preview: {len(preview_result['files'])} files")
        click.echo(f"  New: {preview_result['total_new']}, Conflicts: {preview_result['total_conflict']}\n")
        for f in preview_result["files"]:
            op = f.get("operation", "create").upper()
            click.echo(f"  [{op}] {f['path']}")
        return

    # Show preview first
    preview_result = writer.preview(files, include_content=False)
    click.echo(f"\n  Will generate {len(preview_result['files'])} files")
    click.echo(f"  New: {preview_result['total_new']}, Conflicts: {preview_result['total_conflict']}\n")

    if not force:
        click.confirm("  Proceed with file generation?", abort=True)

    action = ConflictAction(conflict_action)

    import time as _time
    start = _time.perf_counter()
    result = writer.write(files, conflict_action=action)
    duration_ms = int((_time.perf_counter() - start) * 1000)

    click.echo(f"\n  Written: {len(result.written)}")
    click.echo(f"  Skipped: {len(result.skipped)}")
    click.echo(f"  Merged:  {len(result.merged)}")
    if result.errors:
        click.echo(f"  Errors:  {len(result.errors)}")
        for err in result.errors:
            click.secho(f"    ✗ {err}", fg="red")

    # Track generation record (async, best-effort)
    _track_record_sync(
        config=crud_config,
        files=files,
        operation_type="generate",
        write_result=result.to_dict(),
        duration_ms=duration_ms,
        verbose=verbose,
    )


# ============================================================
# preview — Preview without writing
# ============================================================

@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to CrudConfig JSON/YAML file.")
@click.option("--content", is_flag=True, default=False, help="Include file content in output.")
@click.pass_context
def preview(ctx: click.Context, config: str, content: bool) -> None:
    """Preview generated files without writing to disk."""
    from app.codegen.generator import CrudGenerator
    from app.codegen.schemas import CrudConfig
    from app.codegen.writer import CrudWriter

    root = ctx.obj["output_dir"]
    fmt = ctx.obj["format"]

    config_data = _load_config_file(config)
    crud_config = CrudConfig(**config_data)

    gen = CrudGenerator()
    files = gen.generate(crud_config)

    writer = CrudWriter(root)
    result = writer.preview(files, include_content=content)

    if fmt == "json":
        _print_json(result)
    else:
        click.echo(f"\n  Files: {len(result['files'])}")
        click.echo(f"  New: {result['total_new']}, Conflicts: {result['total_conflict']}\n")
        for f in result["files"]:
            op = f.get("operation", "create")
            if op == "create":
                status = click.style("CREATE", fg="green")
            elif op == "merge":
                status = click.style("MERGE", fg="cyan")
            else:
                status = click.style("CONFLICT", fg="yellow")
            click.echo(f"  [{status}] {f['path']}  ({f.get('size', '?')} bytes)")


# ============================================================
# batch — Multi-table batch generation
# ============================================================

@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to BatchCrudProject JSON/YAML file.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview only, do not write files.")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--entity", default=None, help="Only generate specified entities (comma-separated module names).")
@click.option(
    "--conflict", "conflict_action",
    type=click.Choice(["skip", "overwrite", "merge"]),
    default="skip",
    help="Conflict resolution strategy (default: skip).",
)
@click.pass_context
def batch(ctx: click.Context, config: str, dry_run: bool, force: bool, entity: str | None, conflict_action: str) -> None:
    """Batch generate code from a multi-table BatchCrudProject config."""
    from app.codegen.generator import CrudGenerator
    from app.codegen.schemas import BatchCrudProject
    from app.codegen.writer import ConflictAction, CrudWriter

    verbose = ctx.obj["verbose"]
    root = ctx.obj["output_dir"]

    config_data = _load_config_file(config)
    project = BatchCrudProject(**config_data)

    # Filter entities if --entity is specified
    if entity:
        filter_set = {e.strip() for e in entity.split(",")}
        original_count = len(project.entities)
        project.entities = [e for e in project.entities if e.module in filter_set]
        if verbose:
            click.echo(f"  Filtered: {original_count} → {len(project.entities)} entities ({', '.join(filter_set)})")

    if verbose:
        click.echo(f"  Project: {len(project.entities)} entities")
        for e in project.entities:
            click.echo(f"    - {e.module}.{e.table_name}")

    gen = CrudGenerator()
    files = gen.generate_batch(project)

    writer = CrudWriter(root)

    if dry_run:
        preview_result = writer.preview_batch(files, include_content=False)
        click.echo(f"\n  Preview: {preview_result['total_files']} files across {len(preview_result.get('entities', []))} entities")
        click.echo(f"  New: {preview_result['total_new']}, Conflicts: {preview_result['total_conflict']}\n")
        for ent in preview_result.get("entities", []):
            click.echo(f"  [{ent['entity_name']}]")
            for f in ent.get("files", []):
                op = f.get("operation", "create").upper()
                click.echo(f"    [{op}] {f['path']}")
        return

    preview_result = writer.preview_batch(files, include_content=False)
    click.echo(f"\n  Will generate {preview_result['total_files']} files for {len(preview_result.get('entities', []))} entities")
    click.echo(f"  New: {preview_result['total_new']}, Conflicts: {preview_result['total_conflict']}\n")

    if not force:
        click.confirm("  Proceed with batch file generation?", abort=True)

    action = ConflictAction(conflict_action)

    import time as _time
    start = _time.perf_counter()
    result = writer.write(files, conflict_action=action)
    duration_ms = int((_time.perf_counter() - start) * 1000)

    click.echo(f"\n  Written: {len(result.written)}")
    click.echo(f"  Skipped: {len(result.skipped)}")
    click.echo(f"  Merged:  {len(result.merged)}")
    if result.errors:
        click.echo(f"  Errors:  {len(result.errors)}")
        for err in result.errors:
            click.secho(f"    ✗ {err}", fg="red")

    # Track batch generation record (best-effort, use first entity's config)
    if project.entities:
        _track_record_sync(
            config=project.entities[0],
            files=files,
            operation_type="generate",
            write_result=result.to_dict(),
            duration_ms=duration_ms,
            verbose=verbose,
        )


# ============================================================
# validate — Validate config
# ============================================================

@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to config JSON/YAML file.")
@click.option("--batch", "is_batch", is_flag=True, default=False, help="Validate as BatchCrudProject instead of CrudConfig.")
@click.pass_context
def validate(ctx: click.Context, config: str, is_batch: bool) -> None:
    """Validate a CrudConfig or BatchCrudProject config file."""
    fmt = ctx.obj["format"]

    config_data = _load_config_file(config)

    try:
        if is_batch:
            from app.codegen.schemas import BatchCrudProject
            project = BatchCrudProject(**config_data)

            from app.codegen.project_graph import build_project_graph
            graph = build_project_graph(project)

            if fmt == "json":
                _print_json({
                    "valid": graph.valid,
                    "entity_count": graph.entity_count,
                    "generation_order": graph.generation_order,
                    "issues": [i.model_dump(mode="json") for i in graph.issues],
                    "warnings": [w.model_dump(mode="json") for w in graph.warnings],
                })
            else:
                status = click.style("VALID", fg="green") if graph.valid else click.style("INVALID", fg="red")
                click.echo(f"\n  Status: {status}")
                click.echo(f"  Entities: {graph.entity_count}")
                click.echo(f"  Generation order: {', '.join(graph.generation_order)}")
                if graph.issues:
                    click.echo(f"\n  Issues ({len(graph.issues)}):")
                    for issue in graph.issues:
                        click.secho(f"    ✗ {issue}", fg="red")
                if graph.warnings:
                    click.echo(f"\n  Warnings ({len(graph.warnings)}):")
                    for w in graph.warnings:
                        click.secho(f"    ⚠ {w}", fg="yellow")
        else:
            from app.codegen.schemas import CrudConfig
            crud_config = CrudConfig(**config_data)

            if fmt == "json":
                _print_json({"valid": True, "module": crud_config.module, "table": crud_config.table_name, "fields": len(crud_config.fields)})
            else:
                click.secho(f"\n  ✓ Valid CrudConfig", fg="green")
                click.echo(f"  Module: {crud_config.module}")
                click.echo(f"  Table: {crud_config.table_name}")
                click.echo(f"  Fields: {len(crud_config.fields)}")
                click.echo(f"  Relations: {len(crud_config.relations)}")
                click.echo(f"  Enums: {len(crud_config.enums)}")

    except Exception as exc:
        if fmt == "json":
            _print_json({"valid": False, "error": str(exc)})
        else:
            click.secho(f"\n  ✗ Validation failed: {exc}", fg="red")
        sys.exit(1)


# ============================================================
# init — Create config template
# ============================================================

@cli.command()
@click.option("--output", "-o", default=None, type=click.Path(), help="Output file path (default: stdout).")
@click.option("--batch", "is_batch", is_flag=True, default=False, help="Generate BatchCrudProject template.")
@click.option("--module", "-m", default=None, help="Module name.")
@click.option("--table", "-t", default=None, help="Table name.")
@click.pass_context
def init(ctx: click.Context, output: str | None, is_batch: bool, module: str | None, table: str | None) -> None:
    """Create a CrudConfig or BatchCrudProject template file."""
    if is_batch:
        template = {
            "entities": [
                {
                    "module": module or "example",
                    "table_name": table or "examples",
                    "display_name": "示例",
                    "display_name_en": "Example",
                    "scope": "tenant",
                    "parent_menu": "",
                    "fields": [
                        {"name": "name", "type": "string", "label_zh": "名称", "label_en": "Name", "required": True, "max_length": 100, "searchable": True},
                        {"name": "status", "type": "string", "label_zh": "状态", "label_en": "Status", "required": True, "enum_ref": "ExampleStatus"},
                    ],
                    "enums": [
                        {"name": "ExampleStatus", "values": [
                            {"value": "draft", "label_zh": "草稿", "label_en": "Draft"},
                            {"value": "active", "label_zh": "生效", "label_en": "Active"},
                        ]},
                    ],
                    "relations": [],
                }
            ],
            "cross_relations": [],
            "shared_enums": [],
        }
    else:
        template = {
            "module": module or "example",
            "table_name": table or "examples",
            "display_name": "示例",
            "display_name_en": "Example",
            "scope": "tenant",
            "parent_menu": "",
            "description": "",
            "has_status_toggle": False,
            "fields": [
                {"name": "name", "type": "string", "label_zh": "名称", "label_en": "Name", "required": True, "max_length": 100, "searchable": True, "search_op": "ilike", "in_list": True, "in_form": True},
                {"name": "description", "type": "text", "label_zh": "描述", "label_en": "Description", "required": False, "in_list": False, "in_form": True},
                {"name": "status", "type": "string", "label_zh": "状态", "label_en": "Status", "required": True, "enum_ref": "ExampleStatus", "searchable": True, "search_op": "eq", "in_list": True, "in_form": True},
            ],
            "enums": [
                {"name": "ExampleStatus", "values": [
                    {"value": "draft", "label_zh": "草稿", "label_en": "Draft", "color": "default"},
                    {"value": "active", "label_zh": "生效", "label_en": "Active", "color": "success"},
                    {"value": "archived", "label_zh": "归档", "label_en": "Archived", "color": "warning"},
                ]},
            ],
            "relations": [],
            "indexes": [],
            "custom_slots": [],
        }

    result = json.dumps(template, ensure_ascii=False, indent=2)

    if output:
        Path(output).write_text(result, encoding="utf-8")
        click.echo(f"  ✓ Template written to {output}")
    else:
        click.echo(result)


# ============================================================
# rollback — Rollback by record ID (stub, requires DB)
# ============================================================

@cli.command()
@click.option("--record-id", "-r", required=True, type=int, help="Generation record ID to rollback.")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview files to delete without actually deleting.")
@click.pass_context
def rollback(ctx: click.Context, record_id: int, force: bool, dry_run: bool) -> None:
    """Rollback a previous generation by deleting its generated files."""
    import asyncio
    from app.core.database import get_db_context

    verbose = ctx.obj["verbose"]
    root = ctx.obj["output_dir"]

    async def _load_record() -> dict | None:
        async with get_db_context() as db:
            from sqlalchemy import text
            row = await db.execute(text(
                "SELECT id, module_name, table_name, file_manifest, status "
                "FROM crud_generation_records WHERE id = :id AND is_deleted = false"
            ), {"id": record_id})
            r = row.fetchone()
            if not r:
                return None
            return {
                "id": r[0], "module_name": r[1], "table_name": r[2],
                "file_manifest": r[3], "status": r[4],
            }

    try:
        record = asyncio.run(_load_record())
    except Exception as exc:
        click.secho(f"  ✗ Failed to load record: {exc}", fg="red")
        sys.exit(1)

    if not record:
        click.secho(f"  ✗ Record #{record_id} not found", fg="red")
        sys.exit(1)

    manifest = record.get("file_manifest") or []
    written_files = [f for f in manifest if f.get("operation") in ("written", "merged")]

    if not written_files:
        click.echo(f"  Record #{record_id} has no written files to rollback.")
        return

    click.echo(f"\n  Record #{record_id}: {record['module_name']}.{record['table_name']}")
    click.echo(f"  Files to delete: {len(written_files)}\n")

    deleted = 0
    skipped = 0
    for f in written_files:
        abs_path = Path(root) / f["path"]
        exists = abs_path.exists()
        if dry_run:
            status = "EXISTS" if exists else "MISSING"
            click.echo(f"  [{status}] {f['path']}")
        elif exists:
            if verbose:
                click.echo(f"  Deleting: {f['path']}")

    if dry_run:
        return

    if not force:
        click.confirm(f"  Delete {len(written_files)} files?", abort=True)

    for f in written_files:
        abs_path = Path(root) / f["path"]
        if abs_path.exists():
            try:
                abs_path.unlink()
                deleted += 1
            except OSError as exc:
                click.secho(f"  ✗ Failed to delete {f['path']}: {exc}", fg="red")
                skipped += 1
        else:
            skipped += 1

    click.echo(f"\n  Deleted: {deleted}, Skipped: {skipped}")


# ============================================================
# delete — Delete generated files for a config
# ============================================================

@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to CrudConfig JSON/YAML file.")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview files to delete without actually deleting.")
@click.pass_context
def delete(ctx: click.Context, config: str, force: bool, dry_run: bool) -> None:
    """Delete generated files for a CrudConfig by re-generating and removing matching paths."""
    from app.codegen.generator import CrudGenerator
    from app.codegen.schemas import CrudConfig
    from app.codegen.writer import CrudWriter

    verbose = ctx.obj["verbose"]
    root = ctx.obj["output_dir"]

    config_data = _load_config_file(config)
    crud_config = CrudConfig(**config_data)

    gen = CrudGenerator()
    files = gen.generate(crud_config)

    writer = CrudWriter(root)
    preview_result = writer.preview(files, include_content=False)

    # Only target files that actually exist on disk
    existing_files = [f for f in preview_result["files"] if f.get("exists")]

    if not existing_files:
        click.echo("  No existing generated files found to delete.")
        return

    click.echo(f"\n  Module: {crud_config.module}.{crud_config.table_name}")
    click.echo(f"  Files to delete: {len(existing_files)} / {len(preview_result['files'])}\n")

    for f in existing_files:
        if dry_run:
            click.echo(f"  [DELETE] {f['path']}  ({f.get('size', '?')} bytes)")
        elif verbose:
            click.echo(f"  {f['path']}")

    if dry_run:
        return

    if not force:
        click.confirm(f"  Delete {len(existing_files)} files?", abort=True)

    deleted = 0
    for f in existing_files:
        abs_path = Path(root) / f["path"]
        try:
            abs_path.unlink()
            deleted += 1
        except OSError as exc:
            click.secho(f"  ✗ {f['path']}: {exc}", fg="red")

    click.echo(f"\n  Deleted: {deleted} / {len(existing_files)} files")


# ============================================================
# list-records — Show generation history (stub, requires DB)
# ============================================================

@cli.command("list-records")
@click.option("--limit", "-n", default=10, type=int, help="Number of records to show.")
@click.pass_context
def list_records(ctx: click.Context, limit: int) -> None:
    """Show recent generation records."""
    import asyncio
    from app.core.database import get_db_context

    fmt = ctx.obj["format"]

    async def _query() -> list[dict]:
        async with get_db_context() as db:
            from sqlalchemy import text
            rows = await db.execute(text(
                "SELECT id, module_name, table_name, operation_type, status, "
                "file_count, duration_ms, operator_name, created_at "
                "FROM crud_generation_records WHERE is_deleted = false "
                "ORDER BY created_at DESC LIMIT :limit"
            ), {"limit": limit})
            return [
                {
                    "id": r[0], "module": r[1], "table": r[2],
                    "operation": r[3], "status": r[4],
                    "files": r[5], "duration_ms": r[6],
                    "operator": r[7], "created_at": str(r[8]),
                }
                for r in rows.fetchall()
            ]

    try:
        records = asyncio.run(_query())
    except Exception as exc:
        click.secho(f"  ✗ Failed to query records: {exc}", fg="red")
        sys.exit(1)

    if not records:
        click.echo("  No generation records found.")
        return

    if fmt == "json":
        _print_json(records)
    else:
        columns = ["id", "module", "table", "operation", "status", "files", "operator", "created_at"]
        _print_table(records, columns)


# ============================================================
# __main__ entry
# ============================================================

def main() -> None:
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
