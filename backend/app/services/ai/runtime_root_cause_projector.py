"""
Runtime diagnostics root-cause projector.
"""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import (
    extract_textual_tool_call_names,
    has_tool_planning_leak_phrase,
)
from app.enums.ai import CallStatusEnum
from app.models.ai.call_log import AICallLog
from app.services.ai.conversation_diagnostics_projector_support_diagnostics import (
    sanitize_diagnostics_payload,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.turn_failure_normalizer import (
    resolve_failure_projection,
)

_BUDGET_TERMINATION_REASONS = {
    "budget_exit",
    "elapsed_budget_exceeded",
    "completion_budget_exceeded",
    "tool_round_budget_exceeded",
    "retry_budget_exhausted",
    "prompt_budget_exceeded",
    "tool_result_budget_exceeded",
    "candidate_tool_budget_exceeded",
}
_PROVIDER_GATEWAY_FAILURE_KINDS = {
    "provider_timeout",
    "provider_unavailable",
    "provider_http_5xx",
    "provider_gateway_error",
    "provider_bad_response",
    "provider_rate_limit",
}
_PROVIDER_HTTP_5XX_ERROR_TOKENS = (
    "bad gateway",
    "gateway timeout",
    "service unavailable",
    "server error",
    "server_error",
    "服务端错误",
    "服务暂不可用",
    "502",
    "503",
    "504",
)


class RuntimeRootCauseProjector:
    @staticmethod
    def _request_scope(metadata: dict[str, Any]) -> dict[str, Any]:
        nested = metadata.get("request")
        return dict(nested) if isinstance(nested, dict) else {}

    @staticmethod
    def _call_log_request_metadata(call_log: AICallLog | None) -> dict[str, Any]:
        raw = (
            getattr(call_log, "request_metadata", None)
            if call_log is not None
            else None
        )
        return dict(raw) if isinstance(raw, dict) else {}

    @classmethod
    def _call_log_turn_record(cls, call_log: AICallLog | None) -> dict[str, Any]:
        metadata = cls._call_log_request_metadata(call_log)
        request_scope = cls._request_scope(metadata)
        raw_turn_record = metadata.get("turn_record")
        if not isinstance(raw_turn_record, dict):
            raw_turn_record = request_scope.get("turn_record")
        return dict(raw_turn_record) if isinstance(raw_turn_record, dict) else {}

    @classmethod
    def _call_log_turn_record_metadata(
        cls, call_log: AICallLog | None
    ) -> dict[str, Any]:
        turn_record = cls._call_log_turn_record(call_log)
        raw_metadata = turn_record.get("metadata")
        return dict(raw_metadata) if isinstance(raw_metadata, dict) else {}

    @classmethod
    def _resolve_turn_flow_payload(
        cls,
        *,
        diagnostics: dict[str, Any],
        conversation_turn: dict[str, Any] | None,
        call_log: AICallLog | None,
    ) -> dict[str, Any] | None:
        assistant_content = (
            conversation_turn.get("assistant_content")
            if isinstance(conversation_turn, dict)
            else None
        )

        def _normalize(
            raw_turn_flow: dict[str, Any],
            metadata: dict[str, Any] | None = None,
            content: Any = assistant_content,
        ) -> dict[str, Any] | None:
            return ConversationTurnFlowProjector.normalize_turn_flow(
                raw_turn_flow,
                turn_outcome=(
                    str(
                        diagnostics.get("turn_outcome")
                        or diagnostics.get("conversation_outcome")
                        or ""
                    ).strip()
                    or None
                ),
                completion_reason=(
                    str(
                        diagnostics.get("termination_reason")
                        or diagnostics.get("completion_reason")
                        or ""
                    ).strip()
                    or None
                ),
                interrupted=bool(diagnostics.get("interrupted")),
                failure_kind=(
                    str(diagnostics.get("failure_kind") or "").strip() or None
                ),
                final_output_source=(
                    str(diagnostics.get("final_output_source") or "").strip() or None
                ),
                metadata=metadata,
                content=content,
            )

        diagnostic_turn_flow = diagnostics.get("turn_flow")
        if isinstance(diagnostic_turn_flow, dict):
            return _normalize(dict(diagnostic_turn_flow), diagnostics)

        if isinstance(conversation_turn, dict):
            conversation_diagnostics = conversation_turn.get("diagnostics")
            if isinstance(conversation_diagnostics, dict) and isinstance(
                conversation_diagnostics.get("turn_flow"), dict
            ):
                return _normalize(
                    dict(conversation_diagnostics.get("turn_flow") or {}),
                    conversation_diagnostics,
                )
            conversation_metadata = conversation_turn.get("metadata")
            if isinstance(conversation_metadata, dict) and isinstance(
                conversation_metadata.get("turn_flow"), dict
            ):
                return _normalize(
                    dict(conversation_metadata.get("turn_flow") or {}),
                    conversation_metadata,
                )

        call_log_turn_record = cls._call_log_turn_record(call_log)
        if isinstance(call_log_turn_record.get("turn_flow"), dict):
            return _normalize(
                dict(call_log_turn_record.get("turn_flow") or {}),
                call_log_turn_record,
            )

        call_log_metadata = cls._call_log_request_metadata(call_log)
        turn_diagnostics = (
            dict(call_log_metadata.get("turn_diagnostics") or {})
            if isinstance(call_log_metadata.get("turn_diagnostics"), dict)
            else {}
        )
        if isinstance(turn_diagnostics.get("turn_flow"), dict):
            return _normalize(
                dict(turn_diagnostics.get("turn_flow") or {}),
                turn_diagnostics,
            )
        return None

    @staticmethod
    def has_meaningful_value(value: Any) -> bool:
        return value not in (None, "", [], {}, ())

    @classmethod
    def merge_root_cause_diagnostics(
        cls,
        *,
        conversation_diagnostics: dict[str, Any],
        call_log_diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(call_log_diagnostics or {})
        for key, value in (conversation_diagnostics or {}).items():
            if key not in merged or cls.has_meaningful_value(value):
                merged[key] = value
        return sanitize_diagnostics_payload(merged) or {}

    @staticmethod
    def detect_claimed_tool_call_without_event(
        *,
        content: str,
        diagnostics: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        if tool_calls:
            return False
        normalized_content = str(content or "").strip()
        if not normalized_content:
            return False

        tool_names = []
        for name in list(diagnostics.get("candidate_tool_names") or []) + list(
            diagnostics.get("selected_tool_names") or []
        ):
            normalized_name = str(name or "").strip()
            if normalized_name and normalized_name not in tool_names:
                tool_names.append(normalized_name)
        alias_map = {name: name for name in tool_names}
        textual_tool_names = (
            extract_textual_tool_call_names(
                normalized_content,
                alias_to_tool_name=alias_map,
                known_tool_names=set(alias_map) if alias_map else None,
            )
            if alias_map
            else []
        )
        lowered = normalized_content.lower()
        marker_present = (
            has_tool_planning_leak_phrase(normalized_content)
            or "calling " in lowered
            or "invoking " in lowered
            or "正在调用" in normalized_content
            or "调用 " in normalized_content
        )
        return bool(textual_tool_names or (marker_present and tool_names))

    @staticmethod
    def is_research_like_diagnostics(diagnostics: dict[str, Any]) -> bool:
        tool_planner = (
            dict(diagnostics.get("tool_planner") or {})
            if isinstance(diagnostics.get("tool_planner"), dict)
            else {}
        )
        planner_family = str(tool_planner.get("family") or "").strip()
        continuation_source = str(diagnostics.get("continuation_source") or "").strip()
        selected_tools = {
            str(name or "").strip()
            for name in list(diagnostics.get("selected_tool_names") or [])
            + list(diagnostics.get("candidate_tool_names") or [])
            if str(name or "").strip()
        }
        unfinished_intents = {
            str(name or "").strip()
            for name in diagnostics.get("unfinished_intents") or []
            if str(name or "").strip()
        }
        return bool(
            planner_family == "web_research"
            or continuation_source == "web_research"
            or {"web_search", "fetch_url"} & selected_tools
            or unfinished_intents
            & {"web_research", "weather_query", "weather", "rail_ticket_research"}
        )

    @staticmethod
    def planner_source_text(diagnostics: dict[str, Any]) -> str:
        tool_planner = diagnostics.get("tool_planner")
        if not isinstance(tool_planner, dict):
            return ""
        intent_plan = tool_planner.get("intent_plan")
        if not isinstance(intent_plan, list):
            return ""
        for item in intent_plan:
            if not isinstance(item, dict):
                continue
            source_text = str(item.get("source_text") or "").strip()
            if source_text:
                return source_text
        return ""

    @classmethod
    def has_false_direct_reply_signal(cls, diagnostics: dict[str, Any]) -> bool:
        tool_planner = (
            dict(diagnostics.get("tool_planner") or {})
            if isinstance(diagnostics.get("tool_planner"), dict)
            else {}
        )
        if str(tool_planner.get("intent") or "").strip() != "direct_reply":
            return False
        selected_tool_names = {
            str(name or "").strip()
            for name in diagnostics.get("selected_tool_names") or []
            if str(name or "").strip()
        }
        candidate_tool_names = {
            str(name or "").strip()
            for name in diagnostics.get("candidate_tool_names") or []
            if str(name or "").strip()
        }
        if selected_tool_names or candidate_tool_names:
            return False

        selected_skill_names = {
            str(name or "").strip()
            for name in diagnostics.get("selected_skill_names") or []
            if str(name or "").strip()
        }
        if not selected_skill_names:
            return False

        source_text = cls.planner_source_text(diagnostics).lower()
        if not source_text:
            return False

        looks_like_time = any(
            token in source_text
            for token in (
                "现在几点",
                "现在是几点",
                "当前时间",
                "北京时间",
                "current time",
                "beijing time",
                "星期几",
                "周几",
                "几号",
            )
        )
        looks_like_weather = any(
            token in source_text
            for token in ("天气", "气温", "温度", "降雨", "湿度", "weather")
        )
        looks_like_web = any(
            token in source_text
            for token in (
                "联网",
                "搜索",
                "搜一下",
                "搜一搜",
                "官网",
                "链接",
                "网址",
                "web search",
                "search online",
                "fetch",
                "新闻",
                "热点",
                "排行",
            )
        )
        merged_names = " ".join(selected_skill_names).lower()
        has_time_capability = any(
            token in merged_names for token in ("get_current_time", "time", "时间")
        )
        has_weather_capability = any(
            token in merged_names for token in ("weather", "天气")
        )
        has_web_capability = any(
            token in merged_names
            for token in ("web_search", "fetch_url", "search", "搜索")
        )
        return bool(
            (looks_like_time and has_time_capability)
            or (looks_like_weather and (has_weather_capability or has_web_capability))
            or (looks_like_web and has_web_capability)
        )

    @classmethod
    def resolve_root_cause_status(
        cls,
        *,
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        conversation_turn: dict[str, Any] | None,
    ) -> str:
        diagnostics = sanitize_diagnostics_payload(diagnostics) or {}
        turn_flow = cls._resolve_turn_flow_payload(
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
            call_log=call_log,
        )
        normalized_projection = resolve_failure_projection(
            diagnostics=diagnostics,
            turn_flow=turn_flow,
        )
        conversation_outcome = str(
            normalized_projection.get("turn_outcome")
            or diagnostics.get("conversation_outcome")
            or diagnostics.get("turn_outcome")
            or ""
        ).strip()
        if conversation_outcome in {"failed", "partial"}:
            return "failed"
        if bool(diagnostics.get("assistant_claimed_tool_call_without_tool_event")):
            return "failed"
        if str(diagnostics.get("failure_kind") or "").strip() not in {"", "none"}:
            return "failed"
        if str(diagnostics.get("contract_breach_type") or "").strip():
            return "failed"
        if diagnostics.get("unfinished_intents"):
            return "failed"
        if cls.has_false_direct_reply_signal(diagnostics):
            return "failed"
        if normalized_projection.get("blocks_success_shortcut"):
            return "failed"
        if call_log is None:
            return "success"
        return (
            "success"
            if str(call_log.status or "") == CallStatusEnum.SUCCESS.value
            else "failed"
        )

    @classmethod
    def classify_root_cause(
        cls,
        *,
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        conversation_turn: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str, str | None, float | None]:
        diagnostics = sanitize_diagnostics_payload(diagnostics) or {}
        error_message = str(
            getattr(call_log, "error_message", "") if call_log is not None else ""
        ).strip()
        turn_flow = cls._resolve_turn_flow_payload(
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
            call_log=call_log,
        )
        normalized_projection = resolve_failure_projection(
            diagnostics=diagnostics,
            turn_flow=turn_flow,
        )
        failure_kind = str(
            normalized_projection.get("failure_kind")
            or diagnostics.get("failure_kind")
            or ""
        ).strip()
        contract_breach_type = str(
            diagnostics.get("contract_breach_type") or ""
        ).strip()
        termination_reason = str(
            normalized_projection.get("termination_reason")
            or diagnostics.get("termination_reason")
            or ""
        ).strip()
        budget_exit_reason = str(
            normalized_projection.get("budget_exit_reason")
            or diagnostics.get("budget_exit_reason")
            or ""
        ).strip()
        partial_exit_reason = str(diagnostics.get("partial_exit_reason") or "").strip()
        conversation_outcome = str(
            normalized_projection.get("turn_outcome")
            or diagnostics.get("conversation_outcome")
            or diagnostics.get("turn_outcome")
            or ""
        ).strip()
        provider_events = list(diagnostics.get("provider_events") or [])
        retry_events = list(diagnostics.get("retry_events") or [])
        selected_tools = list(diagnostics.get("selected_tool_names") or [])
        unfinished_intents = list(diagnostics.get("unfinished_intents") or [])
        assistant_claimed_tool_call_without_tool_event = bool(
            diagnostics.get("assistant_claimed_tool_call_without_tool_event")
        )
        has_budget_exit_signal = bool(
            failure_kind == "budget_exit"
            or termination_reason in _BUDGET_TERMINATION_REASONS
            or budget_exit_reason
            or partial_exit_reason in _BUDGET_TERMINATION_REASONS
        )
        research_like = cls.is_research_like_diagnostics(diagnostics)
        false_direct_reply = cls.has_false_direct_reply_signal(diagnostics)
        has_non_budget_provider_event = any(
            str((event.get("kind") if isinstance(event, dict) else event) or "").strip()
            not in {"", "budget_exit"}
            for event in provider_events
        )
        lower_error = error_message.lower()
        if failure_kind in {"", "provider_gateway_error"} and any(
            token in lower_error for token in _PROVIDER_HTTP_5XX_ERROR_TOKENS
        ):
            failure_kind = "provider_http_5xx"
        has_provider_gateway_signal = bool(
            failure_kind in _PROVIDER_GATEWAY_FAILURE_KINDS
            or has_non_budget_provider_event
            or any(
                token in lower_error
                for token in (
                    "provider",
                    "upstream",
                    "timeout",
                    "rate limit",
                    "api key",
                )
            )
        )
        call_log_turn_record = cls._call_log_turn_record(call_log)
        call_log_turn_record_metadata = cls._call_log_turn_record_metadata(call_log)
        protocol_fallback_blocked_reason = str(
            call_log_turn_record_metadata.get("protocol_fallback_blocked_reason") or ""
        ).strip()
        stream_failure_error_type = str(
            call_log_turn_record_metadata.get("stream_failure_error_type") or ""
        ).strip()
        stream_failure_chunk_count = call_log_turn_record_metadata.get(
            "stream_failure_chunk_count",
        )
        try:
            stream_failure_chunk_count = (
                int(stream_failure_chunk_count)
                if stream_failure_chunk_count is not None
                else None
            )
        except (TypeError, ValueError):
            stream_failure_chunk_count = None
        stream_failure_has_meaningful_chunk = bool(
            call_log_turn_record_metadata.get("stream_failure_has_meaningful_chunk")
        )

        if assistant_claimed_tool_call_without_tool_event:
            return (
                "stream_output_contract",
                "assistant_claimed_tool_call_without_tool_event",
                "The assistant claimed it was calling a tool, but no real tool event or tool message followed.",
                "Start with the turn executor contract-breach path and keep the active intent family/tool scope pinned during the recovery retry.",
                0.97,
            )
        if false_direct_reply:
            return (
                "post_processing",
                "planner_false_direct_reply",
                "The planner collapsed a tool-eligible current-information request into direct_reply even though matching runtime capabilities were available.",
                "Fix explicit time/weather/web intent detection before allowing direct_reply short-circuit.",
                0.93,
            )
        if (
            call_log is not None
            and str(call_log.status or "") == CallStatusEnum.SUCCESS.value
            and not normalized_projection.get("blocks_success_shortcut")
            and conversation_outcome not in {"failed", "partial"}
            and not contract_breach_type
        ):
            return (
                None,
                None,
                "The call completed successfully and no blocking failure signal was found.",
                None,
                0.98,
            )
        if (
            normalized_projection.get("non_trusted_final_output_source")
            and not has_budget_exit_signal
            and not has_provider_gateway_signal
        ):
            return (
                "post_processing",
                "untrusted_final_output_source",
                "The turn finished with a non-trusted final output source, so the result cannot be treated as a canonical assistant answer.",
                "Inspect final output salvage and enforce assistant-only final output sources before marking this turn as successful.",
                0.9,
            )
        if (
            (
                (termination_reason == "retry_budget_exhausted")
                or (budget_exit_reason == "retry_budget_exhausted")
                or (partial_exit_reason == "retry_budget_exhausted")
            )
            and unfinished_intents
            and not has_provider_gateway_signal
        ):
            return (
                "research_contract" if research_like else "post_processing",
                "retry_budget_exhausted_with_unfinished_intents",
                "The turn exhausted retry budget while one or more intents were still unfinished.",
                "Start with the unfinished-intent retry policy and stop finalizing the turn while required tool work is still missing.",
                0.95,
            )
        if (
            conversation_outcome == "partial"
            and research_like
            and unfinished_intents
            and not has_provider_gateway_signal
        ):
            return (
                "research_contract",
                "research_partial_finalized_by_orchestrator",
                "The orchestrator finalized the turn as partial even though web research remained unfinished from the user's perspective.",
                "Inspect unfinished intents, fetch_url completion checks, and the partial-exit finalization path before changing prompts.",
                0.94,
            )
        if contract_breach_type:
            lower_contract = contract_breach_type.lower()
            if "research" in lower_contract or "unfinished_intent" in lower_contract:
                return (
                    "research_contract",
                    contract_breach_type,
                    "The turn failed because the web-research contract was not fully satisfied.",
                    "Inspect the agent's web_search/fetch_url tool pair and the unfinished-intent retry rules for this trace.",
                    0.92,
                )
            return (
                "stream_output_contract",
                contract_breach_type,
                "The turn failed because the stream/output contract was breached.",
                "Start with the stream handler and final output contract reconciliation for this trace.",
                0.9,
            )
        if unfinished_intents and not has_provider_gateway_signal:
            return (
                "research_contract",
                failure_kind or "unfinished_intents",
                "The turn exited with unfinished intents that never reached the required completion signal.",
                "Check intent retry / fetch_url completion criteria before changing downstream formatting.",
                0.86,
            )
        if (
            protocol_fallback_blocked_reason == "provider_timeout"
            or (
                "timeout" in lower_error
                and stream_failure_chunk_count == 0
                and not stream_failure_has_meaningful_chunk
            )
            or (
                stream_failure_error_type == "ProviderTimeoutError"
                and stream_failure_chunk_count == 0
                and not stream_failure_has_meaningful_chunk
            )
        ):
            protocol_path = str(
                call_log_turn_record.get("protocol_path")
                or diagnostics.get("protocol_path")
                or ""
            ).strip()
            protocol_text = f" via `{protocol_path}`" if protocol_path else ""
            return (
                "provider_gateway",
                "provider_timeout_before_first_meaningful_chunk",
                "The provider timed out before the first meaningful stream chunk"
                f"{protocol_text}, and runtime blocked protocol fallback for `provider_timeout`.",
                "Inspect upstream provider latency/timeout behavior first; this trace failed before visible model output, not during post-processing.",
                0.97,
            )
        if has_provider_gateway_signal:
            return (
                "provider_gateway",
                failure_kind or "provider_gateway_error",
                "The failure came from the provider gateway or upstream model interaction.",
                "Inspect provider events, model routing, and upstream credentials for this trace first.",
                0.84,
            )
        if not has_budget_exit_signal and (
            selected_tools or "tool" in failure_kind or "tool" in lower_error
        ):
            return (
                "tool_execution",
                failure_kind or "tool_execution_failed",
                "A runtime tool call failed or the tool loop did not converge.",
                "Start with the selected tool payloads and execution logs for the affected turn.",
                0.82,
            )
        if any(
            token in lower_error for token in ("skill", "grant", "resolver", "toolkit")
        ):
            return (
                "skill_resolution",
                failure_kind or "skill_resolution_failed",
                "The turn failed before execution because runtime skills/tools could not be resolved cleanly.",
                "Check agent skill grants and runtime skill resolution for this agent.",
                0.78,
            )
        if any(
            token in lower_error
            for token in ("context", "knowledge base", "memory")
        ):
            return (
                "context_assembly",
                failure_kind or "context_assembly_failed",
                "The turn failed while assembling runtime context.",
                "Inspect context assembly diagnostics, including KB, memory, and runtime context contributors.",
                0.76,
            )
        if has_budget_exit_signal:
            return (
                "post_processing",
                budget_exit_reason
                or partial_exit_reason
                or termination_reason
                or failure_kind
                or "budget_exit",
                "The turn exhausted a runtime budget or exited during finalization.",
                "Tune runtime budgets or remove the stop-loss path that terminated this turn.",
                0.8,
            )
        if retry_events:
            return (
                "post_processing",
                failure_kind or "retry_exhausted",
                "The turn could not recover after runtime retries.",
                "Inspect retry chain diagnostics before changing model prompts or frontend rendering.",
                0.74,
            )
        return (
            "post_processing",
            failure_kind or "unknown_failure",
            "The turn failed after execution, but no narrower failure layer matched.",
            "Start from turn diagnostics and provider/tool evidence on this call log.",
            0.6,
        )

    @staticmethod
    def build_root_cause_evidence(
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        *,
        conversation_turn: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        diagnostics = sanitize_diagnostics_payload(diagnostics) or {}
        evidence: list[dict[str, Any]] = []
        call_log_turn_record = RuntimeRootCauseProjector._call_log_turn_record(call_log)
        call_log_turn_record_metadata = (
            RuntimeRootCauseProjector._call_log_turn_record_metadata(call_log)
        )
        turn_flow = RuntimeRootCauseProjector._resolve_turn_flow_payload(
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
            call_log=call_log,
        )
        normalized_projection = resolve_failure_projection(
            diagnostics=diagnostics,
            turn_flow=turn_flow,
        )

        def append(label: str, value: Any) -> None:
            if value in (None, "", [], {}, ()):
                return
            evidence.append({"label": label, "value": value})

        if call_log is not None:
            append("call_status", call_log.status)
            append("error_message", call_log.error_message)
        if isinstance(conversation_turn, dict):
            append("conversation_message_id", conversation_turn.get("message_id"))
        append("turn_outcome", diagnostics.get("turn_outcome"))
        append("conversation_outcome", diagnostics.get("conversation_outcome"))
        append("termination_reason", diagnostics.get("termination_reason"))
        append("tool_planner", diagnostics.get("tool_planner"))
        append("active_intent_id", diagnostics.get("active_intent_id"))
        append("continuation_source", diagnostics.get("continuation_source"))
        append("failure_kind", diagnostics.get("failure_kind"))
        append("contract_breach_type", diagnostics.get("contract_breach_type"))
        append("final_output_source", normalized_projection.get("final_output_source"))
        append(
            "turn_flow_terminal_stage_type",
            normalized_projection.get("turn_flow_terminal_stage_type"),
        )
        append(
            "turn_flow_terminal_stage_status",
            normalized_projection.get("turn_flow_terminal_stage_status"),
        )
        append(
            "protocol_fallback_blocked_reason",
            call_log_turn_record_metadata.get("protocol_fallback_blocked_reason"),
        )
        append(
            "stream_failure_chunk_count",
            call_log_turn_record_metadata.get("stream_failure_chunk_count"),
        )
        append(
            "stream_failure_has_meaningful_chunk",
            call_log_turn_record_metadata.get("stream_failure_has_meaningful_chunk"),
        )
        append(
            "stream_failure_error_type",
            call_log_turn_record_metadata.get("stream_failure_error_type"),
        )
        append(
            "assistant_claimed_tool_call_without_tool_event",
            diagnostics.get("assistant_claimed_tool_call_without_tool_event"),
        )
        append("budget_exit_reason", diagnostics.get("budget_exit_reason"))
        append("selected_tool_names", diagnostics.get("selected_tool_names"))
        append("candidate_tool_names", diagnostics.get("candidate_tool_names"))
        append("selected_skill_names", diagnostics.get("selected_skill_names"))
        append("unfinished_intents", diagnostics.get("unfinished_intents"))
        append("retry_events", diagnostics.get("retry_events"))
        append("provider_events", diagnostics.get("provider_events"))
        append("fallback_history", diagnostics.get("fallback_history"))
        append("turn_record_protocol_path", call_log_turn_record.get("protocol_path"))
        return evidence

    @staticmethod
    def resolve_overall_status(checks: list[dict[str, Any]]) -> str:
        if any(
            bool(check.get("blocking")) and str(check.get("status")) == "unavailable"
            for check in checks
        ):
            return "red"
        if any(str(check.get("status")) != "available" for check in checks):
            return "yellow"
        return "green"

    @staticmethod
    def build_recommended_actions(
        *,
        checks: list[dict[str, Any]],
        manifest: dict[str, Any],
        recent_failures: list[dict[str, Any]],
    ) -> list[str]:
        actions: list[str] = []
        for check in checks:
            status = str(check.get("status") or "")
            reason = str(check.get("reason") or "").strip()
            name = str(check.get("name") or "").strip()
            if status == "unavailable":
                actions.append(
                    f"Restore `{name}` before relying on runtime diagnostics."
                )
            elif status == "degraded" and reason:
                actions.append(f"Investigate `{name}` degradation: {reason}.")

        for item in manifest.get("disabled_capabilities") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if name and reason:
                actions.append(f"Capability `{name}` is degraded: {reason}.")

        if recent_failures:
            failure_kind = str(recent_failures[0].get("failure_kind") or "unknown")
            actions.append(
                f"Start with the most frequent recent failure kind: `{failure_kind}`."
            )

        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:8]
