"""Monitoring call-trace read-model projector helpers."""

from __future__ import annotations

from typing import Any

from app.schemas.ai.monitoring import MonitoringCallTraceItem
from app.services.ai.monitoring_read_model_projector import (
    MonitoringReadModelProjector,
)


class MonitoringCallTraceProjector:
    """Build stable monitoring call-trace payloads from call-log rows."""

    @classmethod
    def build_item(cls, row: Any) -> MonitoringCallTraceItem:
        request_metadata = (
            row.request_metadata if isinstance(row.request_metadata, dict) else {}
        )
        response_payload = (
            request_metadata.get("response")
            if isinstance(request_metadata.get("response"), dict)
            else {}
        )
        trace_diagnostics = MonitoringReadModelProjector.extract_call_trace_diagnostics(
            request_metadata
        )
        return MonitoringCallTraceItem(
            id=row.id,
            created_at=row.created_at,
            status=row.status,
            request_type=row.request_type,
            model_name=row.model_name,
            provider_name=row.provider_name,
            total_tokens=MonitoringReadModelProjector.safe_int(row.total_tokens),
            cost=MonitoringReadModelProjector.safe_float(row.cost),
            latency_ms=row.latency_ms,
            usage_mode=response_payload.get("usage_mode"),
            error_message=row.error_message,
            turn_outcome=trace_diagnostics.get("turn_outcome"),
            termination_reason=trace_diagnostics.get("termination_reason"),
            protocol_path=trace_diagnostics.get("protocol_path"),
            selected_tool_names=trace_diagnostics.get("selected_tool_names") or [],
            selected_skill_names=trace_diagnostics.get("selected_skill_names") or [],
            execution_path=trace_diagnostics.get("execution_path"),
            intent_plan=trace_diagnostics.get("intent_plan") or [],
            budget=trace_diagnostics.get("budget"),
            budget_status=trace_diagnostics.get("budget_status"),
            budget_exit_reason=trace_diagnostics.get("budget_exit_reason"),
            candidate_tool_names=trace_diagnostics.get("candidate_tool_names") or [],
            context_sources=trace_diagnostics.get("context_sources") or [],
            fallback_history=trace_diagnostics.get("fallback_history") or [],
            retry_events=trace_diagnostics.get("retry_events") or [],
            partial_exit_reason=trace_diagnostics.get("partial_exit_reason"),
            failure_kind=trace_diagnostics.get("failure_kind"),
            provider_events=trace_diagnostics.get("provider_events") or [],
            sync_rescue=trace_diagnostics.get("sync_rescue"),
            should_record_call_log=trace_diagnostics.get("should_record_call_log"),
            contract_breach_type=trace_diagnostics.get("contract_breach_type"),
            tool_leak_detected=bool(trace_diagnostics.get("tool_leak_detected")),
            unfinished_intents=trace_diagnostics.get("unfinished_intents") or [],
            leaked_tool_names=trace_diagnostics.get("leaked_tool_names") or [],
            recovered_via_retry=trace_diagnostics.get("recovered_via_retry"),
            last_tool_name=trace_diagnostics.get("last_tool_name"),
            interrupted_stage=trace_diagnostics.get("interrupted_stage"),
            tool_loop_progress=trace_diagnostics.get("tool_loop_progress"),
            turn_record=trace_diagnostics.get("turn_record"),
        )


__all__ = ["MonitoringCallTraceProjector"]
