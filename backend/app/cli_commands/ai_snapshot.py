"""AI conversation data loading and hydration helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.cli_commands import state as S
from app.cli_commands.ai_norm import (
    _extract_turn_diagnostics_from_call_log_metadata,
    _normalize_cli_bool,
    _normalize_cli_call_log_row,
    _normalize_cli_context_sources,
    _normalize_cli_dict,
    _normalize_cli_fallback_history,
    _normalize_cli_intent_plan,
    _normalize_cli_optional_string,
    _normalize_cli_provider_events,
    _normalize_cli_retry_events,
    _normalize_cli_string_list,
    _normalize_cli_tool_calls,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.turn_failure_normalizer import (
    derive_budget_projection,
    resolve_failure_projection,
)

_BACKEND_DIR = S._BACKEND_DIR
settings = S.settings


def _format_cli_dt(dt: object) -> object:
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _serialize_cli_conversation_message(row: object) -> dict:
    from app.services.ai.recovery_evidence_read_model import (
        patch_recovery_evidence_answer_payload,
    )

    metadata = getattr(row, "metadata_", None)
    metadata_payload = dict(metadata) if isinstance(metadata, dict) else None
    payload = {
        "id": getattr(row, "id", None),
        "conversation_id": getattr(row, "conversation_id", None),
        "sequence": getattr(row, "sequence", None),
        "role": getattr(row, "role", None),
        "created_at": _format_cli_dt(getattr(row, "created_at", None)),
        "content": getattr(row, "content", None) or "",
        "tool_calls": _normalize_cli_tool_calls(getattr(row, "tool_calls", None)),
        "tool_call_id": getattr(row, "tool_call_id", None),
        "tool_name": getattr(row, "tool_name", None),
        "token_count": getattr(row, "token_count", None),
        "agent_id": getattr(row, "agent_id", None),
        "model_id": getattr(row, "model_id", None),
        "metadata": metadata_payload,
    }
    if metadata_payload:
        payload["model_name"] = metadata_payload.get("model_name")
        payload["provider_id"] = metadata_payload.get("provider_id")
        payload["provider_name"] = metadata_payload.get("provider_name")
    return patch_recovery_evidence_answer_payload(payload)


def _resolve_assistant_turn_flow(last_assistant: object) -> dict | None:
    if not isinstance(last_assistant, dict):
        return None
    projected = ConversationTurnFlowProjector.project_from_message_payload(
        last_assistant
    )
    return dict(projected) if isinstance(projected, dict) else None


def _resolve_turn_flow_terminal_stage(turn_flow: object) -> dict:
    if not isinstance(turn_flow, dict):
        return {}
    timeline = turn_flow.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        return {}
    for item in reversed(timeline):
        if not isinstance(item, dict):
            continue
        stage_type = _normalize_cli_optional_string(item.get("type"))
        if stage_type in {"completed", "failed"}:
            return dict(item)
    last_stage = timeline[-1]
    return dict(last_stage) if isinstance(last_stage, dict) else {}


def _replace_nested_turn_flow_payloads(payload: object, turn_flow: dict) -> object:
    """中文: CLI 展示只暴露规范化 turn_flow，避免历史脏数据继续误导排障。

    EN: CLI display only exposes normalized turn_flow so historical polluted
    payloads cannot keep misleading diagnostics.
    """
    if isinstance(payload, dict):
        sanitized: dict = {}
        for key, value in payload.items():
            if key in {"turn_flow", "turnFlow"}:
                sanitized[key] = dict(turn_flow)
                continue
            sanitized[key] = _replace_nested_turn_flow_payloads(value, turn_flow)
        return sanitized
    if isinstance(payload, list):
        return [_replace_nested_turn_flow_payloads(item, turn_flow) for item in payload]
    return payload


def _apply_turn_flow_diagnostics_parity(
    snapshot: dict,
    *,
    last_assistant: object = None,
) -> dict:
    if not isinstance(snapshot, dict):
        return {}
    hydrated = dict(snapshot)
    diagnostics = (
        dict(hydrated.get("diagnostics") or {})
        if isinstance(hydrated.get("diagnostics"), dict)
        else {}
    )
    assistant_message = last_assistant
    if not isinstance(assistant_message, dict):
        recent_messages = (
            hydrated.get("recent_messages") or hydrated.get("message_list") or []
        )
        if isinstance(recent_messages, list):
            assistant_message = next(
                (
                    item
                    for item in reversed(recent_messages)
                    if isinstance(item, dict) and item.get("role") == "assistant"
                ),
                None,
            )

    turn_flow = _resolve_assistant_turn_flow(assistant_message)
    normalized_projection = resolve_failure_projection(
        diagnostics=diagnostics,
        turn_flow=turn_flow,
    )
    if turn_flow:
        terminal_stage = _resolve_turn_flow_terminal_stage(turn_flow)
        diagnostics["turn_flow_terminal_stage_type"] = _normalize_cli_optional_string(
            terminal_stage.get("type")
        )
        diagnostics["turn_flow_terminal_stage_status"] = _normalize_cli_optional_string(
            terminal_stage.get("status")
        )
    elif normalized_projection.get("turn_flow_terminal_stage_type"):
        diagnostics["turn_flow_terminal_stage_type"] = _normalize_cli_optional_string(
            normalized_projection.get("turn_flow_terminal_stage_type")
        )
        diagnostics["turn_flow_terminal_stage_status"] = _normalize_cli_optional_string(
            normalized_projection.get("turn_flow_terminal_stage_status")
        )

    normalized_termination_reason = _normalize_cli_optional_string(
        normalized_projection.get("termination_reason")
    )
    if normalized_termination_reason:
        diagnostics["termination_reason"] = normalized_termination_reason
    normalized_turn_outcome = _normalize_cli_optional_string(
        normalized_projection.get("turn_outcome")
    )
    if normalized_turn_outcome:
        diagnostics["turn_outcome"] = normalized_turn_outcome
    normalized_conversation_outcome = _normalize_cli_optional_string(
        normalized_projection.get("conversation_outcome")
    )
    if normalized_conversation_outcome:
        diagnostics["conversation_outcome"] = normalized_conversation_outcome
    normalized_failure_kind = _normalize_cli_optional_string(
        normalized_projection.get("failure_kind")
    )
    if normalized_failure_kind:
        diagnostics["failure_kind"] = normalized_failure_kind
    elif normalized_projection.get("turn_outcome") == "success":
        diagnostics.pop("failure_kind", None)
    normalized_budget_exit_reason = _normalize_cli_optional_string(
        normalized_projection.get("budget_exit_reason")
    )
    if normalized_budget_exit_reason:
        diagnostics["budget_exit_reason"] = normalized_budget_exit_reason
    normalized_final_output_source = _normalize_cli_optional_string(
        normalized_projection.get("final_output_source")
    )
    if normalized_final_output_source:
        diagnostics["final_output_source"] = normalized_final_output_source
    if (
        diagnostics.get("turn_outcome") == "success"
        and diagnostics.get("termination_reason") == "completed"
        and diagnostics.get("partial_exit_reason")
        == diagnostics.get("budget_exit_reason")
    ):
        diagnostics.pop("partial_exit_reason", None)

    if isinstance(assistant_message, dict) and turn_flow:
        assistant_message["turn_flow"] = turn_flow
        metadata = (
            dict(assistant_message.get("metadata") or {})
            if isinstance(assistant_message.get("metadata"), dict)
            else {}
        )
        metadata = _replace_nested_turn_flow_payloads(metadata, turn_flow)
        if isinstance(metadata, dict):
            metadata["turn_flow"] = turn_flow
        assistant_message["metadata"] = metadata
    if turn_flow:
        diagnostics = _replace_nested_turn_flow_payloads(diagnostics, turn_flow)

    hydrated["diagnostics"] = diagnostics
    return hydrated


async def _load_ai_conversation_snapshot(
    conversation_id: int,
    *,
    tail: int,
    keyword: str | None,
    keyword_limit: int,
) -> dict:
    from sqlalchemy import and_, func, select

    from app.ai.text_semantics import extract_textual_tool_call_names
    from app.core.database import get_db_context
    from app.core.i18n import _
    from app.exceptions import NotFoundException
    from app.models.ai.agent import Agent
    from app.models.ai.agent_conversation import AgentConversation
    from app.models.ai.call_log import AICallLog
    from app.models.ai.conversation_message import ConversationMessage

    async with get_db_context() as db:
        conversation = (
            (
                await db.execute(
                    select(AgentConversation).where(
                        AgentConversation.id == conversation_id,
                        AgentConversation.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .first()
        )
        if conversation is None:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )

        total_messages = (
            await db.execute(
                select(func.count(ConversationMessage.id)).where(
                    ConversationMessage.tenant_id == conversation.tenant_id,
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.is_deleted.is_(False),
                )
            )
        ).scalar() or 0
        skip = max(int(total_messages) - tail, 0)
        message_stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.tenant_id == conversation.tenant_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
            .order_by(ConversationMessage.sequence.asc())
            .offset(skip)
            .limit(tail)
        )
        message_rows = (await db.execute(message_stmt)).scalars().all()
        recent_messages = [
            _serialize_cli_conversation_message(row) for row in message_rows
        ]
        agent_name = (
            await db.execute(
                select(Agent.name).where(Agent.id == conversation.agent_id)
            )
        ).scalar_one_or_none()
        detail = {
            "id": conversation.id,
            "tenant_id": conversation.tenant_id,
            "agent_id": conversation.agent_id,
            "agent_name": agent_name,
            "user_id": conversation.user_id,
            "owner_type": conversation.owner_type,
            "status": conversation.status,
            "title": conversation.title,
            "message_count": int(total_messages),
            "token_count": conversation.token_count,
            "cost": conversation.cost,
            "created_at": _format_cli_dt(conversation.created_at),
            "updated_at": _format_cli_dt(conversation.updated_at),
            "message_list": recent_messages,
        }

        last_assistant = next(
            (
                item
                for item in reversed(recent_messages)
                if item.get("role") == "assistant"
            ),
            None,
        )
        if last_assistant is None:
            latest_assistant_row = (
                (
                    await db.execute(
                        select(ConversationMessage)
                        .where(
                            ConversationMessage.tenant_id == conversation.tenant_id,
                            ConversationMessage.conversation_id == conversation_id,
                            ConversationMessage.is_deleted.is_(False),
                            ConversationMessage.role == "assistant",
                        )
                        .order_by(ConversationMessage.sequence.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if latest_assistant_row is not None:
                last_assistant = _serialize_cli_conversation_message(
                    latest_assistant_row
                )

        keyword_hits: list[dict] = []
        if keyword:
            escaped = keyword.replace("%", "\\%").replace("_", "\\_")
            stmt = (
                select(ConversationMessage)
                .where(
                    and_(
                        ConversationMessage.tenant_id == conversation.tenant_id,
                        ConversationMessage.conversation_id == conversation_id,
                        ConversationMessage.is_deleted.is_(False),
                        ConversationMessage.content.ilike(f"%{escaped}%"),
                    )
                )
                .order_by(ConversationMessage.sequence.asc())
                .limit(keyword_limit)
            )
            matched_rows = (await db.execute(stmt)).scalars().all()
            keyword_hits = [
                {
                    "id": row.id,
                    "sequence": row.sequence,
                    "role": row.role,
                    "created_at": _format_cli_dt(row.created_at),
                    "content": row.content or "",
                }
                for row in matched_rows
            ]

        call_log_stmt = (
            select(AICallLog)
            .where(
                AICallLog.conversation_id == conversation_id,
                AICallLog.call_type == "main_chat",
                AICallLog.is_deleted.is_(False),
            )
            .order_by(AICallLog.created_at.desc())
            .limit(3)
        )
        call_logs = (await db.execute(call_log_stmt)).scalars().all()

        last_assistant_text = str((last_assistant or {}).get("content") or "")
        leaked_tool_names = extract_textual_tool_call_names(
            last_assistant_text,
            alias_to_tool_name={},
        )
        assistant_metadata = (
            dict((last_assistant or {}).get("metadata") or {})
            if isinstance((last_assistant or {}).get("metadata"), dict)
            else {}
        )
        assistant_context_diagnostics = (
            dict(assistant_metadata.get("context_diagnostics") or {})
            if isinstance(assistant_metadata.get("context_diagnostics"), dict)
            else {}
        )
        assistant_last_run_summary = (
            dict(assistant_metadata.get("last_run_summary") or {})
            if isinstance(assistant_metadata.get("last_run_summary"), dict)
            else {}
        )
        assistant_tool_planner = (
            dict(assistant_metadata.get("tool_planner") or {})
            if isinstance(assistant_metadata.get("tool_planner"), dict)
            else {}
        )
        assistant_context_tool_planner = (
            dict(assistant_context_diagnostics.get("tool_planner") or {})
            if isinstance(assistant_context_diagnostics.get("tool_planner"), dict)
            else {}
        )
        assistant_summary_tool_planner = (
            dict(assistant_last_run_summary.get("tool_planner") or {})
            if isinstance(assistant_last_run_summary.get("tool_planner"), dict)
            else {}
        )
        detail_context_diagnostics = (
            dict(detail.get("context_diagnostics") or {})
            if isinstance(detail.get("context_diagnostics"), dict)
            else {}
        )
        detail_last_run_summary = (
            dict(detail.get("last_run_summary") or {})
            if isinstance(detail.get("last_run_summary"), dict)
            else {}
        )
        detail_context_tool_planner = (
            dict(detail_context_diagnostics.get("tool_planner") or {})
            if isinstance(detail_context_diagnostics.get("tool_planner"), dict)
            else {}
        )
        detail_summary_tool_planner = (
            dict(detail_last_run_summary.get("tool_planner") or {})
            if isinstance(detail_last_run_summary.get("tool_planner"), dict)
            else {}
        )
        latest_call_log_diagnostics = {}
        for row in call_logs:
            request_metadata = (
                row.request_metadata if isinstance(row.request_metadata, dict) else {}
            )
            diagnostics_from_log = _extract_turn_diagnostics_from_call_log_metadata(
                request_metadata
            )
            if diagnostics_from_log:
                latest_call_log_diagnostics = diagnostics_from_log
                break
        assistant_turn_record = (
            dict(assistant_metadata.get("turn_record") or {})
            if isinstance(assistant_metadata.get("turn_record"), dict)
            else {}
        )
        call_log_turn_record = (
            dict(latest_call_log_diagnostics.get("turn_record") or {})
            if isinstance(latest_call_log_diagnostics.get("turn_record"), dict)
            else {}
        )
        turn_record = assistant_turn_record or call_log_turn_record
        turn_outcome = _normalize_cli_optional_string(
            turn_record.get("turn_outcome")
            or assistant_metadata.get("turn_outcome")
            or assistant_context_diagnostics.get("turn_outcome")
            or assistant_last_run_summary.get("turn_outcome")
            or detail_context_diagnostics.get("turn_outcome")
            or detail_last_run_summary.get("turn_outcome")
            or latest_call_log_diagnostics.get("turn_outcome")
        )
        termination_reason = _normalize_cli_optional_string(
            turn_record.get("termination_reason")
            or assistant_metadata.get("termination_reason")
            or assistant_context_diagnostics.get("termination_reason")
            or assistant_last_run_summary.get("termination_reason")
            or assistant_last_run_summary.get("completion_reason")
            or detail_context_diagnostics.get("termination_reason")
            or detail_last_run_summary.get("termination_reason")
            or detail_last_run_summary.get("completion_reason")
            or assistant_metadata.get("completion_reason")
            or latest_call_log_diagnostics.get("termination_reason")
        )
        protocol_path = _normalize_cli_optional_string(
            turn_record.get("protocol_path")
            or assistant_metadata.get("protocol_path")
            or assistant_context_diagnostics.get("protocol_path")
            or assistant_last_run_summary.get("protocol_path")
            or detail_context_diagnostics.get("protocol_path")
            or detail_last_run_summary.get("protocol_path")
            or latest_call_log_diagnostics.get("protocol_path")
        )

        selected_tool_names = (
            _normalize_cli_string_list(turn_record.get("selected_tool_names"))
            or _normalize_cli_string_list(assistant_metadata.get("selected_tool_names"))
            or _normalize_cli_string_list(
                assistant_context_diagnostics.get("selected_tool_names")
            )
            or _normalize_cli_string_list(
                assistant_last_run_summary.get("selected_tool_names")
            )
            or _normalize_cli_string_list(
                detail_context_diagnostics.get("selected_tool_names")
            )
            or _normalize_cli_string_list(
                detail_last_run_summary.get("selected_tool_names")
            )
            or _normalize_cli_string_list(
                latest_call_log_diagnostics.get("selected_tool_names")
            )
        )
        selected_skill_names = (
            _normalize_cli_string_list(turn_record.get("selected_skill_names"))
            or _normalize_cli_string_list(
                assistant_metadata.get("selected_skill_names")
            )
            or _normalize_cli_string_list(
                assistant_context_diagnostics.get("selected_skill_names")
            )
            or _normalize_cli_string_list(
                assistant_last_run_summary.get("selected_skill_names")
            )
            or _normalize_cli_string_list(
                detail_context_diagnostics.get("selected_skill_names")
            )
            or _normalize_cli_string_list(
                detail_last_run_summary.get("selected_skill_names")
            )
            or _normalize_cli_string_list(
                latest_call_log_diagnostics.get("selected_skill_names")
            )
        )
        context_sources = (
            _normalize_cli_context_sources(turn_record.get("context_sources"))
            or _normalize_cli_context_sources(assistant_metadata.get("context_sources"))
            or _normalize_cli_context_sources(
                assistant_context_diagnostics.get("context_sources")
            )
            or _normalize_cli_context_sources(
                assistant_last_run_summary.get("context_sources")
            )
            or _normalize_cli_context_sources(
                detail_context_diagnostics.get("context_sources")
            )
            or _normalize_cli_context_sources(
                detail_last_run_summary.get("context_sources")
            )
            or _normalize_cli_context_sources(
                latest_call_log_diagnostics.get("context_sources")
            )
        )
        fallback_history = (
            _normalize_cli_fallback_history(turn_record.get("fallback_history"))
            or _normalize_cli_fallback_history(
                assistant_metadata.get("fallback_history")
            )
            or _normalize_cli_fallback_history(
                assistant_context_diagnostics.get("fallback_history")
            )
            or _normalize_cli_fallback_history(
                assistant_last_run_summary.get("fallback_history")
            )
            or _normalize_cli_fallback_history(
                detail_context_diagnostics.get("fallback_history")
            )
            or _normalize_cli_fallback_history(
                detail_last_run_summary.get("fallback_history")
            )
            or _normalize_cli_fallback_history(
                latest_call_log_diagnostics.get("fallback_history")
            )
        )
        sync_rescue = next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(
                        (turn_record.get("metadata") or {}).get("sync_rescue")
                        if isinstance(turn_record.get("metadata"), dict)
                        else None
                    ),
                    _normalize_cli_bool(turn_record.get("sync_rescue")),
                    _normalize_cli_bool(assistant_metadata.get("sync_rescue")),
                    _normalize_cli_bool(
                        assistant_context_diagnostics.get("sync_rescue")
                    ),
                    _normalize_cli_bool(assistant_last_run_summary.get("sync_rescue")),
                    _normalize_cli_bool(detail_context_diagnostics.get("sync_rescue")),
                    _normalize_cli_bool(detail_last_run_summary.get("sync_rescue")),
                    _normalize_cli_bool(latest_call_log_diagnostics.get("sync_rescue")),
                )
                if parsed is not None
            ),
            None,
        )
        should_record_call_log = next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(
                        (turn_record.get("metadata") or {}).get(
                            "should_record_call_log"
                        )
                        if isinstance(turn_record.get("metadata"), dict)
                        else None
                    ),
                    _normalize_cli_bool(turn_record.get("should_record_call_log")),
                    _normalize_cli_bool(
                        assistant_context_diagnostics.get("should_record_call_log")
                    ),
                    _normalize_cli_bool(
                        assistant_last_run_summary.get("should_record_call_log")
                    ),
                    _normalize_cli_bool(
                        detail_context_diagnostics.get("should_record_call_log")
                    ),
                    _normalize_cli_bool(
                        detail_last_run_summary.get("should_record_call_log")
                    ),
                    _normalize_cli_bool(
                        latest_call_log_diagnostics.get("should_record_call_log")
                    ),
                )
                if parsed is not None
            ),
            None,
        )
        contract_breach_type = (
            _normalize_cli_optional_string(
                (turn_record.get("metadata") or {}).get("contract_breach_type")
                if isinstance(turn_record.get("metadata"), dict)
                else None
            )
            or _normalize_cli_optional_string(
                assistant_context_diagnostics.get("contract_breach_type")
            )
            or _normalize_cli_optional_string(
                assistant_last_run_summary.get("contract_breach_type")
            )
            or _normalize_cli_optional_string(
                detail_context_diagnostics.get("contract_breach_type")
            )
            or _normalize_cli_optional_string(
                detail_last_run_summary.get("contract_breach_type")
            )
            or _normalize_cli_optional_string(
                latest_call_log_diagnostics.get("contract_breach_type")
            )
        )
        tool_leak_detected = bool(
            (
                (turn_record.get("metadata") or {}).get("tool_leak_detected")
                if isinstance(turn_record.get("metadata"), dict)
                else False
            )
            or assistant_context_diagnostics.get("tool_leak_detected")
            or assistant_last_run_summary.get("tool_leak_detected")
            or detail_context_diagnostics.get("tool_leak_detected")
            or detail_last_run_summary.get("tool_leak_detected")
            or latest_call_log_diagnostics.get("tool_leak_detected")
        )
        unfinished_intents = (
            _normalize_cli_string_list(
                (turn_record.get("metadata") or {}).get("unfinished_intents")
                if isinstance(turn_record.get("metadata"), dict)
                else None
            )
            or _normalize_cli_string_list(
                assistant_context_diagnostics.get("unfinished_intents")
            )
            or _normalize_cli_string_list(
                assistant_last_run_summary.get("unfinished_intents")
            )
            or _normalize_cli_string_list(
                detail_context_diagnostics.get("unfinished_intents")
            )
            or _normalize_cli_string_list(
                detail_last_run_summary.get("unfinished_intents")
            )
            or _normalize_cli_string_list(
                latest_call_log_diagnostics.get("unfinished_intents")
            )
        )
        leaked_tool_names = (
            _normalize_cli_string_list(
                (turn_record.get("metadata") or {}).get("leaked_tool_names")
                if isinstance(turn_record.get("metadata"), dict)
                else None
            )
            or _normalize_cli_string_list(
                assistant_context_diagnostics.get("leaked_tool_names")
            )
            or _normalize_cli_string_list(
                assistant_last_run_summary.get("leaked_tool_names")
            )
            or _normalize_cli_string_list(
                detail_context_diagnostics.get("leaked_tool_names")
            )
            or _normalize_cli_string_list(
                detail_last_run_summary.get("leaked_tool_names")
            )
            or _normalize_cli_string_list(
                latest_call_log_diagnostics.get("leaked_tool_names")
            )
            or leaked_tool_names
        )
        recovered_via_retry = next(
            (
                parsed
                for parsed in (
                    _normalize_cli_bool(
                        (turn_record.get("metadata") or {}).get("recovered_via_retry")
                        if isinstance(turn_record.get("metadata"), dict)
                        else None
                    ),
                    _normalize_cli_bool(
                        assistant_context_diagnostics.get("recovered_via_retry")
                    ),
                    _normalize_cli_bool(
                        assistant_last_run_summary.get("recovered_via_retry")
                    ),
                    _normalize_cli_bool(
                        detail_context_diagnostics.get("recovered_via_retry")
                    ),
                    _normalize_cli_bool(
                        detail_last_run_summary.get("recovered_via_retry")
                    ),
                    _normalize_cli_bool(
                        latest_call_log_diagnostics.get("recovered_via_retry")
                    ),
                )
                if parsed is not None
            ),
            None,
        )
        execution_path = _normalize_cli_optional_string(
            turn_record.get("execution_path")
            or assistant_metadata.get("execution_path")
            or assistant_context_diagnostics.get("execution_path")
            or assistant_last_run_summary.get("execution_path")
            or assistant_tool_planner.get("execution_path")
            or assistant_context_tool_planner.get("execution_path")
            or assistant_summary_tool_planner.get("execution_path")
            or detail_context_diagnostics.get("execution_path")
            or detail_last_run_summary.get("execution_path")
            or detail_context_tool_planner.get("execution_path")
            or detail_summary_tool_planner.get("execution_path")
            or latest_call_log_diagnostics.get("execution_path")
        )
        intent_plan = (
            _normalize_cli_intent_plan(turn_record.get("intent_plan"))
            or _normalize_cli_intent_plan(assistant_metadata.get("intent_plan"))
            or _normalize_cli_intent_plan(
                assistant_context_diagnostics.get("intent_plan")
            )
            or _normalize_cli_intent_plan(assistant_last_run_summary.get("intent_plan"))
            or _normalize_cli_intent_plan(assistant_tool_planner.get("intent_plan"))
            or _normalize_cli_intent_plan(
                assistant_context_tool_planner.get("intent_plan")
            )
            or _normalize_cli_intent_plan(
                assistant_summary_tool_planner.get("intent_plan")
            )
            or _normalize_cli_intent_plan(detail_context_diagnostics.get("intent_plan"))
            or _normalize_cli_intent_plan(detail_last_run_summary.get("intent_plan"))
            or _normalize_cli_intent_plan(
                detail_context_tool_planner.get("intent_plan")
            )
            or _normalize_cli_intent_plan(
                detail_summary_tool_planner.get("intent_plan")
            )
            or _normalize_cli_intent_plan(
                latest_call_log_diagnostics.get("intent_plan")
            )
        )
        budget = (
            _normalize_cli_dict(turn_record.get("budget"))
            or _normalize_cli_dict(assistant_metadata.get("budget"))
            or _normalize_cli_dict(assistant_context_diagnostics.get("budget"))
            or _normalize_cli_dict(assistant_last_run_summary.get("budget"))
            or _normalize_cli_dict(detail_context_diagnostics.get("budget"))
            or _normalize_cli_dict(detail_last_run_summary.get("budget"))
            or _normalize_cli_dict(latest_call_log_diagnostics.get("budget"))
        )
        budget_status = (
            str(
                (budget or {}).get("status")
                or assistant_context_diagnostics.get("budget_status")
                or assistant_last_run_summary.get("budget_status")
                or detail_context_diagnostics.get("budget_status")
                or detail_last_run_summary.get("budget_status")
                or latest_call_log_diagnostics.get("budget_status")
                or ""
            ).strip()
            or None
        )
        budget_exit_reason = (
            str(
                (budget or {}).get("exit_reason")
                or assistant_context_diagnostics.get("budget_exit_reason")
                or assistant_last_run_summary.get("budget_exit_reason")
                or (
                    (assistant_context_diagnostics.get("tool_loop_progress") or {}).get(
                        "budget_exit_reason"
                    )
                    if isinstance(
                        assistant_context_diagnostics.get("tool_loop_progress"), dict
                    )
                    else None
                )
                or (
                    (assistant_last_run_summary.get("tool_loop_progress") or {}).get(
                        "budget_exit_reason"
                    )
                    if isinstance(
                        assistant_last_run_summary.get("tool_loop_progress"), dict
                    )
                    else None
                )
                or detail_context_diagnostics.get("budget_exit_reason")
                or detail_last_run_summary.get("budget_exit_reason")
                or (
                    (detail_context_diagnostics.get("tool_loop_progress") or {}).get(
                        "budget_exit_reason"
                    )
                    if isinstance(
                        detail_context_diagnostics.get("tool_loop_progress"), dict
                    )
                    else None
                )
                or (
                    (detail_last_run_summary.get("tool_loop_progress") or {}).get(
                        "budget_exit_reason"
                    )
                    if isinstance(
                        detail_last_run_summary.get("tool_loop_progress"), dict
                    )
                    else None
                )
                or latest_call_log_diagnostics.get("budget_exit_reason")
                or (
                    termination_reason
                    if str(termination_reason or "").endswith("_budget_exceeded")
                    else ""
                )
                or ""
            ).strip()
            or None
        )
        candidate_tool_names = (
            _normalize_cli_string_list(turn_record.get("candidate_tool_names"))
            or _normalize_cli_string_list(
                assistant_metadata.get("candidate_tool_names")
            )
            or _normalize_cli_string_list(
                assistant_context_diagnostics.get("candidate_tool_names")
            )
            or _normalize_cli_string_list(
                assistant_last_run_summary.get("candidate_tool_names")
            )
            or _normalize_cli_string_list(
                detail_context_diagnostics.get("candidate_tool_names")
            )
            or _normalize_cli_string_list(
                detail_last_run_summary.get("candidate_tool_names")
            )
            or _normalize_cli_string_list(
                latest_call_log_diagnostics.get("candidate_tool_names")
            )
        )
        retry_events = (
            _normalize_cli_retry_events(turn_record.get("retry_events"))
            or _normalize_cli_retry_events(assistant_metadata.get("retry_events"))
            or _normalize_cli_retry_events(
                assistant_context_diagnostics.get("retry_events")
            )
            or _normalize_cli_retry_events(
                assistant_last_run_summary.get("retry_events")
            )
            or _normalize_cli_retry_events(
                detail_context_diagnostics.get("retry_events")
            )
            or _normalize_cli_retry_events(detail_last_run_summary.get("retry_events"))
            or _normalize_cli_retry_events(
                latest_call_log_diagnostics.get("retry_events")
            )
        )
        partial_exit_reason = (
            str(
                turn_record.get("partial_exit_reason")
                or assistant_metadata.get("partial_exit_reason")
                or assistant_context_diagnostics.get("partial_exit_reason")
                or assistant_last_run_summary.get("partial_exit_reason")
                or budget_exit_reason
                or detail_context_diagnostics.get("partial_exit_reason")
                or detail_last_run_summary.get("partial_exit_reason")
                or latest_call_log_diagnostics.get("partial_exit_reason")
                or ""
            ).strip()
            or None
        )
        failure_kind = (
            str(
                turn_record.get("failure_kind")
                or assistant_metadata.get("failure_kind")
                or assistant_context_diagnostics.get("failure_kind")
                or assistant_last_run_summary.get("failure_kind")
                or detail_context_diagnostics.get("failure_kind")
                or detail_last_run_summary.get("failure_kind")
                or latest_call_log_diagnostics.get("failure_kind")
                or ""
            ).strip()
            or None
        )
        final_output_source = (
            str(
                turn_record.get("final_output_source")
                or assistant_metadata.get("final_output_source")
                or assistant_context_diagnostics.get("final_output_source")
                or assistant_last_run_summary.get("final_output_source")
                or detail_context_diagnostics.get("final_output_source")
                or detail_last_run_summary.get("final_output_source")
                or latest_call_log_diagnostics.get("final_output_source")
                or ""
            ).strip()
            or None
        )
        provider_events = (
            _normalize_cli_provider_events(turn_record.get("provider_events"))
            or _normalize_cli_provider_events(assistant_metadata.get("provider_events"))
            or _normalize_cli_provider_events(
                assistant_context_diagnostics.get("provider_events")
            )
            or _normalize_cli_provider_events(
                assistant_last_run_summary.get("provider_events")
            )
            or _normalize_cli_provider_events(
                detail_context_diagnostics.get("provider_events")
            )
            or _normalize_cli_provider_events(
                detail_last_run_summary.get("provider_events")
            )
            or _normalize_cli_provider_events(
                latest_call_log_diagnostics.get("provider_events")
            )
        )
        last_tool_name = (
            str(
                turn_record.get("last_tool_name")
                or assistant_metadata.get("last_tool_name")
                or assistant_context_diagnostics.get("last_tool_name")
                or assistant_last_run_summary.get("last_tool_name")
                or detail_context_diagnostics.get("last_tool_name")
                or detail_last_run_summary.get("last_tool_name")
                or latest_call_log_diagnostics.get("last_tool_name")
                or ""
            ).strip()
            or None
        )
        interrupted_stage = (
            str(
                turn_record.get("interrupted_stage")
                or assistant_metadata.get("interrupted_stage")
                or assistant_context_diagnostics.get("interrupted_stage")
                or assistant_last_run_summary.get("interrupted_stage")
                or detail_context_diagnostics.get("interrupted_stage")
                or detail_last_run_summary.get("interrupted_stage")
                or latest_call_log_diagnostics.get("interrupted_stage")
                or ""
            ).strip()
            or None
        )
        tool_loop_progress = (
            _normalize_cli_dict(turn_record.get("tool_loop_progress"))
            if isinstance(turn_record.get("tool_loop_progress"), dict)
            else (
                _normalize_cli_dict(
                    assistant_context_diagnostics.get("tool_loop_progress")
                )
                if isinstance(
                    assistant_context_diagnostics.get("tool_loop_progress"), dict
                )
                else (
                    _normalize_cli_dict(
                        assistant_last_run_summary.get("tool_loop_progress")
                    )
                    if isinstance(
                        assistant_last_run_summary.get("tool_loop_progress"), dict
                    )
                    else (
                        _normalize_cli_dict(
                            detail_context_diagnostics.get("tool_loop_progress")
                        )
                        if isinstance(
                            detail_context_diagnostics.get("tool_loop_progress"), dict
                        )
                        else (
                            _normalize_cli_dict(
                                detail_last_run_summary.get("tool_loop_progress")
                            )
                            if isinstance(
                                detail_last_run_summary.get("tool_loop_progress"), dict
                            )
                            else (
                                _normalize_cli_dict(
                                    latest_call_log_diagnostics.get(
                                        "tool_loop_progress"
                                    )
                                )
                                if isinstance(
                                    latest_call_log_diagnostics.get(
                                        "tool_loop_progress"
                                    ),
                                    dict,
                                )
                                else {}
                            )
                        )
                    )
                )
            )
        )

        recent_call_logs: list[dict] = []
        for row in call_logs:
            request_metadata = (
                row.request_metadata if isinstance(row.request_metadata, dict) else {}
            )
            row_diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
                request_metadata
            )
            recent_call_logs.append(
                _normalize_cli_call_log_row(
                    {
                        "id": row.id,
                        "created_at": _format_cli_dt(row.created_at),
                        "status": row.status,
                        "call_type": row.call_type,
                        "provider_id": row.provider_id,
                        "provider_name": row.provider_name_snapshot,
                        "model_id": row.model_id,
                        "model_name": row.model_name_snapshot,
                        "input_tokens": row.input_tokens,
                        "output_tokens": row.output_tokens,
                        "total_tokens": row.total_tokens,
                        "latency_ms": row.latency_ms,
                        "error_message": row.error_message,
                        "turn_outcome": row_diagnostics.get("turn_outcome"),
                        "termination_reason": row_diagnostics.get("termination_reason"),
                        "protocol_path": row_diagnostics.get("protocol_path"),
                        "selected_tool_names": row_diagnostics.get(
                            "selected_tool_names"
                        ),
                        "selected_skill_names": row_diagnostics.get(
                            "selected_skill_names"
                        ),
                        "execution_path": row_diagnostics.get("execution_path"),
                        "failure_kind": row_diagnostics.get("failure_kind"),
                        "fallback_history": row_diagnostics.get("fallback_history"),
                        "provider_events": row_diagnostics.get("provider_events"),
                        "budget": row_diagnostics.get("budget"),
                        "budget_status": row_diagnostics.get("budget_status"),
                        "budget_exit_reason": row_diagnostics.get("budget_exit_reason"),
                        "final_output_source": row_diagnostics.get(
                            "final_output_source"
                        ),
                        "path_decision": row_diagnostics.get("path_decision"),
                        "capability_injection": row_diagnostics.get(
                            "capability_injection"
                        ),
                        "tool_filtering": row_diagnostics.get("tool_filtering"),
                        "recovery_chain": row_diagnostics.get("recovery_chain"),
                        "intent_plan": row_diagnostics.get("intent_plan"),
                        "retry_events": row_diagnostics.get("retry_events"),
                        "partial_exit_reason": row_diagnostics.get(
                            "partial_exit_reason"
                        ),
                        "sync_rescue": row_diagnostics.get("sync_rescue"),
                        "contract_breach_type": row_diagnostics.get(
                            "contract_breach_type"
                        ),
                        "last_tool_name": row_diagnostics.get("last_tool_name"),
                        "interrupted_stage": row_diagnostics.get("interrupted_stage"),
                        "tool_loop_progress": row_diagnostics.get("tool_loop_progress"),
                        "turn_record": row_diagnostics.get("turn_record"),
                    }
                )
            )

        snapshot = {
            "conversation": {
                "id": detail.get("id", conversation_id),
                "tenant_id": detail.get("tenant_id", conversation.tenant_id),
                "agent_id": detail.get("agent_id", conversation.agent_id),
                "agent_name": detail.get("agent_name"),
                "user_id": detail.get("user_id", conversation.user_id),
                "owner_type": detail.get("owner_type", conversation.owner_type),
                "status": detail.get("status", conversation.status),
                "title": detail.get("title", conversation.title),
                "message_count": total_messages,
                "token_count": detail.get("token_count", conversation.token_count),
                "cost": float(detail.get("cost", conversation.cost or 0) or 0),
                "created_at": detail.get(
                    "created_at",
                    _format_cli_dt(conversation.created_at),
                ),
                "updated_at": detail.get(
                    "updated_at",
                    _format_cli_dt(conversation.updated_at),
                ),
            },
            "recent_messages": recent_messages,
            "keyword": keyword,
            "keyword_hits": keyword_hits,
            "recent_call_logs": recent_call_logs,
            "diagnostics": {
                "last_assistant_looks_like_textual_tool_call": bool(leaked_tool_names),
                "last_assistant_textual_tool_call_names": leaked_tool_names,
                "last_assistant_message_id": (last_assistant or {}).get("id"),
                "last_assistant_sequence": (last_assistant or {}).get("sequence"),
                "contract_breach_type": contract_breach_type,
                "tool_leak_detected": tool_leak_detected,
                "unfinished_intents": unfinished_intents,
                "recovered_via_retry": recovered_via_retry,
                "execution_path": execution_path,
                "intent_plan": intent_plan,
                "budget": budget or None,
                "budget_status": budget_status,
                "budget_exit_reason": budget_exit_reason,
                "candidate_tool_names": candidate_tool_names,
                "retry_events": retry_events,
                "partial_exit_reason": partial_exit_reason,
                "failure_kind": failure_kind,
                "final_output_source": final_output_source,
                "provider_events": provider_events,
                "turn_outcome": turn_outcome,
                "termination_reason": termination_reason,
                "protocol_path": protocol_path,
                "selected_tool_names": selected_tool_names,
                "selected_skill_names": selected_skill_names,
                "context_sources": context_sources,
                "fallback_history": fallback_history,
                "sync_rescue": sync_rescue,
                "should_record_call_log": should_record_call_log,
                "last_tool_name": last_tool_name,
                "interrupted_stage": interrupted_stage,
                "tool_loop_progress": tool_loop_progress,
                "turn_record": turn_record or None,
                "source": (
                    "assistant_turn_record"
                    if assistant_turn_record
                    else (
                        "call_log_turn_record"
                        if call_log_turn_record
                        else (
                            "assistant_metadata"
                            if assistant_metadata
                            else (
                                "conversation_detail"
                                if detail_context_diagnostics or detail_last_run_summary
                                else (
                                    "call_log"
                                    if latest_call_log_diagnostics
                                    else "none"
                                )
                            )
                        )
                    )
                ),
            },
        }
        return _apply_turn_flow_diagnostics_parity(
            snapshot,
            last_assistant=last_assistant,
        )


def _hydrate_ai_conversation_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        return {}

    hydrated = dict(snapshot)
    diagnostics = (
        dict(hydrated.get("diagnostics") or {})
        if isinstance(hydrated.get("diagnostics"), dict)
        else {}
    )
    recent_messages = (
        hydrated.get("recent_messages") or hydrated.get("message_list") or []
    )
    if not isinstance(recent_messages, list):
        recent_messages = []
    last_assistant = next(
        (
            item
            for item in reversed(recent_messages)
            if isinstance(item, dict) and item.get("role") == "assistant"
        ),
        None,
    )
    assistant_metadata = (
        dict((last_assistant or {}).get("metadata") or {})
        if isinstance((last_assistant or {}).get("metadata"), dict)
        else {}
    )
    assistant_context_diagnostics = (
        dict(assistant_metadata.get("context_diagnostics") or {})
        if isinstance(assistant_metadata.get("context_diagnostics"), dict)
        else {}
    )
    assistant_last_run_summary = (
        dict(assistant_metadata.get("last_run_summary") or {})
        if isinstance(assistant_metadata.get("last_run_summary"), dict)
        else {}
    )
    assistant_tool_planner = (
        dict(assistant_metadata.get("tool_planner") or {})
        if isinstance(assistant_metadata.get("tool_planner"), dict)
        else {}
    )
    assistant_context_tool_planner = (
        dict(assistant_context_diagnostics.get("tool_planner") or {})
        if isinstance(assistant_context_diagnostics.get("tool_planner"), dict)
        else {}
    )
    assistant_summary_tool_planner = (
        dict(assistant_last_run_summary.get("tool_planner") or {})
        if isinstance(assistant_last_run_summary.get("tool_planner"), dict)
        else {}
    )
    assistant_turn_record = (
        dict(assistant_metadata.get("turn_record") or {})
        if isinstance(assistant_metadata.get("turn_record"), dict)
        else {}
    )
    recent_call_logs = hydrated.get("recent_call_logs") or []
    if not isinstance(recent_call_logs, list):
        recent_call_logs = []
    recent_call_logs = [
        normalized
        for normalized in (
            _normalize_cli_call_log_row(item) for item in recent_call_logs
        )
        if normalized
    ]
    hydrated["recent_call_logs"] = recent_call_logs
    latest_call_log_diagnostics = next(
        (
            dict(item)
            for item in recent_call_logs
            if isinstance(item, dict)
            and any(
                item.get(key)
                for key in (
                    "turn_outcome",
                    "termination_reason",
                    "execution_path",
                    "budget_exit_reason",
                    "partial_exit_reason",
                    "tool_loop_progress",
                )
            )
        ),
        {},
    )
    call_log_turn_record = (
        dict(latest_call_log_diagnostics.get("turn_record") or {})
        if isinstance(latest_call_log_diagnostics.get("turn_record"), dict)
        else {}
    )

    def _first_string(*values: object) -> str | None:
        for value in values:
            text = _normalize_cli_optional_string(value)
            if text:
                return text
        return None

    def _first_dict(*values: object) -> dict:
        for value in values:
            if isinstance(value, dict) and value:
                return _normalize_cli_dict(value)
        return {}

    def _first_list_of_dicts(*values: object) -> list[dict] | None:
        for value in values:
            if not isinstance(value, list):
                continue
            normalized: list[dict] = []
            for item in value:
                payload = _normalize_cli_dict(item)
                if not payload:
                    continue
                normalized.append(payload)
            return normalized
        return None

    diagnostics["last_assistant_message_id"] = diagnostics.get(
        "last_assistant_message_id"
    ) or (last_assistant or {}).get("id")
    diagnostics["last_assistant_sequence"] = diagnostics.get(
        "last_assistant_sequence"
    ) or (last_assistant or {}).get("sequence")
    diagnostics["turn_record"] = (
        _first_dict(
            diagnostics.get("turn_record"),
            assistant_turn_record,
            call_log_turn_record,
        )
        or None
    )
    turn_record = (
        dict(diagnostics.get("turn_record") or {})
        if isinstance(diagnostics.get("turn_record"), dict)
        else {}
    )
    turn_record_metadata = (
        dict(turn_record.get("metadata") or {})
        if isinstance(turn_record.get("metadata"), dict)
        else {}
    )
    turn_record_diagnostics = (
        dict(turn_record_metadata.get("turn_diagnostics") or {})
        if isinstance(turn_record_metadata.get("turn_diagnostics"), dict)
        else {}
    )
    assistant_recovery = _normalize_cli_dict(assistant_metadata.get("recovery"))
    assistant_context_recovery = _normalize_cli_dict(
        assistant_context_diagnostics.get("recovery")
    )
    assistant_summary_recovery = _normalize_cli_dict(
        assistant_last_run_summary.get("recovery")
    )
    turn_record_routing = _normalize_cli_dict(turn_record_diagnostics.get("routing"))
    turn_record_recovery = _normalize_cli_dict(turn_record_diagnostics.get("recovery"))
    latest_call_log_recovery = _normalize_cli_dict(
        latest_call_log_diagnostics.get("recovery")
    )
    diagnostics["execution_path"] = _first_string(
        diagnostics.get("execution_path"),
        assistant_metadata.get("execution_path"),
        assistant_context_diagnostics.get("execution_path"),
        assistant_last_run_summary.get("execution_path"),
        assistant_tool_planner.get("execution_path"),
        assistant_context_tool_planner.get("execution_path"),
        assistant_summary_tool_planner.get("execution_path"),
        latest_call_log_diagnostics.get("execution_path"),
    )
    diagnostics["tool_planner"] = _first_dict(
        diagnostics.get("tool_planner"),
        assistant_tool_planner,
        assistant_context_tool_planner,
        assistant_summary_tool_planner,
        latest_call_log_diagnostics.get("tool_planner"),
    )
    diagnostics["path_decision"] = _first_dict(
        diagnostics.get("path_decision"),
        assistant_metadata.get("path_decision"),
        assistant_context_diagnostics.get("path_decision"),
        assistant_last_run_summary.get("path_decision"),
        turn_record.get("path_decision"),
        turn_record_diagnostics.get("path_decision"),
        latest_call_log_diagnostics.get("path_decision"),
    )
    diagnostics["capability_injection"] = _first_dict(
        diagnostics.get("capability_injection"),
        assistant_metadata.get("capability_injection"),
        assistant_metadata.get("capability_injection_decision"),
        assistant_context_diagnostics.get("capability_injection"),
        assistant_context_diagnostics.get("capability_injection_decision"),
        assistant_last_run_summary.get("capability_injection"),
        assistant_last_run_summary.get("capability_injection_decision"),
        turn_record.get("capability_injection"),
        turn_record.get("capability_injection_decision"),
        turn_record_diagnostics.get("capability_injection"),
        turn_record_diagnostics.get("capability_injection_decision"),
        latest_call_log_diagnostics.get("capability_injection"),
        latest_call_log_diagnostics.get("capability_injection_decision"),
    )
    diagnostics["tool_filtering"] = _first_dict(
        diagnostics.get("tool_filtering"),
        assistant_metadata.get("tool_filtering"),
        assistant_context_diagnostics.get("tool_filtering"),
        assistant_last_run_summary.get("tool_filtering"),
        turn_record.get("tool_filtering"),
        turn_record_diagnostics.get("tool_filtering"),
        turn_record_routing.get("tool_filtering"),
        latest_call_log_diagnostics.get("tool_filtering"),
    )
    diagnostics["recovery_chain"] = _first_list_of_dicts(
        diagnostics.get("recovery_chain"),
        assistant_metadata.get("recovery_chain"),
        assistant_recovery.get("recovery_chain"),
        assistant_context_diagnostics.get("recovery_chain"),
        assistant_context_recovery.get("recovery_chain"),
        assistant_last_run_summary.get("recovery_chain"),
        assistant_summary_recovery.get("recovery_chain"),
        turn_record.get("recovery_chain"),
        turn_record_diagnostics.get("recovery_chain"),
        turn_record_recovery.get("recovery_chain"),
        latest_call_log_diagnostics.get("recovery_chain"),
        latest_call_log_recovery.get("recovery_chain"),
    )
    diagnostics["intent_plan"] = (
        _normalize_cli_intent_plan(diagnostics.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_metadata.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_context_diagnostics.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_last_run_summary.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_tool_planner.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_context_tool_planner.get("intent_plan"))
        or _normalize_cli_intent_plan(assistant_summary_tool_planner.get("intent_plan"))
        or _normalize_cli_intent_plan(latest_call_log_diagnostics.get("intent_plan"))
    )
    diagnostics["budget"] = (
        _normalize_cli_dict(diagnostics.get("budget"))
        or _normalize_cli_dict(assistant_metadata.get("budget"))
        or _normalize_cli_dict(assistant_context_diagnostics.get("budget"))
        or _normalize_cli_dict(assistant_last_run_summary.get("budget"))
        or _normalize_cli_dict(latest_call_log_diagnostics.get("budget"))
        or None
    )
    diagnostics["budget_status"] = _first_string(
        diagnostics.get("budget_status"),
        (diagnostics.get("budget") or {}).get("status")
        if isinstance(diagnostics.get("budget"), dict)
        else None,
        assistant_context_diagnostics.get("budget_status"),
        assistant_last_run_summary.get("budget_status"),
        latest_call_log_diagnostics.get("budget_status"),
    )
    diagnostics["turn_outcome"] = _first_string(
        diagnostics.get("turn_outcome"),
        assistant_metadata.get("turn_outcome"),
        assistant_context_diagnostics.get("turn_outcome"),
        assistant_last_run_summary.get("turn_outcome"),
        latest_call_log_diagnostics.get("turn_outcome"),
    )
    diagnostics["termination_reason"] = _first_string(
        diagnostics.get("termination_reason"),
        assistant_metadata.get("termination_reason"),
        assistant_context_diagnostics.get("termination_reason"),
        assistant_last_run_summary.get("termination_reason"),
        assistant_last_run_summary.get("completion_reason"),
        assistant_metadata.get("completion_reason"),
        latest_call_log_diagnostics.get("termination_reason"),
    )
    diagnostics["budget_exit_reason"] = _first_string(
        diagnostics.get("budget_exit_reason"),
        (diagnostics.get("budget") or {}).get("exit_reason")
        if isinstance(diagnostics.get("budget"), dict)
        else None,
        assistant_context_diagnostics.get("budget_exit_reason"),
        assistant_last_run_summary.get("budget_exit_reason"),
        (assistant_context_diagnostics.get("tool_loop_progress") or {}).get(
            "budget_exit_reason"
        )
        if isinstance(assistant_context_diagnostics.get("tool_loop_progress"), dict)
        else None,
        (assistant_last_run_summary.get("tool_loop_progress") or {}).get(
            "budget_exit_reason"
        )
        if isinstance(assistant_last_run_summary.get("tool_loop_progress"), dict)
        else None,
        latest_call_log_diagnostics.get("budget_exit_reason"),
        diagnostics.get("termination_reason")
        if str(diagnostics.get("termination_reason") or "").endswith("_budget_exceeded")
        else None,
    )
    budget_projection = derive_budget_projection(
        budget=diagnostics.get("budget"),
        budget_status=diagnostics.get("budget_status"),
        budget_exit_reason=diagnostics.get("budget_exit_reason"),
        termination_reason=diagnostics.get("termination_reason"),
    )
    diagnostics["budget"] = budget_projection.get("budget") or diagnostics.get("budget")
    diagnostics["budget_status"] = budget_projection.get(
        "budget_status"
    ) or diagnostics.get("budget_status")
    diagnostics["budget_exit_reason"] = budget_projection.get(
        "budget_exit_reason"
    ) or diagnostics.get("budget_exit_reason")
    diagnostics["failure_kind"] = _first_string(
        diagnostics.get("failure_kind"),
        assistant_metadata.get("failure_kind"),
        assistant_context_diagnostics.get("failure_kind"),
        assistant_last_run_summary.get("failure_kind"),
        latest_call_log_diagnostics.get("failure_kind"),
    )
    diagnostics["final_output_source"] = _first_string(
        diagnostics.get("final_output_source"),
        assistant_metadata.get("final_output_source"),
        assistant_context_diagnostics.get("final_output_source"),
        assistant_last_run_summary.get("final_output_source"),
        latest_call_log_diagnostics.get("final_output_source"),
    )
    diagnostics["partial_exit_reason"] = _first_string(
        diagnostics.get("partial_exit_reason"),
        assistant_metadata.get("partial_exit_reason"),
        assistant_context_diagnostics.get("partial_exit_reason"),
        assistant_last_run_summary.get("partial_exit_reason"),
        latest_call_log_diagnostics.get("partial_exit_reason"),
        diagnostics.get("budget_exit_reason"),
    )
    diagnostics["tool_loop_progress"] = _first_dict(
        diagnostics.get("tool_loop_progress"),
        assistant_context_diagnostics.get("tool_loop_progress"),
        assistant_last_run_summary.get("tool_loop_progress"),
        latest_call_log_diagnostics.get("tool_loop_progress"),
    )
    diagnostics["contract_breach_type"] = _first_string(
        diagnostics.get("contract_breach_type"),
        (diagnostics.get("turn_record") or {})
        .get("metadata", {})
        .get("contract_breach_type")
        if isinstance((diagnostics.get("turn_record") or {}).get("metadata"), dict)
        else None,
        assistant_context_diagnostics.get("contract_breach_type"),
        assistant_last_run_summary.get("contract_breach_type"),
        latest_call_log_diagnostics.get("contract_breach_type"),
    )
    diagnostics["tool_leak_detected"] = bool(
        diagnostics.get("tool_leak_detected")
        or (
            (diagnostics.get("turn_record") or {})
            .get("metadata", {})
            .get("tool_leak_detected")
            if isinstance((diagnostics.get("turn_record") or {}).get("metadata"), dict)
            else False
        )
        or assistant_context_diagnostics.get("tool_leak_detected")
        or assistant_last_run_summary.get("tool_leak_detected")
        or latest_call_log_diagnostics.get("tool_leak_detected")
    )
    diagnostics["unfinished_intents"] = (
        _normalize_cli_string_list(diagnostics.get("unfinished_intents"))
        or _normalize_cli_string_list(
            (diagnostics.get("turn_record") or {})
            .get("metadata", {})
            .get("unfinished_intents")
            if isinstance((diagnostics.get("turn_record") or {}).get("metadata"), dict)
            else None
        )
        or _normalize_cli_string_list(
            assistant_context_diagnostics.get("unfinished_intents")
        )
        or _normalize_cli_string_list(
            assistant_last_run_summary.get("unfinished_intents")
        )
        or _normalize_cli_string_list(
            latest_call_log_diagnostics.get("unfinished_intents")
        )
    )
    diagnostics["turn_events"] = next(
        (
            list(value)
            for value in (
                diagnostics.get("turn_events"),
                assistant_metadata.get("turn_events"),
                assistant_context_diagnostics.get("turn_events"),
                assistant_last_run_summary.get("turn_events"),
                latest_call_log_diagnostics.get("turn_events"),
            )
            if isinstance(value, list) and value
        ),
        [],
    )
    diagnostics["last_assistant_textual_tool_call_names"] = (
        _normalize_cli_string_list(
            diagnostics.get("last_assistant_textual_tool_call_names")
        )
        or _normalize_cli_string_list(
            (diagnostics.get("turn_record") or {})
            .get("metadata", {})
            .get("leaked_tool_names")
            if isinstance((diagnostics.get("turn_record") or {}).get("metadata"), dict)
            else None
        )
        or _normalize_cli_string_list(
            assistant_context_diagnostics.get("leaked_tool_names")
        )
        or _normalize_cli_string_list(
            assistant_last_run_summary.get("leaked_tool_names")
        )
        or _normalize_cli_string_list(
            latest_call_log_diagnostics.get("leaked_tool_names")
        )
    )
    diagnostics["last_assistant_looks_like_textual_tool_call"] = bool(
        diagnostics.get("last_assistant_looks_like_textual_tool_call")
        or diagnostics.get("tool_leak_detected")
        or diagnostics.get("last_assistant_textual_tool_call_names")
    )
    diagnostics["recovered_via_retry"] = next(
        (
            parsed
            for parsed in (
                _normalize_cli_bool(diagnostics.get("recovered_via_retry")),
                _normalize_cli_bool(
                    (diagnostics.get("turn_record") or {})
                    .get("metadata", {})
                    .get("recovered_via_retry")
                    if isinstance(
                        (diagnostics.get("turn_record") or {}).get("metadata"), dict
                    )
                    else None
                ),
                _normalize_cli_bool(
                    assistant_context_diagnostics.get("recovered_via_retry")
                ),
                _normalize_cli_bool(
                    assistant_last_run_summary.get("recovered_via_retry")
                ),
                _normalize_cli_bool(
                    latest_call_log_diagnostics.get("recovered_via_retry")
                ),
            )
            if parsed is not None
        ),
        None,
    )
    diagnostics["source"] = _first_string(
        diagnostics.get("source"),
        "assistant_turn_record" if assistant_turn_record else None,
        "call_log_turn_record" if call_log_turn_record else None,
        "assistant_metadata" if assistant_metadata else None,
        "call_log" if latest_call_log_diagnostics else None,
        "none",
    )
    hydrated["diagnostics"] = diagnostics
    return _apply_turn_flow_diagnostics_parity(
        hydrated,
        last_assistant=last_assistant,
    )
