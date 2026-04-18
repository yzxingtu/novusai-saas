# Provider Contracts

## Goal

Protocol decisions must be explicit, validated, and owned by the runtime
kernel, not by adapter-local heuristics.

## Canonical Inputs

- `protocol_capabilities` in provider config:
  `primary_wire_api`, `wire_api` (alias), `allowed_wire_apis`,
  `allowed_cross_protocol_fallbacks`, `allow_adapter_cross_protocol_fallback`.
- Legacy `wire_api` at the provider config root (compat seed only).
- Runtime guard keys carried via ProtocolGuardContract:
  `_runtime_disable_cross_protocol_fallback`, `_runtime_disable_sync_rescue`.
- Runtime-selected protocol path injected as `_runtime_force_wire_api`.

## Contracts

- When `protocol_capabilities` exists, it is the source of truth. Invalid
protocol tokens raise `ProviderError(invalid_protocol_contract)`.
- `protocol_capabilities.wire_api` is a transitional alias for
`primary_wire_api`. It may seed a missing primary but must not widen or override
the contract.
- `primary_wire_api` must be included in `allowed_wire_apis` when an explicit
`allowed_wire_apis` list is provided.
- Legacy top-level `wire_api` is only a seed when the protocol contract is
absent or incomplete. It must not override an explicit contract.
- Runtime overrides that request a protocol outside `allowed_wire_apis` raise
`ProviderError(unsupported_protocol)`.
- Responses-only providers must publish `allowed_wire_apis=["responses"]` and
`allow_adapter_cross_protocol_fallback=False`. Adapters must never send a
`chat/completions` request for those providers.
- Runtime protocol planning requires an explicit
`allowed_cross_protocol_fallbacks` map to schedule a multi-protocol chain. If
the map is empty and a contract exists, the runtime chain stays on the primary
protocol.
- `allow_adapter_cross_protocol_fallback` remains a hard gate. If it is false,
the runtime planner must keep a single-step chain even when a fallback map is
present.
- Adapter-level compatibility may still allow cross-protocol fallback when
`allow_adapter_cross_protocol_fallback` is true and multiple wire APIs are
listed, even if no fallback map is present. This is transitional behavior and
must not be treated as the runtime planner rule.
- Runtime guard keys are enforced by protocol-safe adapter entrypoints. If a
caller tries to set either guard to false, adapters must raise
`ProviderError(invalid_runtime_guard)`.
- `_runtime_force_wire_api` and guard keys are consumed at the adapter boundary
and must not be forwarded downstream as ordinary provider kwargs.
- Responses stream usage backfill is best-effort only. If a terminal
  `response.output_text.done` or `response.completed` event omits usage,
  adapters may issue one bounded retrieve call with retries disabled, then must
  fall back to estimated usage instead of delaying stream completion behind
  long provider-side retry loops.

## Ownership

- The runtime kernel owns protocol planning and fallback decisions.
- Adapters execute one protocol step; they do not invent fallback chains.
- Guard semantics are defined by the runtime kernel and must not be redefined
per adapter.

## Required Diagnostics

- TurnRecord must capture `protocol_path` and `fallback_history`.
- Usage and monitoring surfaces read the protocol path from TurnRecord, not
from adapter-local metadata.

## Prohibited Patterns

- Adapter-local fallback chains that bypass the runtime planner.
- Treating the legacy no-contract fallback chain as the canonical rule.
- Allowing callers to disable runtime guards at adapter entrypoints.
- Using top-level `wire_api` to override an explicit protocol contract.
- Mixing multiple protocols inside a single adapter call.
