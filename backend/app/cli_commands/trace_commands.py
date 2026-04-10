"""Trace command domain."""

from __future__ import annotations

import os
import sys

import click

from app.cli_commands import state as S

_BACKEND_DIR = S._BACKEND_DIR
_run_async = S._run_async
_echo_json = S._echo_json
_json_error = S._json_error
settings = S.settings

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


@click.group("trace", help="Trace lookup / 根据 trace_id 查询错误上下文")
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


# ============================================================
# novusai ai / AI 对话排查
# ============================================================
