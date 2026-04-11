"""
Conversation message persistence helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.base_model import utc_now
from app.enums.agent import MessageRoleEnum


class ConversationMessagePersistenceService:
    @staticmethod
    def has_pending_state(
        *,
        tool_calls: list[dict[str, Any]] | None,
        metadata: dict[str, Any] | None,
    ) -> bool:
        if isinstance(metadata, dict) and (
            isinstance(metadata.get("pending_confirmation"), dict)
            or isinstance(metadata.get("pending_consent"), dict)
        ):
            return True

        for tc in tool_calls or []:
            if not isinstance(tc, dict):
                continue
            if isinstance(tc.get("pending_confirmation"), dict) or isinstance(
                tc.get("pending_consent"),
                dict,
            ):
                return True
        return False

    @classmethod
    def assistant_has_content_or_signal(
        cls,
        message: dict[str, Any],
    ) -> bool:
        content = str(message.get("content") or "").strip()
        tool_calls = message.get("tool_calls")
        metadata = (
            dict(message.get("metadata") or {})
            if isinstance(message.get("metadata"), dict)
            else None
        )
        if content:
            return True
        if isinstance(tool_calls, list) and tool_calls:
            return True
        if cls.has_pending_state(tool_calls=tool_calls, metadata=metadata):
            return True
        if isinstance(metadata, dict) and isinstance(metadata.get("action_buttons"), list):
            return len(metadata.get("action_buttons") or []) > 0
        return False

    @staticmethod
    def sanitize_tool_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
        if not messages:
            return messages

        result: list[ChatMessage] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.role == "tool":
                i += 1
                continue
            if msg.role != "assistant" or not msg.tool_calls:
                result.append(msg)
                i += 1
                continue

            tc_ids_expected = {tc.get("id", "") for tc in msg.tool_calls if tc.get("id")}
            if not tc_ids_expected:
                result.append(msg)
                i += 1
                continue

            collected_tool_ids: set[str] = set()
            round_msgs: list[ChatMessage] = [msg]
            j = i + 1
            while j < len(messages):
                next_msg = messages[j]
                if next_msg.role == "tool" and next_msg.tool_call_id:
                    if next_msg.tool_call_id in tc_ids_expected:
                        collected_tool_ids.add(next_msg.tool_call_id)
                        round_msgs.append(next_msg)
                    j += 1
                    continue
                if next_msg.role in ("assistant", "user", "system"):
                    break
                j += 1

            if collected_tool_ids == tc_ids_expected:
                result.extend(round_msgs)
            i = j

        return result

    @staticmethod
    def enrich_tool_calls_for_persistence(
        tool_calls: list[dict[str, Any]] | None,
        tool_result_map: dict[str, ToolResult],
    ) -> list[dict[str, Any]] | None:
        if not tool_calls:
            return tool_calls

        enriched: list[dict[str, Any]] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue

            next_tc = dict(tc)
            tc_id = str(next_tc.get("id") or "")
            tr = tool_result_map.get(tc_id) if tc_id else None
            if tr:
                if tr.display_name and not next_tc.get("display_name"):
                    next_tc["display_name"] = tr.display_name
                if tr.summary and not next_tc.get("summary"):
                    next_tc["summary"] = tr.summary
                if tr.summary_payload:
                    existing_payload = (
                        next_tc.get("summary_payload")
                        if isinstance(next_tc.get("summary_payload"), dict)
                        else {}
                    )
                    next_tc["summary_payload"] = {**existing_payload, **tr.summary_payload}
                if tr.result_link and not next_tc.get("result_link"):
                    next_tc["result_link"] = tr.result_link
                if tr.error_type and not next_tc.get("error_type"):
                    next_tc["error_type"] = tr.error_type
                if tr.duration_ms and not next_tc.get("duration_ms"):
                    next_tc["duration_ms"] = tr.duration_ms
                next_tc["success"] = tr.success

            enriched.append(next_tc)

        return enriched

    @classmethod
    async def persist_chat_messages(
        cls,
        service: Any,
        *,
        conversation: Any,
        result: Any,
        history_count: int,
        agent_id: int | None = None,
        route_source: str | None = None,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        # Count leading system messages dynamically (not hard-coded as 1)
        system_count = 0
        for msg_dict in result.messages:
            if msg_dict.get("role") == "system":
                system_count += 1
            else:
                break
        new_start = system_count + history_count
        new_messages_raw = result.messages[new_start:]

        if not new_messages_raw:
            return [], 0

        # Sanitize: persist complete tool rounds only; drop orphan tool_calls
        chat_msgs = [
            ChatMessage(
                role=m.get("role", ""),
                content=m.get("content", "") or "",
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
                attachments=m.get("attachments"),
                reasoning_content=m.get("reasoning_content"),
                metadata=service._copy_metadata(m.get("metadata")),
                internal_only=bool(m.get("internal_only", False)),
            )
            for m in new_messages_raw
        ]
        chat_msgs = cls.sanitize_tool_messages(chat_msgs)
        new_messages = [
            {
                "role": m.role,
                "content": m.content or "",
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
                "attachments": m.attachments,
                "reasoning_content": m.reasoning_content,
                "metadata": service._copy_metadata(m.metadata),
            }
            for m in chat_msgs
            if not m.internal_only
        ]
        if not new_messages:
            return [], 0

        # tool_call_id -> ToolResult lookup
        tool_result_map: dict[str, ToolResult] = {}
        if result.tool_results:
            for tr in result.tool_results:
                if tr.tool_call_id:
                    tool_result_map[tr.tool_call_id] = tr

        next_seq = await service.message_repo.get_next_sequence(conversation.id)
        tool_calls_collected: list[dict[str, Any]] = []
        persisted_count = 0
        route_source_marked = False

        rag_sources = getattr(result, "rag_sources", None)
        turn_meta = service._extract_turn_diagnostics_from_metadata(
            {
                "turn_record": getattr(result, "turn_record", None),
                "completion_reason": getattr(result, "completion_reason", None),
                "partial": bool(getattr(result, "partial", False)),
                "interrupted": bool(getattr(result, "interrupted", False)),
            }
        )
        turn_record_payload = turn_meta.get("turn_record")
        turn_outcome = turn_meta.get("turn_outcome")
        turn_termination_reason = turn_meta.get("termination_reason")
        turn_protocol_path = turn_meta.get("protocol_path")
        turn_selected_tools = turn_meta.get("selected_tool_names") or []
        turn_selected_skills = turn_meta.get("selected_skill_names") or []
        turn_context_sources = turn_meta.get("context_sources") or []
        result_completion_reason = service._to_non_empty_str(
            getattr(result, "completion_reason", None)
        )
        if bool(getattr(result, "partial", False)) or bool(
            getattr(result, "interrupted", False)
        ):
            turn_outcome = "partial"
            if bool(getattr(result, "interrupted", False)) or (
                result_completion_reason == "interrupted"
            ):
                turn_termination_reason = "interrupted"
            elif result_completion_reason:
                turn_termination_reason = result_completion_reason

        effective_context_diagnostics = (
            dict(context_diagnostics) if isinstance(context_diagnostics, dict) else {}
        )
        if turn_outcome:
            effective_context_diagnostics["turn_outcome"] = turn_outcome
        if turn_termination_reason:
            effective_context_diagnostics["termination_reason"] = (
                turn_termination_reason
            )
        if turn_protocol_path:
            effective_context_diagnostics["protocol_path"] = turn_protocol_path
        if turn_meta.get("tool_planner"):
            effective_context_diagnostics["tool_planner"] = turn_meta["tool_planner"]
        if turn_selected_tools:
            effective_context_diagnostics["selected_tool_names"] = turn_selected_tools
        if turn_selected_skills:
            effective_context_diagnostics["selected_skill_names"] = turn_selected_skills
        if turn_context_sources:
            effective_context_diagnostics["context_sources"] = turn_context_sources
        if turn_meta.get("execution_path"):
            effective_context_diagnostics["execution_path"] = turn_meta["execution_path"]
        if turn_meta.get("active_intent_id"):
            effective_context_diagnostics["active_intent_id"] = turn_meta[
                "active_intent_id"
            ]
        if turn_meta.get("continuation_source"):
            effective_context_diagnostics["continuation_source"] = turn_meta[
                "continuation_source"
            ]
        if turn_meta.get("conversation_outcome"):
            effective_context_diagnostics["conversation_outcome"] = turn_meta[
                "conversation_outcome"
            ]
        if turn_meta.get("intent_plan"):
            effective_context_diagnostics["intent_plan"] = turn_meta["intent_plan"]
        if turn_meta.get("budget"):
            effective_context_diagnostics["budget"] = turn_meta["budget"]
        if turn_meta.get("budget_status"):
            effective_context_diagnostics["budget_status"] = turn_meta["budget_status"]
        if turn_meta.get("budget_exit_reason"):
            effective_context_diagnostics["budget_exit_reason"] = turn_meta[
                "budget_exit_reason"
            ]
        if turn_meta.get("candidate_tool_names"):
            effective_context_diagnostics["candidate_tool_names"] = turn_meta[
                "candidate_tool_names"
            ]
        if turn_meta.get("retry_events"):
            effective_context_diagnostics["retry_events"] = turn_meta["retry_events"]
        if turn_meta.get("partial_exit_reason"):
            effective_context_diagnostics["partial_exit_reason"] = turn_meta[
                "partial_exit_reason"
            ]
        if turn_meta.get("failure_kind"):
            effective_context_diagnostics["failure_kind"] = turn_meta["failure_kind"]
        if turn_meta.get("provider_events"):
            effective_context_diagnostics["provider_events"] = turn_meta[
                "provider_events"
            ]
        if turn_meta.get("contract_breach_type"):
            effective_context_diagnostics["contract_breach_type"] = turn_meta[
                "contract_breach_type"
            ]
        if turn_meta.get("tool_leak_detected"):
            effective_context_diagnostics["tool_leak_detected"] = True
        if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
            effective_context_diagnostics[
                "assistant_claimed_tool_call_without_tool_event"
            ] = True
        if turn_meta.get("unfinished_intents"):
            effective_context_diagnostics["unfinished_intents"] = turn_meta[
                "unfinished_intents"
            ]
        if turn_meta.get("leaked_tool_names"):
            effective_context_diagnostics["leaked_tool_names"] = turn_meta[
                "leaked_tool_names"
            ]
        if turn_meta.get("recovered_via_retry") is not None:
            effective_context_diagnostics["recovered_via_retry"] = turn_meta[
                "recovered_via_retry"
            ]
        if turn_meta.get("last_tool_name"):
            effective_context_diagnostics["last_tool_name"] = turn_meta["last_tool_name"]
        if turn_meta.get("last_page_key"):
            effective_context_diagnostics["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            effective_context_diagnostics["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            effective_context_diagnostics["interrupted_stage"] = turn_meta[
                "interrupted_stage"
            ]
        if turn_meta.get("tool_loop_progress"):
            effective_context_diagnostics["tool_loop_progress"] = turn_meta[
                "tool_loop_progress"
            ]
        if turn_meta.get("sync_rescue") is not None:
            effective_context_diagnostics["sync_rescue"] = turn_meta["sync_rescue"]
        if turn_meta.get("should_record_call_log") is not None:
            effective_context_diagnostics["should_record_call_log"] = turn_meta[
                "should_record_call_log"
            ]
        effective_context_diagnostics.setdefault(
            "last_interrupted",
            bool(getattr(result, "interrupted", False))
            or turn_termination_reason == "interrupted",
        )

        effective_last_run_summary = (
            dict(last_run_summary) if isinstance(last_run_summary, dict) else {}
        )
        if turn_outcome:
            effective_last_run_summary["turn_outcome"] = turn_outcome
        if turn_termination_reason:
            effective_last_run_summary["termination_reason"] = turn_termination_reason
            effective_last_run_summary.setdefault(
                "completion_reason", turn_termination_reason
            )
        if turn_protocol_path:
            effective_last_run_summary["protocol_path"] = turn_protocol_path
        if turn_meta.get("tool_planner"):
            effective_last_run_summary["tool_planner"] = turn_meta["tool_planner"]
        if turn_selected_tools:
            effective_last_run_summary["selected_tool_names"] = turn_selected_tools
        if turn_selected_skills:
            effective_last_run_summary["selected_skill_names"] = turn_selected_skills
        if turn_context_sources:
            effective_last_run_summary["context_sources"] = turn_context_sources
        if turn_meta.get("execution_path"):
            effective_last_run_summary["execution_path"] = turn_meta["execution_path"]
        if turn_meta.get("active_intent_id"):
            effective_last_run_summary["active_intent_id"] = turn_meta[
                "active_intent_id"
            ]
        if turn_meta.get("continuation_source"):
            effective_last_run_summary["continuation_source"] = turn_meta[
                "continuation_source"
            ]
        if turn_meta.get("conversation_outcome"):
            effective_last_run_summary["conversation_outcome"] = turn_meta[
                "conversation_outcome"
            ]
        if turn_meta.get("intent_plan"):
            effective_last_run_summary["intent_plan"] = turn_meta["intent_plan"]
        if turn_meta.get("budget"):
            effective_last_run_summary["budget"] = turn_meta["budget"]
        if turn_meta.get("budget_status"):
            effective_last_run_summary["budget_status"] = turn_meta["budget_status"]
        if turn_meta.get("budget_exit_reason"):
            effective_last_run_summary["budget_exit_reason"] = turn_meta[
                "budget_exit_reason"
            ]
        if turn_meta.get("candidate_tool_names"):
            effective_last_run_summary["candidate_tool_names"] = turn_meta[
                "candidate_tool_names"
            ]
        if turn_meta.get("retry_events"):
            effective_last_run_summary["retry_events"] = turn_meta["retry_events"]
        if turn_meta.get("partial_exit_reason"):
            effective_last_run_summary["partial_exit_reason"] = turn_meta[
                "partial_exit_reason"
            ]
        if turn_meta.get("failure_kind"):
            effective_last_run_summary["failure_kind"] = turn_meta["failure_kind"]
        if turn_meta.get("provider_events"):
            effective_last_run_summary["provider_events"] = turn_meta["provider_events"]
        if turn_meta.get("contract_breach_type"):
            effective_last_run_summary["contract_breach_type"] = turn_meta[
                "contract_breach_type"
            ]
        if turn_meta.get("tool_leak_detected"):
            effective_last_run_summary["tool_leak_detected"] = True
        if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
            effective_last_run_summary[
                "assistant_claimed_tool_call_without_tool_event"
            ] = True
        if turn_meta.get("unfinished_intents"):
            effective_last_run_summary["unfinished_intents"] = turn_meta[
                "unfinished_intents"
            ]
        if turn_meta.get("leaked_tool_names"):
            effective_last_run_summary["leaked_tool_names"] = turn_meta[
                "leaked_tool_names"
            ]
        if turn_meta.get("recovered_via_retry") is not None:
            effective_last_run_summary["recovered_via_retry"] = turn_meta[
                "recovered_via_retry"
            ]
        if turn_meta.get("last_tool_name"):
            effective_last_run_summary["last_tool_name"] = turn_meta["last_tool_name"]
        if turn_meta.get("last_page_key"):
            effective_last_run_summary["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            effective_last_run_summary["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            effective_last_run_summary["interrupted_stage"] = turn_meta[
                "interrupted_stage"
            ]
        if turn_meta.get("tool_loop_progress"):
            effective_last_run_summary["tool_loop_progress"] = turn_meta[
                "tool_loop_progress"
            ]
        if turn_meta.get("sync_rescue") is not None:
            effective_last_run_summary["sync_rescue"] = turn_meta["sync_rescue"]
        if turn_meta.get("should_record_call_log") is not None:
            effective_last_run_summary["should_record_call_log"] = turn_meta[
                "should_record_call_log"
            ]
        if (
            bool(getattr(result, "interrupted", False))
            or turn_termination_reason == "interrupted"
        ):
            effective_last_run_summary["interrupted"] = True

        last_assistant_idx: int | None = None
        last_plain_assistant_idx: int | None = None
        last_assistant_with_signal_idx: int | None = None
        for j, m in enumerate(new_messages):
            if m.get("role") != "assistant":
                continue
            last_assistant_idx = j
            if cls.assistant_has_content_or_signal(m):
                last_assistant_with_signal_idx = j
            if not m.get("tool_calls"):
                last_plain_assistant_idx = j

        turn_target_assistant_idx = (
            last_plain_assistant_idx
            if last_plain_assistant_idx is not None
            else (
                last_assistant_with_signal_idx
                if last_assistant_with_signal_idx is not None
                else last_assistant_idx
            )
        )

        for i, msg_dict in enumerate(new_messages):
            role = msg_dict.get("role", "")
            content = msg_dict.get("content", "")
            tool_calls = msg_dict.get("tool_calls")
            tool_call_id = msg_dict.get("tool_call_id")
            attachments = msg_dict.get("attachments")
            reasoning_content = msg_dict.get("reasoning_content")
            persisted_metadata = service._copy_metadata(msg_dict.get("metadata"))
            tool_calls = cls.enrich_tool_calls_for_persistence(
                tool_calls,
                tool_result_map,
            )

            if tool_calls:
                tool_calls_collected.extend(tool_calls)

            should_skip_empty_assistant_success = (
                role == "assistant"
                and bool(getattr(result, "success", False))
                and not bool(getattr(result, "partial", False))
                and not bool(getattr(result, "interrupted", False))
                and not str(content or "").strip()
                and not bool(tool_calls)
                and not cls.has_pending_state(
                    tool_calls=tool_calls,
                    metadata=persisted_metadata,
                )
                and not isinstance(
                    (persisted_metadata or {}).get("action_buttons"), list
                )
            )
            if should_skip_empty_assistant_success:
                continue

            token_estimate = estimate_tokens(content) if content else 0

            metadata = service._normalize_json_safe_dict(persisted_metadata)
            if attachments:
                metadata = metadata or {}
                metadata["attachments"] = service._normalize_json_safe(attachments)
            if role == "assistant" and reasoning_content and reasoning_content.strip():
                metadata = metadata or {}
                metadata["thinking_content"] = reasoning_content.strip()
            if (
                role == "assistant"
                and persisted_metadata
                and "action_buttons_used" in persisted_metadata
            ):
                metadata = metadata or {}
                metadata["action_buttons_used"] = persisted_metadata.get(
                    "action_buttons_used",
                )

            if role == "tool" and tool_call_id and tool_call_id in tool_result_map:
                tr = tool_result_map[tool_call_id]
                metadata = metadata or {}
                metadata["tool_success"] = tr.success
                if not tr.success and tr.error:
                    metadata["tool_error"] = tr.error
                if tr.display_name:
                    metadata["tool_display_name"] = tr.display_name
                if tr.summary:
                    metadata["tool_summary"] = tr.summary
                if tr.summary_payload:
                    metadata["tool_summary_payload"] = tr.summary_payload
                if tr.result_link:
                    metadata["tool_result_link"] = tr.result_link
                if tr.error_type:
                    metadata["tool_error_type"] = tr.error_type
                if tr.duration_ms:
                    metadata["tool_duration_ms"] = tr.duration_ms

            should_mark_partial_semantics = (
                role == "assistant"
                and (
                    getattr(result, "partial", False)
                    or getattr(result, "interrupted", False)
                )
                and i == turn_target_assistant_idx
            )
            if should_mark_partial_semantics:
                metadata = metadata or {}
                metadata["partial"] = bool(
                    getattr(result, "partial", False)
                    or getattr(result, "interrupted", False)
                )
                metadata["interrupted"] = getattr(result, "interrupted", False)
                completion_reason = service._to_non_empty_str(
                    getattr(result, "completion_reason", None)
                )
                if completion_reason:
                    metadata["completion_reason"] = completion_reason

            if route_source and role == "assistant" and not route_source_marked:
                metadata = metadata or {}
                metadata["route_source"] = route_source
                route_source_marked = True

            if role == "assistant":
                if result.runtime_model_name:
                    metadata = metadata or {}
                    metadata["model_name"] = result.runtime_model_name
                if result.runtime_provider_id is not None:
                    metadata = metadata or {}
                    metadata["provider_id"] = result.runtime_provider_id
                if result.runtime_provider_name:
                    metadata = metadata or {}
                    metadata["provider_name"] = result.runtime_provider_name

            if (
                rag_sources
                and role == "assistant"
                and not tool_calls
                and i == last_plain_assistant_idx
            ):
                metadata = metadata or {}
                metadata["rag_sources"] = rag_sources
                if getattr(result, "rag_source_kinds", None):
                    metadata["rag_source_kinds"] = result.rag_source_kinds

            if (
                role == "assistant"
                and not tool_calls
                and i == turn_target_assistant_idx
            ):
                if getattr(result, "prune_stats", None):
                    metadata = metadata or {}
                    metadata["prune_stats"] = result.prune_stats
                if getattr(result, "context_compacted", False):
                    metadata = metadata or {}
                    metadata["context_compacted"] = True
                if getattr(result, "memory_flush_triggered", False):
                    metadata = metadata or {}
                    metadata["memory_flush_triggered"] = True
                if getattr(result, "memory_recalled", False):
                    metadata = metadata or {}
                    metadata["memory_recalled"] = True
                if effective_context_diagnostics:
                    metadata = metadata or {}
                    metadata["context_diagnostics"] = service._normalize_json_safe(
                        effective_context_diagnostics
                    )
                if effective_last_run_summary:
                    metadata = metadata or {}
                    metadata["last_run_summary"] = service._normalize_json_safe(
                        effective_last_run_summary
                    )

            if role == "assistant" and i == turn_target_assistant_idx:
                metadata = metadata or {}
                if effective_context_diagnostics:
                    metadata["context_diagnostics"] = service._normalize_json_safe(
                        effective_context_diagnostics
                    )
                if effective_last_run_summary:
                    metadata["last_run_summary"] = service._normalize_json_safe(
                        effective_last_run_summary
                    )
                if turn_record_payload:
                    metadata["turn_record"] = service._normalize_json_safe(
                        turn_record_payload
                    )
                if turn_outcome:
                    metadata["turn_outcome"] = turn_outcome
                if turn_termination_reason:
                    metadata["termination_reason"] = turn_termination_reason
                    metadata.setdefault("completion_reason", turn_termination_reason)
                if turn_protocol_path:
                    metadata["protocol_path"] = turn_protocol_path
                if turn_selected_tools:
                    metadata["selected_tool_names"] = service._normalize_json_safe(
                        turn_selected_tools
                    )
                if turn_selected_skills:
                    metadata["selected_skill_names"] = service._normalize_json_safe(
                        turn_selected_skills
                    )
                if turn_context_sources:
                    metadata["context_sources"] = service._normalize_json_safe(
                        turn_context_sources
                    )

            metadata = service._normalize_json_safe_dict(metadata)

            msg_agent_id = agent_id if role in ("assistant", "tool") else None
            msg_model_id = result.runtime_model_id if role == "assistant" else None

            await service.message_repo.create(
                {
                    "tenant_id": service.tenant_id,
                    "conversation_id": conversation.id,
                    "role": role,
                    "content": content,
                    "sequence": next_seq + persisted_count,
                    "token_count": token_estimate,
                    "tool_calls": tool_calls,
                    "tool_call_id": tool_call_id,
                    "agent_id": msg_agent_id,
                    "model_id": msg_model_id,
                    "metadata_": metadata,
                }
            )
            persisted_count += 1

        new_message_count = (conversation.message_count or 0) + persisted_count
        await service.repo.update(
            conversation.id,
            {"message_count": new_message_count},
        )

        return tool_calls_collected, persisted_count

    @classmethod
    async def persist_user_messages(
        cls,
        service: Any,
        *,
        conversation: Any,
        messages: list[ChatMessage],
    ) -> int:
        user_messages = [
            message
            for message in (messages or [])
            if message.role == "user"
            and (
                bool(str(message.content or "").strip())
                or bool(message.attachments)
            )
        ]
        if not user_messages:
            return 0

        next_seq = await service.message_repo.get_next_sequence(conversation.id)
        persisted_count = 0

        for message in user_messages:
            metadata: dict[str, Any]
            if message.attachments:
                metadata = {
                    "attachments": service._normalize_json_safe(message.attachments),
                    "stream_seeded": True,
                }
            else:
                metadata = {"stream_seeded": True}
            normalized_metadata = service._normalize_json_safe_dict(metadata)

            content = str(message.content or "")
            await service.message_repo.create(
                {
                    "tenant_id": service.tenant_id,
                    "conversation_id": conversation.id,
                    "role": MessageRoleEnum.USER.value,
                    "content": content,
                    "sequence": next_seq + persisted_count,
                    "token_count": estimate_tokens(content) if content else 0,
                    "agent_id": None,
                    "model_id": None,
                    "metadata_": normalized_metadata,
                }
            )
            persisted_count += 1

        if persisted_count:
            conversation.message_count = int(conversation.message_count or 0) + int(
                persisted_count
            )
            await service.repo.update(
                conversation.id,
                {"message_count": conversation.message_count},
            )

        return persisted_count

    @classmethod
    async def mark_memory_updated(
        cls,
        service: Any,
        conversation_id: int,
    ) -> None:
        messages = await service.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=1,
        )
        if not messages:
            return
        last_msg = messages[-1]
        if last_msg.role != MessageRoleEnum.ASSISTANT.value:
            return
        metadata = service._normalize_json_safe_dict(last_msg.metadata_) or {}
        metadata["memory_updated"] = True
        await service.message_repo.update(
            last_msg.id,
            {"metadata_": service._normalize_json_safe_dict(metadata) or metadata},
        )

    @staticmethod
    async def get_context_compaction_snapshot(
        service: Any,
        conversation_id: int,
        *,
        metadata_key: str,
    ) -> dict[str, Any] | None:
        conversation = await service.repo.get_by_id(conversation_id)
        if not conversation:
            return None
        metadata = (
            conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
        )
        snapshot = metadata.get(metadata_key)
        return snapshot if isinstance(snapshot, dict) else None

    @staticmethod
    async def upsert_context_compaction_snapshot(
        service: Any,
        conversation_id: int,
        *,
        metadata_key: str,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any] | None:
        conversation = await service.repo.get_by_id(conversation_id)
        if not conversation:
            return None
        metadata = dict(conversation.metadata_ or {})
        snapshot = {
            "summary": summary,
            "source_message_count": source_message_count,
            "source_token_estimate": source_token_estimate,
            "generated_at": service._format_dt(utc_now()),
        }
        metadata[metadata_key] = snapshot
        conversation.metadata_ = metadata
        await service.db.flush()
        return snapshot
