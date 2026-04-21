# OpenAI Legacy Compat Closeout

## Goal

Retire the remaining explicit OpenAI adapter legacy compatibility surfaces so
the new SaaS runtime keeps a single protocol-safe owner chain instead of
shipping legacy compat as a first-class package contract.

## Requirements

- Keep `backend/app/ai/adapters/openai_adapter.py` public `chat()` and
  `stream_chat()` protocol-safe only; no hidden re-entry into legacy planner or
  fallback paths.
- Remove or quarantine explicit legacy compat entrypoints and compatibility
  re-export modules that are no longer part of the live runtime owner chain.
- If any low-level fallback helper is still genuinely needed, move it under the
  protocol-safe owner modules instead of preserving `legacy_compat`-style
  public entrypoints.
- Update tests to validate the surviving owner chain, not the retired
  compatibility facades.
- Update canonical AI runtime/backend spec only if the resulting package/export
  shape becomes the new stable rule.

## Acceptance Criteria

- No live runtime path depends on `openai_compatible.compat/**` or explicit
  `*_legacy_compat` adapter entrypoints.
- Package re-exports no longer promote legacy compat helpers as ordinary public
  adapter surface unless an explicit documented compatibility waiver remains.
- Tests cover the intended protocol-safe fallback/rescue behavior through the
  surviving owner modules.
- Any removed surface is reflected in Trellis spec/task notes so future work
  does not reintroduce it casually.
