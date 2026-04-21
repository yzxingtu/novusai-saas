# Codex Page-Session Join Handshake Freeze

## Goal

Freeze the page-session join handshake to the same live identity contract that
WS4 already applied to action transport: explicit `page_session_id` only.
`page_key` may remain in thin page context and read-model metadata, but it
should no longer participate in join acknowledgement or page-op readiness.

## Current Gap

WS4 removed `page_key` from live action payloads and deleted the old
`page_key -> page_session_id` recovery path, but one connector seam still
remains:

1. frontend `use-ui-action-channel.ts` still emits `page_key` in
   `page_session_join` and stores join acknowledgement keyed by
   `(page_session_id, page_key)`;
2. backend `page_session.py` still echoes `page_key` in
   `page_session_joined`;
3. `use-ai-chat-page-operations.ts` still waits for join readiness through that
   page-key-bearing handshake.

For a new SaaS runtime, this is not a compatibility layer we should preserve.

## Write Scope

- `frontend/apps/web-antd/src/composables/use-ui-action-channel.ts`
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat-page-operations.ts`
- `backend/app/sio/page_session.py`
- related frontend/backend page-session join tests

## Requirements

1. `page_session_join` and `page_session_joined` must use `page_session_id` as
   the only live handshake identity field.
2. frontend join acknowledgement storage, readiness polling, and rejoin logic
   must no longer depend on `page_key`.
3. no fallback or compatibility shim may keep page-key-based join readiness
   alive for current live turns.
4. canonical specs and umbrella tracking must be updated when the new handshake
   contract lands.

## Acceptance

1. frontend no longer sends or waits on `page_key` for page-session join.
2. backend join acknowledgement no longer echoes `page_key`.
3. page-operation readiness continues to work across reconnect/rejoin flows
   using only `page_session_id` and socket/runtime facts.
4. backend/frontend regression tests cover the join handshake contract.
