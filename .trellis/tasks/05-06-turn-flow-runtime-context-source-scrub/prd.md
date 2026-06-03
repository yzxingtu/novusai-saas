# Scrub Runtime Context Diagnostics From Turn-Flow Evidence

## Problem

Conversation `2340` used no online-search tools after online search removal, but
the user-facing process UI still showed source progress and a completed-looking
state. CLI diagnostics prove the real turn failed at the provider layer:

- `intent=direct_reply`
- `selected_tool_names=[]`
- `candidate_tool_names=[]`
- `tool_rounds_used=0`
- `failure_kind=provider_unavailable`

The bad projection came from `context_sources` entries such as
`skill_resolver`, inactive `long_term_memory`, and `runtime_model_capability`
being converted into evidence/source chips.

## Goals

1. Runtime `context_sources` stay diagnostics/inventory only.
2. User-facing evidence comes only from real RAG sources, real tool results, or
   explicit canonical evidence events.
3. Existing polluted `turn_flow` payloads are scrubbed when normalized.
4. Provider-failed turns render as error/异常 even when a partial text string is
   present.
5. The exact conversation `2340` failure shape has a permanent regression test.

## Non-Goals

- Do not restore online search.
- Do not add provider-native search or fetch fallback.
- Do not hide genuine KB/RAG evidence or real tool evidence.

## Acceptance

- The new backend regression for `BUG-2026-05-06-2340` fails before the fix and
  passes after the fix.
- Chat kernel regression fails before the fix and passes after the fix.
- CLI inspection of conversation `2340` shows no selected/candidate tools, no
  tool rounds, and no fake evidence/source chips in the projected turn flow.
- Playwright real browser check shows the conversation UI no longer displays
  completed/source-count chrome for the provider failure.
