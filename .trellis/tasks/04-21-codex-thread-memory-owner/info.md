# Codex Thread Memory Owner Notes

## Design Freeze

This deep-path task converges thread memory ownership around one public owner
chain:

1. `ExecutionResult.memory_runtime_policy` is the only runtime result field
   that command/stream persistence may read.
2. Assistant message metadata persists the normalized
   `memory_runtime_policy` snapshot for turn-scoped diagnostics.
3. Conversation `metadata_.thread_memory_state` persists the thread-owned
   snapshot so detail/error-only paths can still project the latest owner state
   even when an assistant row is missing.

## Audit Follow-Up

The 2026-04-21 audit closed two narrow seams without reopening legacy paths:

1. Stream completion no longer relies on the private
   `_memory_runtime_policy` side channel when cloning/persisting
   `ExecutionResult`.
2. Marker-only stream error fallback mirrors `thread_memory_state` onto
   conversation metadata, so the narrowest fallback path still preserves the
   canonical thread owner snapshot.

## Non-Goals

- Do not re-embed memory ownership into page hints, prompt-only recovery, or
  page-local context flags.
- Do not reintroduce private `ExecutionResult` side channels for memory state.
