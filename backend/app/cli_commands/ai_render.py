"""AI conversation rendering and runtime bridge helpers."""

from __future__ import annotations

import click

from app.cli_commands import state as S
from app.cli_commands.ai_norm import (
    _compact_json_text,
    _indent_cli_block,
    _normalize_cli_bool,
    _normalize_cli_context_sources,
    _normalize_cli_dict,
    _normalize_cli_dict_list,
    _normalize_cli_fallback_history,
    _normalize_cli_intent_plan,
    _normalize_cli_optional_string,
    _normalize_cli_provider_events,
    _normalize_cli_retry_events,
    _normalize_cli_string_list,
    _truncate_cli_block,
)
from app.cli_commands.ai_snapshot import _hydrate_ai_conversation_snapshot

_BACKEND_DIR = S._BACKEND_DIR
settings = S.settings
_json_default = S._json_default


def _build_ai_conversation_compact_diagnostics(snapshot: dict) -> dict:
    snapshot = _hydrate_ai_conversation_snapshot(snapshot)
    conversation = snapshot.get("conversation") or {}
    diagnostics = snapshot.get("diagnostics") or {}
    intent_plan = _normalize_cli_intent_plan(diagnostics.get("intent_plan"))
    retry_events = _normalize_cli_retry_events(diagnostics.get("retry_events"))
    provider_events = _normalize_cli_provider_events(diagnostics.get("provider_events"))
    budget = _normalize_cli_dict(diagnostics.get("budget"))
    return {
        "conversation_id": conversation.get("id"),
        "tenant_id": conversation.get("tenant_id"),
        "agent_id": conversation.get("agent_id"),
        "user_id": conversation.get("user_id"),
        "status": conversation.get("status"),
        "message_count": conversation.get("message_count"),
        "source": diagnostics.get("source"),
        "turn_outcome": diagnostics.get("turn_outcome"),
        "termination_reason": diagnostics.get("termination_reason"),
        "protocol_path": diagnostics.get("protocol_path"),
        "execution_path": diagnostics.get("execution_path"),
        "selected_tool_names": _normalize_cli_string_list(
            diagnostics.get("selected_tool_names")
        ),
        "selected_skill_names": _normalize_cli_string_list(
            diagnostics.get("selected_skill_names")
        ),
        "candidate_tool_names": _normalize_cli_string_list(
            diagnostics.get("candidate_tool_names")
        ),
        "tool_planner": _normalize_cli_dict(diagnostics.get("tool_planner")),
        "path_decision": _normalize_cli_dict(diagnostics.get("path_decision")),
        "capability_injection": _normalize_cli_dict(
            diagnostics.get("capability_injection")
        ),
        "tool_filtering": _normalize_cli_dict(diagnostics.get("tool_filtering")),
        "recovery_chain": (
            _normalize_cli_dict_list(diagnostics.get("recovery_chain"))
            if isinstance(diagnostics.get("recovery_chain"), list)
            else None
        ),
        "intent_plan": intent_plan,
        "unfinished_intents": _normalize_cli_string_list(
            diagnostics.get("unfinished_intents")
        ),
        "retry_events": retry_events,
        "partial_exit_reason": diagnostics.get("partial_exit_reason"),
        "failure_kind": diagnostics.get("failure_kind"),
        "provider_events": provider_events,
        "budget": budget or None,
        "budget_usage": (
            _normalize_cli_dict((budget or {}).get("usage"))
            if isinstance(budget, dict)
            else {}
        ),
        "budget_status": diagnostics.get("budget_status"),
        "budget_exit_reason": diagnostics.get("budget_exit_reason"),
        "final_output_source": diagnostics.get("final_output_source"),
        "web_research_pipeline_id": diagnostics.get("web_research_pipeline_id"),
        "search_provider": diagnostics.get("search_provider"),
        "fetch_provider": diagnostics.get("fetch_provider"),
        "evidence_status": diagnostics.get("evidence_status"),
        "candidate_urls": _normalize_cli_string_list(diagnostics.get("candidate_urls")),
        "fetched_urls": _normalize_cli_string_list(diagnostics.get("fetched_urls")),
        "evidence_quality": diagnostics.get("evidence_quality"),
        "answer_source": diagnostics.get("answer_source"),
        "web_research_failure_kind": diagnostics.get("web_research_failure_kind"),
        "web_research_failure_layer": diagnostics.get("web_research_failure_layer"),
        "web_research_provider_disable_reason": diagnostics.get(
            "web_research_provider_disable_reason"
        ),
        "contract_breach_type": diagnostics.get("contract_breach_type"),
        "tool_leak_detected": bool(diagnostics.get("tool_leak_detected")),
        "recovered_via_retry": diagnostics.get("recovered_via_retry"),
        "last_tool_name": diagnostics.get("last_tool_name"),
        "interrupted_stage": diagnostics.get("interrupted_stage"),
        "turn_event_count": len(diagnostics.get("turn_events") or []),
    }


def _render_ai_conversation_diagnostics_text(snapshot: dict) -> str:
    conversation = snapshot.get("conversation") or {}
    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    lines = [
        "Conversation #{id} diagnostics".format(id=conversation.get("id")),
        "source={source} outcome={turn_outcome} termination_reason={termination_reason} protocol_path={protocol_path}".format(
            source=compact.get("source") or "-",
            turn_outcome=compact.get("turn_outcome") or "-",
            termination_reason=compact.get("termination_reason") or "-",
            protocol_path=compact.get("protocol_path") or "-",
        ),
        "execution_path={execution_path} failure_kind={failure_kind} budget_status={budget_status} budget_exit_reason={budget_exit_reason}".format(
            execution_path=compact.get("execution_path") or "-",
            failure_kind=compact.get("failure_kind") or "-",
            budget_status=compact.get("budget_status") or "-",
            budget_exit_reason=compact.get("budget_exit_reason") or "-",
        ),
    ]
    if compact.get("final_output_source"):
        lines.append(f"final_output_source={compact.get('final_output_source')}")
    if compact.get("web_research_pipeline_id") or compact.get("evidence_status"):
        lines.append(
            "web_research pipeline_id={pipeline_id} search_provider={search_provider} fetch_provider={fetch_provider} evidence_status={evidence_status} evidence_quality={evidence_quality} answer_source={answer_source}".format(
                pipeline_id=compact.get("web_research_pipeline_id") or "-",
                search_provider=compact.get("search_provider") or "-",
                fetch_provider=compact.get("fetch_provider") or "-",
                evidence_status=compact.get("evidence_status") or "-",
                evidence_quality=compact.get("evidence_quality") or "-",
                answer_source=compact.get("answer_source") or "-",
            )
        )
    candidate_urls = _normalize_cli_string_list(compact.get("candidate_urls"))
    fetched_urls = _normalize_cli_string_list(compact.get("fetched_urls"))
    if candidate_urls:
        lines.append("web_research_candidate_urls={}".format(", ".join(candidate_urls)))
    if fetched_urls:
        lines.append("web_research_fetched_urls={}".format(", ".join(fetched_urls)))
    if compact.get("web_research_failure_kind"):
        lines.append(
            "web_research_failure kind={kind} layer={layer}".format(
                kind=compact.get("web_research_failure_kind"),
                layer=compact.get("web_research_failure_layer") or "-",
            )
        )
    if compact.get("web_research_provider_disable_reason"):
        lines.append(
            "web_research_provider_disable_reason={}".format(
                compact.get("web_research_provider_disable_reason")
            )
        )
    selected_tools = _normalize_cli_string_list(compact.get("selected_tool_names"))
    lines.append(
        "selected_tools={}".format(
            ", ".join(selected_tools) if selected_tools else "[]"
        )
    )
    selected_skills = _normalize_cli_string_list(compact.get("selected_skill_names"))
    if selected_skills:
        lines.append("selected_skills={}".format(", ".join(selected_skills)))
    candidate_tool_names = _normalize_cli_string_list(
        compact.get("candidate_tool_names")
    )
    lines.append(
        "candidate_tools={}".format(
            ", ".join(candidate_tool_names) if candidate_tool_names else "[]"
        )
    )
    tool_planner = _normalize_cli_dict(compact.get("tool_planner"))
    if tool_planner:
        lines.append(f"tool_planner={_compact_json_text(tool_planner)}")
    path_decision = _normalize_cli_dict(compact.get("path_decision"))
    if path_decision:
        lines.append(f"path_decision={_compact_json_text(path_decision)}")
    capability_injection = _normalize_cli_dict(compact.get("capability_injection"))
    if capability_injection:
        lines.append(f"capability_injection={_compact_json_text(capability_injection)}")
    tool_filtering = _normalize_cli_dict(compact.get("tool_filtering"))
    if tool_filtering:
        lines.append(f"tool_filtering={_compact_json_text(tool_filtering)}")
    recovery_chain = compact.get("recovery_chain")
    if isinstance(recovery_chain, list):
        lines.append(f"recovery_chain={_compact_json_text(recovery_chain)}")
    intent_plan = _normalize_cli_intent_plan(compact.get("intent_plan"))
    if intent_plan:
        lines.append(
            "intent_plan={}".format(
                " > ".join(
                    "{}:{}[{}]".format(
                        item.get("family") or "-",
                        item.get("user_visible_label") or item.get("kind") or "-",
                        item.get("status") or "-",
                    )
                    for item in intent_plan
                )
            )
        )
    unfinished_intents = _normalize_cli_string_list(compact.get("unfinished_intents"))
    if unfinished_intents:
        lines.append("unfinished_intents={}".format(", ".join(unfinished_intents)))
    retry_events = _normalize_cli_retry_events(compact.get("retry_events"))
    if retry_events:
        lines.append(f"retry_events={_compact_json_text(retry_events)}")
    if compact.get("partial_exit_reason"):
        lines.append(f"partial_exit_reason={compact.get('partial_exit_reason')}")
    provider_events = _normalize_cli_provider_events(compact.get("provider_events"))
    if provider_events:
        lines.append(f"provider_events={_compact_json_text(provider_events)}")
    budget = _normalize_cli_dict(compact.get("budget"))
    if budget:
        lines.append(f"budget={_compact_json_text(budget)}")
    budget_usage = _normalize_cli_dict(compact.get("budget_usage"))
    if budget_usage:
        lines.append(f"budget_usage={_compact_json_text(budget_usage)}")
    if compact.get("turn_event_count"):
        lines.append(f"turn_event_count={compact.get('turn_event_count')}")
    return "\n".join(lines)


def _render_ai_conversation_text(
    snapshot: dict,
    *,
    full_content: bool = False,
) -> str:
    snapshot = _hydrate_ai_conversation_snapshot(snapshot)
    conversation = snapshot.get("conversation") or {}
    recent_messages = snapshot.get("recent_messages") or []
    keyword = snapshot.get("keyword")
    keyword_hits = snapshot.get("keyword_hits") or []
    recent_call_logs = snapshot.get("recent_call_logs") or []
    diagnostics = snapshot.get("diagnostics") or {}

    lines: list[str] = []
    lines.append(
        "Conversation #{id} tenant={tenant_id} owner={owner_type} agent={agent_id} "
        "user={user_id} status={status} messages={message_count}".format(
            id=conversation.get("id"),
            tenant_id=conversation.get("tenant_id"),
            owner_type=conversation.get("owner_type"),
            agent_id=conversation.get("agent_id"),
            user_id=conversation.get("user_id"),
            status=conversation.get("status"),
            message_count=conversation.get("message_count"),
        )
    )
    if conversation.get("title"):
        lines.append(f"Title: {conversation.get('title')}")
    if conversation.get("agent_name"):
        lines.append(f"Agent: {conversation.get('agent_name')}")
    lines.append(
        "Created: {created_at} | Updated: {updated_at} | Tokens: {token_count} | Cost: {cost}".format(
            created_at=conversation.get("created_at"),
            updated_at=conversation.get("updated_at"),
            token_count=conversation.get("token_count"),
            cost=conversation.get("cost"),
        )
    )

    leaked_names = diagnostics.get("last_assistant_textual_tool_call_names") or []
    if diagnostics.get("last_assistant_looks_like_textual_tool_call"):
        lines.append(
            "Diagnostic: last assistant message looks like leaked textual tool call -> {}".format(
                ", ".join(leaked_names),
            )
        )
    if diagnostics.get("contract_breach_type"):
        lines.append(
            "Diagnostic: contract_breach_type={}".format(
                diagnostics.get("contract_breach_type"),
            )
        )
    if diagnostics.get("unfinished_intents"):
        lines.append(
            "Diagnostic: unfinished_intents={}".format(
                ", ".join(
                    str(item) for item in diagnostics.get("unfinished_intents") or []
                ),
            )
        )
    if diagnostics.get("recovered_via_retry") is not None:
        lines.append(
            "Diagnostic: recovered_via_retry={}".format(
                diagnostics.get("recovered_via_retry"),
            )
        )

    turn_outcome = diagnostics.get("turn_outcome")
    termination_reason = diagnostics.get("termination_reason")
    protocol_path = diagnostics.get("protocol_path")
    selected_tool_names = _normalize_cli_string_list(
        diagnostics.get("selected_tool_names")
    )
    selected_skill_names = _normalize_cli_string_list(
        diagnostics.get("selected_skill_names")
    )
    context_sources = _normalize_cli_context_sources(diagnostics.get("context_sources"))
    fallback_history = _normalize_cli_fallback_history(
        diagnostics.get("fallback_history")
    )
    sync_rescue = _normalize_cli_bool(diagnostics.get("sync_rescue"))
    should_record_call_log = _normalize_cli_bool(
        diagnostics.get("should_record_call_log")
    )
    last_tool_name = str(diagnostics.get("last_tool_name") or "").strip() or None
    interrupted_stage = str(diagnostics.get("interrupted_stage") or "").strip() or None
    tool_loop_progress = (
        dict(diagnostics.get("tool_loop_progress") or {})
        if isinstance(diagnostics.get("tool_loop_progress"), dict)
        else {}
    )
    diagnostics_source = str(diagnostics.get("source") or "").strip() or None
    if turn_outcome or termination_reason or protocol_path:
        lines.append(
            "Turn diagnostics: outcome={} termination_reason={} protocol_path={}".format(
                turn_outcome or "-",
                termination_reason or "-",
                protocol_path or "-",
            )
        )
    if selected_tool_names:
        lines.append(
            "Turn selected tools: {}".format(
                ", ".join(str(item) for item in selected_tool_names)
            )
        )
    if selected_skill_names:
        lines.append(
            "Turn selected skills: {}".format(
                ", ".join(str(item) for item in selected_skill_names)
            )
        )
    if fallback_history:
        lines.append(f"Turn fallback history: {_compact_json_text(fallback_history)}")
    if sync_rescue is not None:
        lines.append(f"Turn sync rescue: {sync_rescue}")
    if should_record_call_log is not None:
        lines.append(f"Turn should_record_call_log: {should_record_call_log}")
    if last_tool_name:
        lines.append(f"Turn last step: tool={last_tool_name}")
    if interrupted_stage:
        lines.append(f"Turn interrupted stage: {interrupted_stage}")
    if tool_loop_progress:
        lines.append(
            f"Turn tool loop progress: {_compact_json_text(tool_loop_progress)}"
        )
    if diagnostics_source:
        lines.append(f"Turn diagnostics source: {diagnostics_source}")
    if context_sources:
        rendered_sources: list[str] = []
        for source in context_sources:
            name = str(source.get("name") or "-")
            kind = str(source.get("kind") or "-")
            active = bool(source.get("active", True))
            rendered_sources.append(f"{kind}:{name}(active={active})")
        if rendered_sources:
            lines.append("Turn context sources: {}".format(", ".join(rendered_sources)))

    if recent_messages:
        lines.append("")
        lines.append(f"Last {len(recent_messages)} message(s):")
        for msg in recent_messages:
            lines.append(
                "[seq={sequence}] role={role} id={id} time={created_at}".format(
                    sequence=msg.get("sequence"),
                    role=msg.get("role"),
                    id=msg.get("id"),
                    created_at=msg.get("created_at"),
                )
            )
            content = _truncate_cli_block(
                msg.get("content") or "",
                full_content=full_content,
            )
            if content:
                lines.append("  content:")
                lines.append(_indent_cli_block(content))
            if msg.get("tool_calls"):
                lines.append("  tool_calls:")
                lines.append(
                    _indent_cli_block(
                        _truncate_cli_block(
                            _compact_json_text(msg.get("tool_calls")),
                            max_chars=1200,
                            full_content=full_content,
                        )
                    )
                )
            if msg.get("metadata"):
                lines.append("  metadata:")
                lines.append(
                    _indent_cli_block(
                        _truncate_cli_block(
                            _compact_json_text(msg.get("metadata")),
                            max_chars=1200,
                            full_content=full_content,
                        )
                    )
                )

    if keyword is not None:
        lines.append("")
        lines.append(f"Keyword hits for {keyword!r}: {len(keyword_hits)}")
        if not keyword_hits:
            lines.append("  No matches found in this conversation.")
        for msg in keyword_hits:
            lines.append(
                "[seq={sequence}] role={role} id={id} time={created_at}".format(
                    sequence=msg.get("sequence"),
                    role=msg.get("role"),
                    id=msg.get("id"),
                    created_at=msg.get("created_at"),
                )
            )
            lines.append("  content:")
            lines.append(
                _indent_cli_block(
                    _truncate_cli_block(
                        msg.get("content") or "",
                        full_content=full_content,
                    )
                )
            )

    if recent_call_logs:
        lines.append("")
        lines.append(f"Recent call logs ({len(recent_call_logs)}):")
        for item in recent_call_logs:
            lines.append(
                "[log_id={id}] time={created_at} status={status} type={call_type} provider={provider_name} "
                "model={model_name} tokens={total_tokens} latency_ms={latency_ms}".format(
                    id=item.get("id"),
                    created_at=item.get("created_at"),
                    status=item.get("status"),
                    call_type=item.get("call_type"),
                    provider_name=item.get("provider_name"),
                    model_name=item.get("model_name"),
                    total_tokens=item.get("total_tokens"),
                    latency_ms=item.get("latency_ms"),
                )
            )
            if item.get("error_message"):
                lines.append(
                    "  error: {}".format(
                        _truncate_cli_block(
                            item.get("error_message"),
                            full_content=full_content,
                        )
                    )
                )
            call_log_turn_outcome = str(item.get("turn_outcome") or "").strip()
            call_log_termination = str(item.get("termination_reason") or "").strip()
            call_log_protocol = str(item.get("protocol_path") or "").strip()
            if call_log_turn_outcome or call_log_termination or call_log_protocol:
                lines.append(
                    "  summary: outcome={} termination_reason={} protocol_path={}".format(
                        call_log_turn_outcome or "-",
                        call_log_termination or "-",
                        call_log_protocol or "-",
                    )
                )
            call_log_skills = _normalize_cli_string_list(
                item.get("selected_skill_names")
            )
            if call_log_skills:
                lines.append("  selected_skills: {}".format(", ".join(call_log_skills)))
            call_log_fallback = _normalize_cli_fallback_history(
                item.get("fallback_history")
            )
            if call_log_fallback:
                lines.append(
                    f"  fallback_history: {_compact_json_text(call_log_fallback)}"
                )
            call_log_sync_rescue = _normalize_cli_bool(item.get("sync_rescue"))
            if call_log_sync_rescue is not None:
                lines.append(f"  sync_rescue: {call_log_sync_rescue}")
            if item.get("last_tool_name"):
                lines.append("  last_step: tool={}".format(item.get("last_tool_name")))
            if item.get("interrupted_stage"):
                lines.append(
                    "  interrupted_stage: {}".format(item.get("interrupted_stage"))
                )
            call_log_progress = (
                dict(item.get("tool_loop_progress") or {})
                if isinstance(item.get("tool_loop_progress"), dict)
                else {}
            )
            if call_log_progress:
                lines.append(
                    f"  tool_loop_progress: {_compact_json_text(call_log_progress)}"
                )

    return "\n".join(lines)


def _normalize_cli_identifier(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


async def _resolve_ai_conversation_reference(conversation_ref: str) -> int:
    """Resolve CLI conversation reference to numeric ID / 将 CLI 会话引用解析为数字 ID。"""
    normalized = _normalize_cli_identifier(conversation_ref)
    from app.core.i18n import _
    from app.exceptions import BusinessException, NotFoundException

    if not normalized:
        raise NotFoundException(message=_("agent_chat.error.conversation_not_found"))
    if normalized and normalized.isdigit():
        return int(normalized)

    from sqlalchemy import select

    from app.core.database import get_db_context
    from app.models.ai.call_log import AICallLog
    from app.models.system.operation_log import OperationLog
    from app.services.system.trace_lookup_service import TraceLookupService

    trace_operation: dict | None = None
    async with get_db_context() as db:
        result = await db.execute(
            select(AICallLog.conversation_id)
            .where(
                AICallLog.trace_id == normalized,
                AICallLog.conversation_id.is_not(None),
                AICallLog.is_deleted.is_(False),
            )
            .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
            .limit(1)
        )
        conversation_id = result.scalar_one_or_none()
        if conversation_id is None:
            operation_result = await db.execute(
                select(
                    OperationLog.method,
                    OperationLog.path,
                    OperationLog.module,
                    OperationLog.action,
                )
                .where(OperationLog.trace_id == normalized)
                .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
                .limit(1)
            )
            operation_row = operation_result.first()
            if operation_row is not None:
                trace_operation = {
                    "method": _normalize_cli_optional_string(operation_row.method),
                    "path": _normalize_cli_optional_string(operation_row.path),
                    "module": _normalize_cli_optional_string(operation_row.module),
                    "action": _normalize_cli_optional_string(operation_row.action),
                }
    if conversation_id is not None:
        return int(conversation_id)

    trace_lookup = TraceLookupService(
        db=None,
        log_dir=(_BACKEND_DIR / settings.LOG_DIR),
    )
    trace_lookup_result = await trace_lookup.lookup(
        normalized,
        source="logs",
        context=0,
        max_blocks=1,
        since_hours=72,
        redact=True,
    )
    if trace_operation is not None or trace_lookup_result.log_matches:
        operation_desc = "unknown operation"
        if trace_operation is not None:
            operation_desc = " ".join(
                part
                for part in [
                    trace_operation.get("method"),
                    trace_operation.get("path"),
                ]
                if part
            ) or (
                trace_operation.get("action")
                or trace_operation.get("module")
                or operation_desc
            )
        raise BusinessException(
            message=_(
                "Trace exists but is not linked to an AI conversation. Use `novusai trace show <trace_id>` instead."
            ),
            data={
                "code": "trace_not_linked_to_conversation",
                "trace_id": normalized,
                "suggested_command": f"novusai trace show {normalized}",
                "operation": operation_desc,
            },
        )
    raise NotFoundException(message=_("agent_chat.error.conversation_not_found"))


def _render_ai_runtime_section(title: str, payload: object) -> str:
    import json

    lines = [title]
    if isinstance(payload, dict):
        for key in sorted(payload.keys()):
            lines.append(f"{key}: {payload.get(key)}")
        return "\n".join(lines)
    if isinstance(payload, list):
        lines.append(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
        )
        return "\n".join(lines)
    lines.append(str(payload))
    return "\n".join(lines)


async def _run_ai_runtime_cli_operation(
    operation: str,
    *,
    tenant_id: int | None = None,
    agent_id: int | None = None,
    agent_code: str | None = None,
    trace_id: str | None = None,
    call_log_id: int | None = None,
    conversation_id: int | None = None,
    turn: int | None = None,
) -> dict:
    from app.core.database import get_db_context
    from app.services.ai.runtime_cli_bridge import AIRuntimeCliBridge, RuntimeCliScope

    scope = RuntimeCliScope(
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_code=agent_code,
    )
    async with get_db_context() as db:
        bridge = AIRuntimeCliBridge(db)
        if operation == "capabilities":
            return await bridge.get_capabilities(scope)
        if operation == "doctor":
            return await bridge.run_doctor(scope)
        if operation == "smoke":
            return await bridge.run_smoke(scope)
        if operation == "root-cause":
            return await bridge.run_root_cause(
                trace_id=trace_id,
                call_log_id=call_log_id,
                conversation_id=conversation_id,
                turn=turn,
            )
        if operation == "starter-pack-sync":
            return await bridge.sync_starter_pack()
    raise click.ClickException(f"Unsupported AI runtime CLI operation: {operation}")
