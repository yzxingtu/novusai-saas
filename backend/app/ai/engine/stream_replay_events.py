# FROZEN: do not add new dependencies
"""Replay and immediate-event helpers for stream generation finalization."""

from __future__ import annotations

from typing import Any

from app.ai.sse import SSEChunkEncoder

from .final_output_policy import is_trusted_assistant_final_output_source
from .stream_error_utils import trace_payload as _trace_payload
from .turn_flow_projector import build_turn_evidence_events


def build_immediate_turn_events(
    *,
    action_buttons: list[dict[str, Any]] | None,
    rag_sources: list[dict[str, Any]] | None,
) -> list[str]:
    events: list[str] = []
    if action_buttons:
        events.append(
            SSEChunkEncoder.encode(
                {
                    "event": "action_buttons",
                    "buttons": action_buttons,
                }
            )
        )
    if rag_sources:
        events.append(
            SSEChunkEncoder.encode(
                {
                    "event": "rag_sources",
                    "sources": rag_sources,
                }
            )
        )
        for canonical_event in build_turn_evidence_events(rag_sources):
            events.append(SSEChunkEncoder.encode(_trace_payload(canonical_event)))
    return events


def build_replay_events(
    *,
    streamed_output: str,
    finalized_output: str,
    final_output_source: str | None,
    partial_reply_stream_chunks: list[str],
    completed_reply_stream_chunks: list[str],
) -> list[str]:
    streamed = str(streamed_output or "").strip()
    finalized = str(finalized_output or "").strip()
    has_replay_chunks = bool(partial_reply_stream_chunks or completed_reply_stream_chunks)
    overlapping_outputs = bool(
        streamed
        and finalized
        and (streamed.startswith(finalized) or finalized.startswith(streamed))
    )
    should_clear_replayed_output = bool(
        streamed
        and finalized
        and finalized != streamed
        and has_replay_chunks
        and (
            is_trusted_assistant_final_output_source(final_output_source)
            or bool(completed_reply_stream_chunks)
        )
        and not overlapping_outputs
    )

    events: list[str] = []
    if should_clear_replayed_output:
        events.append(SSEChunkEncoder.encode({"event": "clear_content"}))
    for chunk in partial_reply_stream_chunks:
        events.append(SSEChunkEncoder.encode({"event": "message", "delta": chunk}))
    for chunk in completed_reply_stream_chunks:
        events.append(SSEChunkEncoder.encode({"event": "message", "delta": chunk}))
    return events


__all__ = ["build_immediate_turn_events", "build_replay_events"]
