# Turn-Flow Legacy Projection Closeout

## Goal

Retire the live frontend/runtime path that mutates canonical assistant
`turnFlow` back into legacy chat message fields so the new SaaS keeps one
unified assistant-process protocol.

## Requirements

- Streaming SSE handlers, chat lifecycle helpers, and finalize/merge paths must
  stop treating `reconcileTurnFlowWithLegacy()` / `applyLegacyFieldsFromTurnFlow()`
  as normal live-state mutation owners.
- Shared chat UI should render timeline/evidence/process details from canonical
  `turnFlow` selectors rather than depending on legacy `thinkingContent`,
  `optimizingTools`, `ragSources`, or `toolCalls` synthesized from turnFlow.
- Any remaining legacy field support must be bounded to reading truly old
  persisted payloads, not re-projecting fresh canonical runtime data back into
  legacy shapes.
- Legacy `legacy-*` stage/source markers and helper shims should be reduced or
  removed where they are no longer needed after canonical renderers become the
  only live path.
- Regression coverage should prove that live stream/history message assembly can
  operate from canonical `turnFlow` without rehydrating legacy fields.

## Acceptance Criteria

- No live frontend chat runtime path mutates freshly built canonical `turnFlow`
  into legacy message fields as the primary truth source.
- Canonical timeline/evidence renderers remain complete for stream, history,
  and persisted conversation replay.
- Compatibility handling for old stored messages is explicit and read-only,
  rather than mixed into normal forward runtime assembly.
- Tests cover the surviving canonical contract and fail if legacy back-projection
  becomes required again.
