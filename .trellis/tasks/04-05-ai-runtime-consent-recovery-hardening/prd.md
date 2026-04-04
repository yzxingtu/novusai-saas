# AI Runtime Consent Recovery Hardening

## Goal

Harden the current AI runtime so consent-gated tool calls pause cleanly instead of degrading into retry/partial-exit flows, while also fixing the verified runtime bugs from the audit pass and preserving current structured orchestration behavior.

## Requirements

1. Consent-gated tool calls must be treated as a pause state, not as ordinary tool failure.
2. Fast-path turns must not emit partial-exit output solely because a consent prompt is pending.
3. Recovery/diagnostic state must record pending consent explicitly enough for conversation history, monitoring, and resume flows to stay coherent.
4. User-visible partial output must not expose the internal `[PARTIAL EXIT]` contract text.
5. The fast-path elapsed budget should match current provider latency reality.
6. The verified dynamic capability awareness bug must be fixed with regression coverage.
7. Verified Decimal call-log serialization failures must be fixed with regression coverage.
8. Any issue that cannot be fixed in code because it is operational/config-owned or absent from the repo must be explicitly documented in the final result instead of being guessed.

## Acceptance Criteria

- A weather turn that reaches pending consent exits the engine in a resumable pending-consent state without retry-budget exhaustion.
- A mixed multi-intent turn with one consent-gated tool does not emit a partial-exit assistant message just because consent is pending.
- Partial outputs shown to users are natural-language text, not raw contract markers.
- Targeted backend tests cover the new consent pause semantics, user-facing partial-output rendering, and the verified bug fixes.
- The change does not revert unrelated user edits already present in the working tree.
