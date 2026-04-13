"""Replay and immediate-event helpers for stream generation finalization."""

from __future__ import annotations

from typing import Any

from app.ai.sse import SSEChunkEncoder


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
    return events


def build_replay_events(
    *,
    streamed_output: str,
    finalized_output: str,
    final_output_source: str | None,
    partial_reply_stream_chunks: list[str],
    completed_reply_stream_chunks: list[str],
) -> list[str]:
    should_clear_replayed_output = bool(
        streamed_output
        and finalized_output
        and finalized_output != streamed_output
        and final_output_source in {"tool_evidence_completed", "budget_fallback"}
        and (partial_reply_stream_chunks or completed_reply_stream_chunks)
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
