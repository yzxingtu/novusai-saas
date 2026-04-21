# Responses Tool History Compat Retirement

## Goal

Retire the remaining runtime path that rewrites Responses tool-call history into
assistant text compatibility mode so the OpenAI-compatible adapter keeps one
canonical structured tool-history contract for the new SaaS.

## Requirements

- Provider runtime behavior must no longer depend on
  `responses_tool_history_mode=text` as an ordinary supported mode.
- Responses follow-up turns should preserve canonical structured tool history
  unless a narrowly scoped, explicitly documented low-level rescue path is kept.
- Admin/provider surfaces must not persist or suggest this compatibility mode as
  a supported product setting.
- Tests should validate the surviving structured owner chain and any remaining
  explicitly allowed rescue logic.

## Acceptance Criteria

- The default and supported Responses input conversion path uses structured
  function-call / function-call-output history only.
- Provider config no longer promotes `responses_tool_history_mode=text` as a
  normal runtime option.
- Compat-only tests are either removed or rewritten against the intended
  canonical contract.
- Trellis/backend or AI-runtime spec is updated if the resulting runtime shape
  becomes the stable documented rule.
