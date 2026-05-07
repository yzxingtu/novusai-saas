"""AI command groups and subcommands."""

from __future__ import annotations

import os
import sys

import click

from app.cli_commands import state as S
from app.cli_commands.ai_render import (
    _build_ai_conversation_compact_diagnostics,
    _normalize_cli_identifier,
    _render_ai_conversation_diagnostics_text,
    _render_ai_conversation_text,
    _render_ai_runtime_section,
    _resolve_ai_conversation_reference,
    _run_ai_runtime_cli_operation,
)
from app.cli_commands.ai_snapshot import (
    _hydrate_ai_conversation_snapshot,
    _load_ai_conversation_snapshot,
)
from app.enums.common import UserRoleEnum

_BACKEND_DIR = S._BACKEND_DIR
_echo_compact_json = S._echo_compact_json
_echo_json = S._echo_json
_ensure_utf8_stdio = S._ensure_utf8_stdio
_json_error = S._json_error
_json_success = S._json_success
_run_async = S._run_async
_run_quietly = S._run_quietly


@click.group("ai", help="AI diagnostics / AI 对话排查")
def ai_cmd() -> None:
    pass


@ai_cmd.command("capabilities")
@click.option("--tenant-id", type=int, default=None, help="Tenant scope ID")
@click.option("--agent-id", type=int, default=None, help="Agent ID")
@click.option("--agent-code", default=None, help="Agent code")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def ai_capabilities(
    tenant_id: int | None,
    agent_id: int | None,
    agent_code: str | None,
    output_json: bool,
) -> None:
    """Show runtime capabilities snapshot / 查看运行态能力快照。"""
    os.chdir(_BACKEND_DIR)
    normalized_agent_code = _normalize_cli_identifier(agent_code)
    if agent_id is not None and normalized_agent_code:
        raise click.ClickException("Use either --agent-id or --agent-code, not both.")
    payload = _run_quietly(
        True,
        _run_async,
        _run_ai_runtime_cli_operation(
            "capabilities",
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=normalized_agent_code,
        ),
    )
    if output_json:
        _echo_json(_json_success({"operation": "capabilities", "result": payload}))
        return
    click.echo(_render_ai_runtime_section("AI Runtime Capabilities", payload))


@ai_cmd.command("doctor")
@click.option("--tenant-id", type=int, default=None, help="Tenant scope ID")
@click.option("--agent-id", type=int, default=None, help="Agent ID")
@click.option("--agent-code", default=None, help="Agent code")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def ai_doctor(
    tenant_id: int | None,
    agent_id: int | None,
    agent_code: str | None,
    output_json: bool,
) -> None:
    """Run runtime doctor checks / 运行 AI Runtime Doctor 检查。"""
    os.chdir(_BACKEND_DIR)
    normalized_agent_code = _normalize_cli_identifier(agent_code)
    if agent_id is not None and normalized_agent_code:
        raise click.ClickException("Use either --agent-id or --agent-code, not both.")
    payload = _run_quietly(
        True,
        _run_async,
        _run_ai_runtime_cli_operation(
            "doctor",
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=normalized_agent_code,
        ),
    )
    if output_json:
        _echo_json(_json_success({"operation": "doctor", "result": payload}))
        return
    click.echo(_render_ai_runtime_section("AI Runtime Doctor", payload))


@ai_cmd.command("smoke")
@click.option("--tenant-id", type=int, default=None, help="Tenant scope ID")
@click.option("--agent-id", type=int, default=None, help="Agent ID")
@click.option("--agent-code", default=None, help="Agent code")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def ai_smoke(
    tenant_id: int | None,
    agent_id: int | None,
    agent_code: str | None,
    output_json: bool,
) -> None:
    """Run agent capability smoke checks / 运行 agent 能力冒烟检查。"""
    os.chdir(_BACKEND_DIR)
    normalized_agent_code = _normalize_cli_identifier(agent_code)
    if agent_id is not None and normalized_agent_code:
        raise click.ClickException("Use either --agent-id or --agent-code, not both.")
    if agent_id is None and not normalized_agent_code:
        raise click.ClickException("smoke requires --agent-id or --agent-code.")
    payload = _run_quietly(
        True,
        _run_async,
        _run_ai_runtime_cli_operation(
            "smoke",
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=normalized_agent_code,
        ),
    )
    if output_json:
        _echo_json(_json_success({"operation": "smoke", "result": payload}))
        return
    click.echo(_render_ai_runtime_section("AI Runtime Smoke", payload))


@ai_cmd.command("real-dialogue-smoke")
@click.option("--tenant-id", type=int, default=0, help="Tenant scope ID")
@click.option("--agent-id", type=int, default=None, help="Agent ID")
@click.option("--agent-code", default=None, help="Agent feature code or exact name")
@click.option(
    "--ledger",
    "ledger_path",
    type=click.Path(dir_okay=False),
    default=str(
        _BACKEND_DIR.parent
        / ".trellis"
        / "tasks"
        / "04-23-codex-llm-first-dialogue-replan"
        / "smoke-scenarios.md"
    ),
    show_default=True,
    help="Scenario ledger path",
)
@click.option(
    "--scenario-id",
    "scenario_ids",
    multiple=True,
    help="Scenario ID to run; repeat to run several. Defaults to all ledger scenarios.",
)
@click.option("--message", default=None, help="Run a one-off custom smoke prompt")
@click.option("--user-id", type=int, default=None, help="Actor user ID")
@click.option(
    "--user-role",
    type=click.Choice(
        [
            UserRoleEnum.PLATFORM_ADMIN.value,
            UserRoleEnum.TENANT_ADMIN.value,
            UserRoleEnum.TENANT_USER.value,
        ]
    ),
    default=UserRoleEnum.PLATFORM_ADMIN.value,
    show_default=True,
    help="Actor user role",
)
@click.option("--user-role-id", type=int, default=None, help="Actor role/org node ID")
@click.option("--json", "output_json", is_flag=True, help="Output JSON envelope")
@click.option(
    "--raw-json",
    "raw_json",
    is_flag=True,
    help="Output raw acceptance report JSON for production probe archives",
)
def ai_real_dialogue_smoke(
    tenant_id: int,
    agent_id: int | None,
    agent_code: str | None,
    ledger_path: str,
    scenario_ids: tuple[str, ...],
    message: str | None,
    user_id: int | None,
    user_role: str,
    user_role_id: int | None,
    output_json: bool,
    raw_json: bool,
) -> None:
    """Run real provider-backed agent dialogue smoke / 运行真实模型对话冒烟检查。"""
    os.chdir(_BACKEND_DIR)
    normalized_agent_code = _normalize_cli_identifier(agent_code)
    if agent_id is not None and normalized_agent_code:
        raise click.ClickException("Use either --agent-id or --agent-code, not both.")
    if agent_id is None and not normalized_agent_code:
        raise click.ClickException(
            "real-dialogue-smoke requires --agent-id or --agent-code."
        )
    payload = _run_quietly(
        True,
        _run_async,
        _run_ai_runtime_cli_operation(
            "real-dialogue-smoke",
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=normalized_agent_code,
            ledger_path=ledger_path,
            scenario_ids=list(scenario_ids),
            message=message,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
            repo_root=str(_BACKEND_DIR.parent),
        ),
    )
    if raw_json:
        _echo_json(payload)
        return
    if output_json:
        _echo_json(
            _json_success({"operation": "real-dialogue-smoke", "result": payload})
        )
        return
    click.echo(_render_ai_runtime_section("AI Real Dialogue Smoke", payload))


@ai_cmd.command("root-cause")
@click.option("--trace-id", default=None, help="Trace ID")
@click.option("--call-log-id", type=int, default=None, help="Call log ID")
@click.option("--conversation-id", type=int, default=None, help="Conversation ID")
@click.option(
    "--turn", type=int, default=None, help="Turn number (with --conversation-id)"
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def ai_root_cause(
    trace_id: str | None,
    call_log_id: int | None,
    conversation_id: int | None,
    turn: int | None,
    output_json: bool,
) -> None:
    """Analyze runtime root cause / 运行时根因分析。"""
    os.chdir(_BACKEND_DIR)
    _ensure_utf8_stdio()
    normalized_trace_id = _normalize_cli_identifier(trace_id)
    from app.exceptions import AppException, NotFoundException

    selectors = [
        bool(normalized_trace_id),
        call_log_id is not None,
        conversation_id is not None,
    ]
    if sum(1 for item in selectors if item) != 1:
        raise click.ClickException(
            "Provide exactly one selector: --trace-id OR --call-log-id OR --conversation-id."
        )
    if conversation_id is not None and turn is None:
        raise click.ClickException("--conversation-id requires --turn.")
    if conversation_id is None and turn is not None:
        raise click.ClickException("--turn can only be used with --conversation-id.")

    try:
        payload = _run_quietly(
            True,
            _run_async,
            _run_ai_runtime_cli_operation(
                "root-cause",
                trace_id=normalized_trace_id,
                call_log_id=call_log_id,
                conversation_id=conversation_id,
                turn=turn,
            ),
        )
    except NotFoundException as e:
        if output_json:
            _echo_json(_json_error(e.message, code="ai_root_cause_not_found"))
        else:
            click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    except AppException as e:
        if output_json:
            _echo_json(
                _json_error(
                    e.message,
                    code="ai_root_cause_failed",
                    data=e.data if isinstance(e.data, dict) else None,
                )
            )
        else:
            click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    if output_json:
        _echo_json(_json_success({"operation": "root-cause", "result": payload}))
        return
    click.echo(_render_ai_runtime_section("AI Runtime Root Cause", payload))


@ai_cmd.group("starter-pack", help="Starter pack ops / 官方 starter pack 操作")
def ai_starter_pack_cmd() -> None:
    pass


@ai_starter_pack_cmd.command("sync")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def ai_starter_pack_sync(output_json: bool) -> None:
    """Sync official starter packs / 同步官方 starter pack。"""
    os.chdir(_BACKEND_DIR)
    payload = _run_quietly(
        True,
        _run_async,
        _run_ai_runtime_cli_operation("starter-pack-sync"),
    )
    if output_json:
        _echo_json(_json_success({"operation": "starter-pack-sync", "result": payload}))
        return
    click.echo(_render_ai_runtime_section("AI Starter Pack Sync", payload))


@ai_cmd.group("conversation", help="Inspect AI conversations / 查询 AI 对话")
def ai_conversation_cmd() -> None:
    pass


@ai_conversation_cmd.command("show")
@click.argument("conversation_ref", type=str)
@click.option(
    "--tail",
    type=click.IntRange(1, 200),
    default=8,
    show_default=True,
    help="Show the last N messages",
)
@click.option("--keyword", default=None, help="Search keyword inside this conversation")
@click.option(
    "--keyword-limit",
    type=click.IntRange(1, 100),
    default=20,
    show_default=True,
    help="Maximum matched messages to return for --keyword",
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
@click.option(
    "--diagnostics-only",
    is_flag=True,
    help="Show only compact orchestration diagnostics",
)
@click.option(
    "--compact-json",
    is_flag=True,
    help="Emit compact JSON without indentation (implies --json)",
)
@click.option(
    "--full-content",
    is_flag=True,
    help="Do not truncate long message content in text mode",
)
def ai_conversation_show(
    conversation_ref: str,
    tail: int,
    keyword: str | None,
    keyword_limit: int,
    output_json: bool,
    diagnostics_only: bool,
    compact_json: bool,
    full_content: bool,
) -> None:
    """Show AI conversation detail by ID or trace ID / 按对话 ID 或 trace ID 查看 AI 对话详情。"""
    os.chdir(_BACKEND_DIR)
    _ensure_utf8_stdio()
    render_json = output_json or compact_json

    from app.exceptions import AppException, BusinessException, NotFoundException

    try:
        conversation_id = _run_quietly(
            True,
            _run_async,
            _resolve_ai_conversation_reference(conversation_ref),
        )
        snapshot = _run_quietly(
            True,
            _run_async,
            _load_ai_conversation_snapshot(
                conversation_id,
                tail=tail,
                keyword=keyword,
                keyword_limit=keyword_limit,
            ),
        )
    except NotFoundException as e:
        if render_json:
            _echo_json(_json_error(e.message, code="conversation_not_found"))
        else:
            click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    except BusinessException as e:
        error_data = dict(e.data) if isinstance(e.data, dict) else None
        error_code = (
            str(error_data.pop("code"))
            if error_data and isinstance(error_data.get("code"), str)
            else "ai_conversation_show_failed"
        )
        if render_json:
            _echo_json(
                _json_error(
                    e.message,
                    code=error_code,
                    data=error_data,
                )
            )
        else:
            click.echo(f"Error: {e.message}", err=True)
            if error_data and error_data.get("operation"):
                click.echo(f"Operation: {error_data['operation']}", err=True)
            if error_data and error_data.get("suggested_command"):
                click.echo(
                    f"Hint: {error_data['suggested_command']}",
                    err=True,
                )
        sys.exit(1)
    except AppException as e:
        if render_json:
            _echo_json(
                _json_error(
                    e.message,
                    code="ai_conversation_show_failed",
                    data=e.data if isinstance(e.data, dict) else None,
                )
            )
        else:
            click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)

    snapshot = _hydrate_ai_conversation_snapshot(snapshot)

    if diagnostics_only:
        diagnostics_payload = _build_ai_conversation_compact_diagnostics(snapshot)
        if compact_json:
            _echo_compact_json(diagnostics_payload)
        elif render_json:
            _echo_json(_json_success({"diagnostics": diagnostics_payload}))
        else:
            click.echo(_render_ai_conversation_diagnostics_text(snapshot))
        return

    if compact_json:
        _echo_compact_json(_json_success(snapshot))
    elif render_json:
        _echo_json(_json_success(snapshot))
    else:
        click.echo(
            _render_ai_conversation_text(
                snapshot,
                full_content=full_content,
            )
        )
