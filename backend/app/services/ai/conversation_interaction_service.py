"""
Conversation interaction helpers extracted from the main ConversationService.

This module owns the logic for persisting user confirmations, consents,
and interaction metadata so that the facade can remain thin.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.core.logging import LogManager
from app.enums.agent import ActionLevelEnum, MessageRoleEnum
from app.enums.execution import (
    ExecutionDecisionScopeEnum,
    ExecutionDecisionStatusEnum,
    ExecutionDecisionSubjectEnum,
    ExecutionDecisionTypeEnum,
)
from app.models.ai.agent_conversation import AgentConversation
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.services.ai.action_log_service import resolve_action_level, write_ai_action_log
from app.services.ai.execution_decision_service import ExecutionDecisionService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)

logger = LogManager.get_logger("ai.conversation_interaction_service")


class ConversationInteractionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        message_repo: ConversationMessageRepository,
        memory_tenant_id: int,
        decision_service_cls: type[ExecutionDecisionService] = ExecutionDecisionService,
        trust_policy_service_cls: type[ExecutionTrustPolicyService] = ExecutionTrustPolicyService,
        write_ai_action_log_fn=write_ai_action_log,
        resolve_action_level_fn=resolve_action_level,
    ) -> None:
        self.db = db
        self.message_repo = message_repo
        self.memory_tenant_id = memory_tenant_id
        self.decision_service_cls = decision_service_cls
        self.trust_policy_service_cls = trust_policy_service_cls
        self.write_ai_action_log_fn = write_ai_action_log_fn
        self.resolve_action_level_fn = resolve_action_level_fn

    async def update_last_assistant_interaction_state(
        self,
        *,
        conversation: AgentConversation,
        updates: list[dict[str, Any]],
        user_id: int | None = None,
        owner_type: str | None = None,
        interaction_mode_requested: str | None = None,
        interaction_mode_effective: str | None = None,
        interaction_mode_downgrade_reason: str | None = None,
    ) -> int:
        if not updates:
            return 0

        messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation.id,
            n=50,
        )
        assistant_messages = [
            msg
            for msg in reversed(messages)
            if msg.role == MessageRoleEnum.ASSISTANT.value
        ]
        if not assistant_messages:
            return 0

        updated = 0
        seen_ids: set[int] = set()
        decision_service = self.decision_service_cls(
            self.db,
            self.memory_tenant_id,
        )

        def _match_action_buttons(
            metadata: dict[str, Any],
            value: str | None,
        ) -> bool:
            buttons = metadata.get("action_buttons")
            if not isinstance(buttons, list) or not value:
                return False
            return any(
                isinstance(item, dict) and item.get("value") == value
                for item in buttons
            )

        def _match_pending_confirmation(
            metadata: dict[str, Any],
            tool_calls: list | None,
            action: str | None,
            table: str | None,
        ) -> bool:
            pending = metadata.get("pending_confirmation")
            if isinstance(pending, dict):
                if action and pending.get("action") not in (None, action):
                    return False
                return not (table and pending.get("table") not in (None, table))
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_confirmation")
                    if not isinstance(nested, dict):
                        continue
                    if action and nested.get("action") not in (None, action):
                        continue
                    if table and nested.get("table") not in (None, table):
                        continue
                    return True
            return False

        def _find_pending_confirmation_evidence(
            metadata: dict[str, Any],
            tool_calls: list | None,
            action: str | None,
            table: str | None,
        ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            pending = metadata.get("pending_confirmation")
            if isinstance(pending, dict):
                if action and pending.get("action") not in (None, action):
                    return None, None
                if table and pending.get("table") not in (None, table):
                    return None, None
                return dict(pending), None
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_confirmation")
                    if not isinstance(nested, dict):
                        continue
                    if action and nested.get("action") not in (None, action):
                        continue
                    if table and nested.get("table") not in (None, table):
                        continue
                    return dict(nested), dict(tc)
            return None, None

        def _match_pending_consent(
            metadata: dict[str, Any],
            tool_calls: list | None,
            tool_name: str | None,
        ) -> bool:
            pending = metadata.get("pending_consent")
            if isinstance(pending, dict):
                return not (
                    tool_name and pending.get("tool_name") not in (None, tool_name)
                )
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_consent")
                    if not isinstance(nested, dict):
                        continue
                    if tool_name and nested.get("tool_name") not in (None, tool_name):
                        continue
                    return True
            return False

        def _find_pending_consent_evidence(
            metadata: dict[str, Any],
            tool_calls: list | None,
            tool_name: str | None,
        ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            pending = metadata.get("pending_consent")
            if isinstance(pending, dict):
                if tool_name and pending.get("tool_name") not in (None, tool_name):
                    return None, None
                return dict(pending), None
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    nested = tc.get("pending_consent")
                    if not isinstance(nested, dict):
                        continue
                    if tool_name and nested.get("tool_name") not in (None, tool_name):
                        continue
                    return dict(nested), dict(tc)
            return None, None

        for raw_update in updates:
            kind = str(raw_update.get("kind") or "")
            if not kind:
                continue
            for msg in assistant_messages:
                metadata = dict(msg.metadata_ or {})
                tool_calls = [
                    dict(tc) for tc in (msg.tool_calls or []) if isinstance(tc, dict)
                ]
                decision_payload: dict[str, Any] | None = None

                matched = False
                if kind == "action_buttons":
                    matched = _match_action_buttons(metadata, raw_update.get("value"))
                    if matched:
                        metadata["action_buttons_used"] = True
                elif kind == "pending_confirmation":
                    pending_evidence, matched_tool_call = _find_pending_confirmation_evidence(
                        metadata,
                        tool_calls,
                        raw_update.get("action"),
                        raw_update.get("table"),
                    )
                    matched = _match_pending_confirmation(
                        metadata,
                        tool_calls,
                        raw_update.get("action"),
                        raw_update.get("table"),
                    )
                    if matched:
                        pending = dict(metadata.get("pending_confirmation") or {})
                        pending["resolved"] = True
                        pending["rejected"] = bool(raw_update.get("rejected"))
                        metadata["pending_confirmation"] = pending
                        for tc in tool_calls:
                            nested = tc.get("pending_confirmation")
                            if isinstance(nested, dict):
                                next_nested = dict(nested)
                                next_nested["resolved"] = True
                                next_nested["rejected"] = bool(raw_update.get("rejected"))
                                tc["pending_confirmation"] = next_nested
                        action_name = str(
                            raw_update.get("action") or pending.get("action") or ""
                        ).strip()
                        table_name = str(
                            raw_update.get("table") or pending.get("table") or ""
                        ).strip()
                        tool_call_id = (
                            str((matched_tool_call or {}).get("id") or "").strip()
                            or None
                        )
                        tool_name = (
                            str(
                                ((matched_tool_call or {}).get("function") or {}).get("name")
                                or ""
                            ).strip()
                            or None
                        )
                        rejected = bool(raw_update.get("rejected"))
                        extra_evidence = {
                            "interaction_mode_effective": raw_update.get(
                                "interaction_mode_effective"
                            ),
                            "downgraded_from": raw_update.get("downgraded_from"),
                            "downgrade_reason": raw_update.get("downgrade_reason"),
                            "auto_approve_source": raw_update.get("auto_approve_source"),
                        }
                        decision_payload = {
                            "tenant_id": self.memory_tenant_id,
                            "conversation_id": conversation.id,
                            "agent_id": conversation.agent_id,
                            "operator_id": user_id,
                            "operator_type": owner_type,
                            "decision_type":
                            ExecutionDecisionTypeEnum.CONFIRMATION.value,
                            "subject_type":
                            ExecutionDecisionSubjectEnum.DATA_ACTION.value,
                            "status": (
                                ExecutionDecisionStatusEnum.REJECTED.value
                                if rejected
                                else ExecutionDecisionStatusEnum.APPROVED.value
                            ),
                            "decision_scope": ExecutionDecisionScopeEnum.ONCE.value,
                            "risk_level": self.resolve_action_level_fn(
                                action_name,
                                default=ActionLevelEnum.SAFE_WRITE.value,
                            ),
                            "auto_approved": False,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "action_name": action_name or None,
                            "table_name": table_name or None,
                            "correlation_key": (
                                f"confirmation:{conversation.id}:{msg.id}:{tool_call_id or action_name or table_name}:"
                                f"{'rejected' if rejected else 'approved'}"
                            ),
                            "reason": "user_confirmation",
                            "evidence": {
                                **(pending_evidence or {}),
                                **{
                                    key: value
                                    for key, value in extra_evidence.items()
                                    if value is not None
                                },
                            },
                        }
                elif kind == "pending_consent":
                    pending_evidence, matched_tool_call = _find_pending_consent_evidence(
                        metadata,
                        tool_calls,
                        raw_update.get("tool_name"),
                    )
                    matched = _match_pending_consent(
                        metadata,
                        tool_calls,
                        raw_update.get("tool_name"),
                    )
                    if matched:
                        pending = dict(metadata.get("pending_consent") or {})
                        pending["resolved"] = True
                        pending["rejected"] = bool(raw_update.get("rejected"))
                        pending["auto_approved"] = bool(
                            raw_update.get("auto_approved")
                        )
                        metadata["pending_consent"] = pending
                        for tc in tool_calls:
                            nested = tc.get("pending_consent")
                            if isinstance(nested, dict):
                                next_nested = dict(nested)
                                next_nested["resolved"] = True
                                next_nested["rejected"] = bool(raw_update.get("rejected"))
                                next_nested["auto_approved"] = bool(
                                    raw_update.get("auto_approved")
                                )
                                tc["pending_consent"] = next_nested
                        tool_name = str(
                            raw_update.get("tool_name")
                            or pending.get("tool_name")
                            or (
                                ((matched_tool_call or {}).get("function") or {}).get("name")
                            )
                            or ""
                        ).strip()
                        tool_call_id = (
                            str((matched_tool_call or {}).get("id") or "").strip()
                            or None
                        )
                        auto_approved = bool(raw_update.get("auto_approved"))
                        rejected = bool(raw_update.get("rejected"))
                        extra_evidence = {
                            "interaction_mode_effective": raw_update.get(
                                "interaction_mode_effective"
                            ),
                            "downgraded_from": raw_update.get("downgraded_from"),
                            "downgrade_reason": raw_update.get("downgrade_reason"),
                            "auto_approve_source": raw_update.get(
                                "auto_approve_source"
                            ),
                        }
                        decision_payload = {
                            "tenant_id": self.memory_tenant_id,
                            "conversation_id": conversation.id,
                            "agent_id": conversation.agent_id,
                            "operator_id": user_id,
                            "operator_type": owner_type,
                            "decision_type": ExecutionDecisionTypeEnum.CONSENT.value,
                            "subject_type": ExecutionDecisionSubjectEnum.TOOL_CALL.value,
                            "status": (
                                ExecutionDecisionStatusEnum.AUTO_APPROVED.value
                                if auto_approved
                                else (
                                    ExecutionDecisionStatusEnum.REJECTED.value
                                    if rejected
                                    else ExecutionDecisionStatusEnum.APPROVED.value
                                )
                            ),
                            "decision_scope": (
                                ExecutionDecisionScopeEnum.CONVERSATION.value
                                if auto_approved
                                else ExecutionDecisionScopeEnum.ONCE.value
                            ),
                            "risk_level": self.trust_policy_service_cls.tool_risk_level(
                                tool_name=tool_name,
                                tool_family=self.trust_policy_service_cls.tool_family_for_name(
                                    tool_name
                                ),
                            ),
                            "auto_approved": auto_approved,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name or None,
                            "action_name": None,
                            "table_name": None,
                            "correlation_key": (
                                f"consent:{conversation.id}:{msg.id}:{tool_call_id or tool_name}:"
                                f"{'auto' if auto_approved else ('rejected' if rejected else 'approved')}"
                            ),
                            "reason": "tool_consent",
                            "evidence": {
                                **(pending_evidence or {}),
                                **{
                                    key: value
                                    for key, value in extra_evidence.items()
                                    if value is not None
                                },
                            },
                        }

                if not matched:
                    continue

                normalized_metadata = normalize_json_safe_dict(metadata) or {}
                normalized_tool_calls_raw = normalize_json_safe(
                    tool_calls or msg.tool_calls
                )
                normalized_tool_calls = (
                    normalized_tool_calls_raw
                    if isinstance(normalized_tool_calls_raw, list)
                    else (tool_calls or msg.tool_calls)
                )
                await self.message_repo.update(
                    msg.id,
                    {
                        "metadata_": normalized_metadata,
                        "tool_calls": normalized_tool_calls,
                    },
                )
                msg.metadata_ = normalized_metadata
                msg.tool_calls = normalized_tool_calls
                if msg.id not in seen_ids:
                    updated += 1
                    seen_ids.add(msg.id)
                should_record_decision = (
                    decision_payload is not None
                    and user_id is not None
                    and bool(owner_type)
                )
                if should_record_decision:
                    try:
                        interaction_context: dict[str, Any] = {}
                        planner_context = None
                        context_diagnostics = metadata.get("context_diagnostics")
                        if isinstance(context_diagnostics, dict) and isinstance(
                            context_diagnostics.get("tool_planner"), dict
                        ):
                            planner_context = dict(
                                context_diagnostics.get("tool_planner") or {}
                            )
                        elif isinstance(
                            metadata.get("last_run_summary"), dict
                        ) and isinstance(
                            metadata.get("last_run_summary", {}).get("tool_planner"),
                            dict,
                        ):
                            planner_context = dict(
                                metadata.get("last_run_summary", {}).get("tool_planner")
                                or {}
                            )
                        if interaction_mode_requested:
                            interaction_context[
                                "interaction_mode_requested"
                            ] = interaction_mode_requested
                        if interaction_mode_effective:
                            interaction_context[
                                "interaction_mode_effective"
                            ] = interaction_mode_effective
                        if interaction_mode_downgrade_reason:
                            interaction_context[
                                "interaction_mode_downgrade_reason"
                            ] = interaction_mode_downgrade_reason
                        if planner_context:
                            interaction_context["tool_planner"] = planner_context
                        if interaction_context:
                            evidence_payload = dict(decision_payload.get("evidence") or {})
                            evidence_payload.update(interaction_context)
                            decision_payload["evidence"] = evidence_payload
                        mode_tag = (
                            f"interaction_mode={interaction_mode_effective or 'trusted_auto'}"
                        )
                        reason = str(decision_payload.get("reason") or "").strip()
                        decision_payload["reason"] = (
                            f"{reason}|{mode_tag}" if reason else mode_tag
                        )
                        decision = await decision_service.record_decision(
                            decision_payload
                        )
                        await self.write_ai_action_log_fn(
                            self.db,
                            tenant_id=self.memory_tenant_id,
                            agent_id=conversation.agent_id,
                            conversation_id=conversation.id,
                            execution_decision_id=getattr(decision, "id", None),
                            tool_call_id=decision_payload.get("tool_call_id"),
                            operator_id=user_id,
                            operator_type=owner_type,
                            action_name=(
                                decision_payload.get("tool_name")
                                or decision_payload.get("action_name")
                                or kind
                            ),
                            action_type="confirm",
                            action_level=decision_payload.get("risk_level")
                            or ActionLevelEnum.SAFE_WRITE.value,
                            status=(
                                "rejected"
                                if decision_payload.get("status")
                                == ExecutionDecisionStatusEnum.REJECTED.value
                                else "success"
                            ),
                            request_data={
                                "decision_id": getattr(decision, "id", None),
                                "decision_type": decision_payload.get("decision_type"),
                                "decision_scope": decision_payload.get("decision_scope"),
                                "subject_type": decision_payload.get("subject_type"),
                                "tool_call_id": decision_payload.get("tool_call_id"),
                                "tool_name": decision_payload.get("tool_name"),
                                "action_name": decision_payload.get("action_name"),
                                "table_name": decision_payload.get("table_name"),
                                "evidence": decision_payload.get("evidence"),
                            },
                            response_data={
                                "decision_status": decision_payload.get("status"),
                                "auto_approved": bool(
                                    decision_payload.get("auto_approved")
                                ),
                                "correlation_key": decision_payload.get("correlation_key"),
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "Record execution decision degraded: tenant={} conversation={} message={} kind={} err={}",
                            self.memory_tenant_id,
                            conversation.id,
                            msg.id,
                            kind,
                            str(exc),
                        )
                break

        return updated
