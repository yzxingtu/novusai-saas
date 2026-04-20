"""Conversation message persistence helpers."""

from __future__ import annotations

from typing import Any

from app.ai.memory_policy import MemoryRuntimePolicy
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.base_model import utc_now
from app.enums.agent import MessageRoleEnum
from app.services.ai.conversation_message_persistence_support import (
    build_turn_persistence_context,
    resolve_new_message_start,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)


class ConversationMessagePersistenceService:
    @classmethod
    def resolve_new_message_start(
        cls,
        *,
        result_messages: list[dict[str, Any]] | None,
        history_count: int,
        history_messages: list[ChatMessage] | None = None,
    ) -> int:
        return resolve_new_message_start(
            result_messages=result_messages,
            history_count=history_count,
            history_messages=history_messages,
        )

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
        if isinstance(metadata, dict) and isinstance(
            metadata.get("action_buttons"), list
        ):
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

            tc_ids_expected = {
                tc.get("id", "") for tc in msg.tool_calls if tc.get("id")
            }
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
                    next_tc["summary_payload"] = {
                        **existing_payload,
                        **tr.summary_payload,
                    }
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
        history_messages: list[ChatMessage] | None = None,
        agent_id: int | None = None,
        route_source: str | None = None,
        context_diagnostics: dict[str, Any] | None = None,
        last_run_summary: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        new_start = cls.resolve_new_message_start(
            result_messages=result.messages,
            history_count=history_count,
            history_messages=history_messages,
        )
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

        turn_context = build_turn_persistence_context(
            service,
            result=result,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
        )
        rag_sources = turn_context.rag_sources
        turn_record_payload = turn_context.turn_record_payload
        turn_outcome = turn_context.turn_outcome
        turn_termination_reason = turn_context.turn_termination_reason
        turn_protocol_path = turn_context.turn_protocol_path
        turn_selected_tools = turn_context.turn_selected_tools
        turn_selected_skills = turn_context.turn_selected_skills
        turn_context_sources = turn_context.turn_context_sources
        memory_runtime_policy = turn_context.memory_runtime_policy
        effective_context_diagnostics = turn_context.effective_context_diagnostics
        effective_last_run_summary = turn_context.effective_last_run_summary

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
                if memory_runtime_policy:
                    metadata["memory_runtime_policy"] = service._normalize_json_safe(
                        memory_runtime_policy
                    )
                metadata["turn_flow"] = service._normalize_json_safe(
                    ConversationTurnFlowProjector.project_from_metadata(
                        metadata,
                        content=content,
                        tool_calls=tool_calls,
                        token_count=token_estimate,
                    )
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
        update_payload: dict[str, Any] = {"message_count": new_message_count}
        if memory_runtime_policy:
            thread_memory_state = MemoryRuntimePolicy(
                **{
                    key: value
                    for key, value in memory_runtime_policy.items()
                    if key in MemoryRuntimePolicy.__dataclass_fields__
                }
            ).to_thread_state()
            thread_memory_state["updated_at"] = service._format_dt(utc_now())
            conversation_metadata = dict(conversation.metadata_ or {})
            conversation_metadata["thread_memory_state"] = thread_memory_state
            conversation.metadata_ = (
                service._normalize_json_safe_dict(conversation_metadata) or {}
            )
            update_payload["metadata_"] = conversation.metadata_
        await service.repo.update(
            conversation.id,
            update_payload,
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
            and (bool(str(message.content or "").strip()) or bool(message.attachments))
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
