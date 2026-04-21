# Codex Turn Loop Convergence Notes

## Design Freeze

The chat core should expose one canonical runtime contract across sync and
stream paths:

1. command entrypoints depend on canonical runtime owners directly;
2. stream persistence delegates through canonical conversation persistence
   contracts;
3. callers project runtime outputs, but do not probe for alternate owner
   shapes or rebuild a second persistence truth.

## Audit Follow-Up

The 2026-04-21 audit removed two remaining compat seams from the live path:

1. `AgentChatCommandService` no longer resolves `ExecutionDispatcher`,
   `AgentQuotaManager`, `AgentStatsManager`, or `AgentConcurrencyLimiter`
   through `agent_chat_service` compat re-exports.
2. `AgentChatStreamPersistenceOrchestrator` and its error-support helpers no
   longer branch on old-shape `ConversationService` capability probes; they now
   call the published `persist_stream_completion`,
   `persist_stream_last_error_marker`, and `save_stream_error_message`
   contract directly.

## Non-Goals

- Do not reintroduce compat-layer import indirection into live chat entrypoints.
- Do not keep dual persistence implementations around “just in case” for the
  new SaaS runtime.
