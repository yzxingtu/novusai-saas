"""
Monitoring read-model projector utilities.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.identity import resolve_identity_display_role_name
from app.core.identity_snapshot import snapshot_has_key, snapshot_value
from app.schemas.ai.monitoring import MonitoringActorInfo
from app.services.ai.conversation_diagnostics_projector_support import (
    normalize_turn_skill_activation_payload,
    resolve_live_selected_name_list,
)
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.turn_failure_normalizer import (
    derive_budget_projection,
    resolve_failure_projection,
)


class MonitoringReadModelProjector:
    @staticmethod
    def safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def safe_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def normalize_optional_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        return None

    @staticmethod
    def normalize_fallback_history(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            from_protocol = ConversationDiagnosticsProjector.to_non_empty_str(
                item.get("from_protocol")
            )
            to_protocol = ConversationDiagnosticsProjector.to_non_empty_str(
                item.get("to_protocol")
            )
            reason = ConversationDiagnosticsProjector.to_non_empty_str(item.get("reason"))
            if not (from_protocol or to_protocol or reason):
                continue
            metadata = item.get("metadata")
            normalized.append(
                {
                    "from_protocol": from_protocol,
                    "to_protocol": to_protocol,
                    "reason": reason,
                    "recovered": bool(item.get("recovered", False)),
                    "metadata": dict(metadata) if isinstance(metadata, dict) else {},
                }
            )
        return normalized

    @classmethod
    def _resolve_turn_flow_payload(
        cls,
        *,
        request_metadata: dict[str, Any],
        request_payload: dict[str, Any],
        diagnostics: dict[str, Any],
        turn_record: dict[str, Any],
        turn_record_diagnostics: dict[str, Any],
        turn_outcome: str | None,
        termination_reason: str | None,
        failure_kind: str | None,
        final_output_source: str | None,
    ) -> dict[str, Any] | None:
        def _normalize(
            raw_turn_flow: Any,
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any] | None:
            if not isinstance(raw_turn_flow, dict):
                return None
            return ConversationTurnFlowProjector.normalize_turn_flow(
                raw_turn_flow,
                turn_outcome=turn_outcome,
                completion_reason=termination_reason,
                interrupted=bool(
                    diagnostics.get("interrupted") or diagnostics.get("partial")
                ),
                failure_kind=failure_kind,
                final_output_source=final_output_source,
                metadata=metadata,
            )

        for raw_turn_flow, metadata in (
            (diagnostics.get("turn_flow"), diagnostics),
            (turn_record.get("turn_flow"), turn_record),
            (turn_record_diagnostics.get("turn_flow"), turn_record_diagnostics),
            (request_payload.get("turn_flow"), request_payload),
            (request_metadata.get("turn_flow"), request_metadata),
        ):
            projected = _normalize(raw_turn_flow, metadata if isinstance(metadata, dict) else None)
            if projected is not None:
                return projected
        return None

    @classmethod
    def extract_call_trace_diagnostics(cls, request_metadata: Any) -> dict[str, Any]:
        if not isinstance(request_metadata, dict):
            return {}
        diagnostics = (
            dict(request_metadata.get("turn_diagnostics") or {})
            if isinstance(request_metadata.get("turn_diagnostics"), dict)
            else {}
        )
        request_payload = (
            dict(request_metadata.get("request") or {})
            if isinstance(request_metadata.get("request"), dict)
            else {}
        )
        turn_record = (
            ConversationDiagnosticsProjector.normalize_turn_record_payload(
                diagnostics.get("turn_record")
            )
            or ConversationDiagnosticsProjector.normalize_turn_record_payload(
                request_payload.get("turn_record")
            )
            or {}
        )
        turn_record_metadata = (
            dict(turn_record.get("metadata") or {})
            if isinstance(turn_record.get("metadata"), dict)
            else {}
        )
        turn_record_diagnostics = (
            ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record_metadata.get("turn_diagnostics")
            )
            or {}
        )
        tool_planner = (
            ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record.get("tool_planner")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                diagnostics.get("tool_planner")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record_diagnostics.get("tool_planner")
            )
            or {}
        )
        routing = (
            ConversationDiagnosticsProjector.normalize_json_dict(
                diagnostics.get("routing")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record.get("routing")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record_diagnostics.get("routing")
            )
            or {}
        )
        recovery = (
            ConversationDiagnosticsProjector.normalize_json_dict(
                diagnostics.get("recovery")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record.get("recovery")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record_diagnostics.get("recovery")
            )
            or {}
        )
        failures = (
            ConversationDiagnosticsProjector.normalize_json_dict(
                diagnostics.get("failures")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record.get("failures")
            )
            or ConversationDiagnosticsProjector.normalize_json_dict(
                turn_record_diagnostics.get("failures")
            )
            or {}
        )
        budget = ConversationDiagnosticsProjector.normalize_json_dict(
            diagnostics.get("budget") or turn_record.get("budget")
        )
        tool_loop_progress = (
            dict(turn_record.get("tool_loop_progress") or {})
            if isinstance(turn_record.get("tool_loop_progress"), dict)
            else (
                dict(diagnostics.get("tool_loop_progress") or {})
                if isinstance(diagnostics.get("tool_loop_progress"), dict)
                else None
            )
        )
        raw_budget_status = ConversationDiagnosticsProjector.to_non_empty_str(
            (budget or {}).get("status")
            or turn_record.get("budget_status")
            or diagnostics.get("budget_status")
        )
        raw_budget_exit_reason = ConversationDiagnosticsProjector.to_non_empty_str(
            (budget or {}).get("exit_reason")
            or turn_record.get("budget_exit_reason")
            or diagnostics.get("budget_exit_reason")
            or ((tool_loop_progress or {}).get("budget_exit_reason"))
        )
        termination_reason = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record.get("termination_reason")
            or diagnostics.get("termination_reason")
            or diagnostics.get("completion_reason")
            or turn_record_diagnostics.get("termination_reason")
        )
        turn_outcome = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record.get("turn_outcome")
            or diagnostics.get("turn_outcome")
            or turn_record_diagnostics.get("turn_outcome")
        )
        if not turn_outcome:
            if (
                bool(diagnostics.get("partial"))
                or bool(diagnostics.get("interrupted"))
                or termination_reason == "interrupted"
            ):
                turn_outcome = "partial"
            elif termination_reason in {
                "error",
                "failed",
                "tool_error",
                "tool_round_failed",
            }:
                turn_outcome = "failed"
        raw_failure_kind = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record.get("failure_kind")
            or failures.get("failure_kind")
            or diagnostics.get("failure_kind")
        )
        raw_final_output_source = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record.get("final_output_source")
            or diagnostics.get("final_output_source")
            or turn_record_diagnostics.get("final_output_source")
        )
        contract_breach_type = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record_metadata.get("contract_breach_type")
            or diagnostics.get("contract_breach_type")
            or turn_record_diagnostics.get("contract_breach_type")
        )
        unfinished_intents = ConversationDiagnosticsProjector.normalize_string_list(
            turn_record_metadata.get("unfinished_intents")
            or turn_record.get("unfinished_intents")
            or recovery.get("unfinished_intents")
            or diagnostics.get("unfinished_intents")
        )
        budget_projection = derive_budget_projection(
            budget=budget,
            budget_status=raw_budget_status,
            budget_exit_reason=raw_budget_exit_reason,
            termination_reason=termination_reason,
        )
        budget = ConversationDiagnosticsProjector.normalize_json_dict(
            budget_projection.get("budget")
        ) or budget
        turn_flow = cls._resolve_turn_flow_payload(
            request_metadata=request_metadata,
            request_payload=request_payload,
            diagnostics=diagnostics,
            turn_record=turn_record,
            turn_record_diagnostics=turn_record_diagnostics,
            turn_outcome=turn_outcome,
            termination_reason=termination_reason,
            failure_kind=raw_failure_kind,
            final_output_source=raw_final_output_source,
        )
        normalized_failure = resolve_failure_projection(
            diagnostics={
                "turn_outcome": turn_outcome,
                "conversation_outcome": ConversationDiagnosticsProjector.to_non_empty_str(
                    turn_record.get("conversation_outcome")
                    or diagnostics.get("conversation_outcome")
                    or turn_record_diagnostics.get("conversation_outcome")
                    or turn_outcome
                ),
                "termination_reason": termination_reason,
                "failure_kind": raw_failure_kind,
                "budget": budget or None,
                "budget_exit_reason": budget_projection.get("budget_exit_reason")
                or raw_budget_exit_reason,
                "final_output_source": raw_final_output_source,
                "contract_breach_type": contract_breach_type,
                "assistant_claimed_tool_call_without_tool_event": bool(
                    turn_record_metadata.get(
                        "assistant_claimed_tool_call_without_tool_event"
                    )
                    or turn_record.get(
                        "assistant_claimed_tool_call_without_tool_event"
                    )
                    or diagnostics.get(
                        "assistant_claimed_tool_call_without_tool_event"
                    )
                    or turn_record_diagnostics.get(
                        "assistant_claimed_tool_call_without_tool_event"
                    )
                ),
                "unfinished_intents": unfinished_intents,
            },
            turn_flow=turn_flow,
        )
        turn_outcome = (
            ConversationDiagnosticsProjector.to_non_empty_str(
                normalized_failure.get("turn_outcome")
            )
            or turn_outcome
        )
        termination_reason = (
            ConversationDiagnosticsProjector.to_non_empty_str(
                normalized_failure.get("termination_reason")
            )
            or termination_reason
        )
        conversation_outcome = ConversationDiagnosticsProjector.to_non_empty_str(
            turn_record.get("conversation_outcome")
            or diagnostics.get("conversation_outcome")
            or turn_record_diagnostics.get("conversation_outcome")
            or turn_outcome
        )
        failure_kind = (
            ConversationDiagnosticsProjector.to_non_empty_str(
                normalized_failure.get("failure_kind")
            )
            or raw_failure_kind
        )
        final_output_source = (
            ConversationDiagnosticsProjector.to_non_empty_str(
                normalized_failure.get("final_output_source")
            )
            or raw_final_output_source
        )
        budget_status = ConversationDiagnosticsProjector.to_non_empty_str(
            budget_projection.get("budget_status")
        )
        budget_exit_reason = (
            ConversationDiagnosticsProjector.to_non_empty_str(
                normalized_failure.get("budget_exit_reason")
            )
            or ConversationDiagnosticsProjector.to_non_empty_str(
                budget_projection.get("budget_exit_reason")
            )
            or raw_budget_exit_reason
        )
        conversation_outcome = ConversationDiagnosticsProjector.to_non_empty_str(
            conversation_outcome or turn_outcome
        )
        turn_skill_activation = normalize_turn_skill_activation_payload(
            turn_record.get("turn_skill_activation")
            or diagnostics.get("turn_skill_activation")
            or turn_record_diagnostics.get("turn_skill_activation")
        )
        selected_tool_names, _selected_tools_explicit = resolve_live_selected_name_list(
            "selected_tool_names",
            turn_record,
            diagnostics,
            turn_record_diagnostics,
            turn_skill_activation=turn_skill_activation,
        )
        selected_skill_names, _selected_skills_explicit = resolve_live_selected_name_list(
            "selected_skill_names",
            turn_record,
            diagnostics,
            turn_record_diagnostics,
            turn_skill_activation=turn_skill_activation,
        )

        return {
            "turn_outcome": turn_outcome,
            "conversation_outcome": conversation_outcome,
            "termination_reason": termination_reason,
            "protocol_path": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("protocol_path") or diagnostics.get("protocol_path")
            ),
            "tool_planner": tool_planner or None,
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "execution_path": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("execution_path")
                or diagnostics.get("execution_path")
                or turn_record_diagnostics.get("execution_path")
            ),
            "active_intent_id": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("active_intent_id")
                or diagnostics.get("active_intent_id")
                or turn_record_diagnostics.get("active_intent_id")
            ),
            "continuation_source": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("continuation_source")
                or diagnostics.get("continuation_source")
                or turn_record_diagnostics.get("continuation_source")
            ),
            "intent_plan": ConversationDiagnosticsProjector.normalize_intent_plan(
                turn_record.get("intent_plan")
                or diagnostics.get("intent_plan")
                or turn_record_diagnostics.get("intent_plan")
            ),
            "budget": budget or None,
            "budget_status": budget_status,
            "budget_exit_reason": budget_exit_reason,
            "final_output_source": final_output_source,
            "candidate_tool_names": ConversationDiagnosticsProjector.normalize_string_list(
                turn_record.get("candidate_tool_names")
                or routing.get("candidate_tool_names")
                or diagnostics.get("candidate_tool_names")
            ),
            "context_sources": ConversationDiagnosticsProjector.normalize_context_sources(
                turn_record.get("context_sources") or diagnostics.get("context_sources")
            ),
            "fallback_history": cls.normalize_fallback_history(
                turn_record.get("fallback_history")
                or diagnostics.get("fallback_history")
            ),
            "retry_events": ConversationDiagnosticsProjector.normalize_retry_events(
                turn_record.get("retry_events")
                or recovery.get("retry_events")
                or diagnostics.get("retry_events")
            ),
            "partial_exit_reason": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("partial_exit_reason")
                or recovery.get("partial_exit_reason")
                or diagnostics.get("partial_exit_reason")
            ),
            "failure_kind": failure_kind,
            "provider_events": ConversationDiagnosticsProjector.normalize_provider_events(
                turn_record.get("provider_events")
                or failures.get("provider_events")
                or diagnostics.get("provider_events")
            ),
            "sync_rescue": next(
                (
                    parsed
                    for parsed in (
                        cls.normalize_optional_bool(
                            turn_record_metadata.get("sync_rescue")
                        ),
                        cls.normalize_optional_bool(turn_record.get("sync_rescue")),
                        cls.normalize_optional_bool(diagnostics.get("sync_rescue")),
                    )
                    if parsed is not None
                ),
                None,
            ),
            "should_record_call_log": next(
                (
                    parsed
                    for parsed in (
                        cls.normalize_optional_bool(
                            turn_record_metadata.get("should_record_call_log")
                        ),
                        cls.normalize_optional_bool(
                            turn_record.get("should_record_call_log")
                        ),
                        cls.normalize_optional_bool(
                            diagnostics.get("should_record_call_log")
                        ),
                    )
                    if parsed is not None
                ),
                None,
            ),
            "contract_breach_type": contract_breach_type,
            "tool_leak_detected": bool(
                turn_record_metadata.get("tool_leak_detected")
                or diagnostics.get("tool_leak_detected")
            ),
            "assistant_claimed_tool_call_without_tool_event": bool(
                turn_record_metadata.get(
                    "assistant_claimed_tool_call_without_tool_event"
                )
                or turn_record.get(
                    "assistant_claimed_tool_call_without_tool_event"
                )
                or diagnostics.get(
                    "assistant_claimed_tool_call_without_tool_event"
                )
                or turn_record_diagnostics.get(
                    "assistant_claimed_tool_call_without_tool_event"
                )
            ),
            "unfinished_intents": unfinished_intents,
            "leaked_tool_names": ConversationDiagnosticsProjector.normalize_string_list(
                turn_record_metadata.get("leaked_tool_names")
                or diagnostics.get("leaked_tool_names")
            ),
            "recovered_via_retry": next(
                (
                    parsed
                    for parsed in (
                        cls.normalize_optional_bool(
                            turn_record_metadata.get("recovered_via_retry")
                        ),
                        cls.normalize_optional_bool(
                            turn_record.get("recovered_via_retry")
                        ),
                        cls.normalize_optional_bool(
                            diagnostics.get("recovered_via_retry")
                        ),
                    )
                    if parsed is not None
                ),
                None,
            ),
            "last_tool_name": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("last_tool_name") or diagnostics.get("last_tool_name")
            ),
            "last_page_key": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("last_page_key") or diagnostics.get("last_page_key")
            ),
            "last_page_op": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("last_page_op") or diagnostics.get("last_page_op")
            ),
            "interrupted_stage": ConversationDiagnosticsProjector.to_non_empty_str(
                turn_record.get("interrupted_stage")
                or diagnostics.get("interrupted_stage")
            ),
            "tool_loop_progress": tool_loop_progress,
            "turn_record": turn_record or None,
        }

    @staticmethod
    def format_dt(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc).isoformat()
        return value.isoformat()

    @staticmethod
    def extract_caller_snapshot(request_metadata: Any) -> dict[str, Any]:
        if not isinstance(request_metadata, dict):
            return {}
        snapshot = request_metadata.get("caller_snapshot")
        if isinstance(snapshot, dict):
            return dict(snapshot)
        return {}

    @classmethod
    def resolve_snapshot_display_role_name(
        cls,
        snapshot: dict[str, Any] | None,
        live_actor: MonitoringActorInfo | None = None,
    ) -> str | None:
        if snapshot_has_key(snapshot, "display_role_name"):
            return snapshot.get("display_role_name")
        if snapshot_has_key(snapshot, "role_name") or snapshot_has_key(
            snapshot,
            "org_node_name",
        ):
            return resolve_identity_display_role_name(
                snapshot_value(snapshot, "role_name"),
                snapshot_value(snapshot, "org_node_name"),
            )
        return live_actor.display_role_name if live_actor else None

    @classmethod
    def build_actor_info_from_snapshot(
        cls,
        snapshot: dict[str, Any] | None,
        *,
        platform_usage_tenant_name: str,
        actor_id: int | None = None,
        actor_type: str | None = None,
        tenant_id: int | None = None,
        tenant_name: str | None = None,
        live_actor: MonitoringActorInfo | None = None,
    ) -> MonitoringActorInfo | None:
        if not snapshot:
            return live_actor

        resolved_type = snapshot_value(
            snapshot,
            "user_type",
            live_actor.type if live_actor else actor_type,
        )
        resolved_tenant_id = (
            tenant_id
            if tenant_id is not None
            else live_actor.tenant_id
            if live_actor
            else None
        )
        if resolved_tenant_id is None and resolved_type == "platform_admin":
            resolved_tenant_id = PLATFORM_TENANT_ID

        resolved_tenant_name = (
            tenant_name
            if tenant_name is not None
            else live_actor.tenant_name
            if live_actor
            else None
        )
        if resolved_tenant_name is None and resolved_type == "platform_admin":
            resolved_tenant_name = platform_usage_tenant_name

        display_name = snapshot_value(
            snapshot,
            "display_name",
            live_actor.display_name if live_actor else None,
        )
        username = snapshot_value(
            snapshot,
            "username",
            live_actor.username if live_actor else None,
        )
        nickname = snapshot_value(
            snapshot,
            "nickname",
            live_actor.nickname if live_actor else None,
        )
        if not display_name:
            display_name = nickname or username or (
                live_actor.display_name if live_actor else None
            )

        return MonitoringActorInfo(
            id=snapshot_value(snapshot, "user_id", live_actor.id if live_actor else actor_id),
            type=resolved_type,
            display_name=display_name,
            username=username,
            nickname=nickname,
            avatar=snapshot_value(
                snapshot,
                "avatar",
                live_actor.avatar if live_actor else None,
            ),
            tenant_id=resolved_tenant_id,
            tenant_name=resolved_tenant_name,
            org_node_id=snapshot_value(
                snapshot,
                "org_node_id",
                live_actor.org_node_id if live_actor else None,
            ),
            org_node_name=snapshot_value(
                snapshot,
                "org_node_name",
                live_actor.org_node_name if live_actor else None,
            ),
            role_name=snapshot_value(
                snapshot,
                "role_name",
                live_actor.role_name if live_actor else None,
            ),
            display_role_name=cls.resolve_snapshot_display_role_name(
                snapshot,
                live_actor,
            ),
            is_active=snapshot_value(
                snapshot,
                "is_active",
                live_actor.is_active if live_actor else None,
            ),
            is_owner=snapshot_value(
                snapshot,
                "is_owner",
                live_actor.is_owner if live_actor else None,
            ),
            is_leader=snapshot_value(
                snapshot,
                "is_leader",
                live_actor.is_leader if live_actor else None,
            ),
        )
