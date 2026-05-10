# Provider Contracts

## Goal

Protocol decisions must be explicit, validated, and owned by the runtime
kernel, not by adapter-local heuristics.

## Canonical Inputs

- `protocol_capabilities` in provider config:
  `primary_wire_api`, `allowed_wire_apis`,
  `allowed_cross_protocol_fallbacks`, `allow_adapter_cross_protocol_fallback`.
- Runtime guard keys carried via ProtocolGuardContract:
  `_runtime_disable_cross_protocol_fallback`, `_runtime_disable_sync_rescue`.
- Runtime-selected protocol path injected as `_runtime_force_wire_api`.

## Contracts

- When `protocol_capabilities` exists, it is the source of truth. Invalid
protocol tokens raise `ProviderError(invalid_protocol_contract)`.
- `primary_wire_api` must be included in `allowed_wire_apis` when an explicit
`allowed_wire_apis` list is provided.
- Top-level `wire_api` is retired for new runtime config. Provider setup must
publish `protocol_capabilities.primary_wire_api`; runtime code must not infer a
live protocol contract from old root-level fields.
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
- Adapter-level cross-protocol fallback is retired. Adapters execute only the
runtime-planned protocol step; multi-protocol chains require an explicit
runtime `allowed_cross_protocol_fallbacks` plan.
- Runtime guard keys are enforced by protocol-safe adapter entrypoints. If a
caller tries to set either guard to false, adapters must raise
`ProviderError(invalid_runtime_guard)`.
- Public OpenAI-compatible adapter entrypoints expose only protocol-safe
  chat/stream surfaces. Retired compat entrypoints and package-level re-export
  shims are not part of the supported public contract.
- `_runtime_force_wire_api` and guard keys are consumed at the adapter boundary
and must not be forwarded downstream as ordinary provider kwargs.
- Responses follow-up turns must preserve structured `function_call` /
  `function_call_output` history. Adapters must not rewrite prior tool rounds
  into assistant text compatibility mode as a normal runtime behavior.
- Responses stream usage backfill is best-effort only. If a terminal
  `response.output_text.done` or `response.completed` event omits usage,
  adapters may issue one bounded retrieve call with retries disabled, then must
  fall back to estimated usage instead of delaying stream completion behind
  long provider-side retry loops.
- Gateway exception conversion must preserve the effective upstream HTTP status
  for provider-side 4xx failures. Auth/quota/permission or invalid-request
  errors must not be reclassified into `provider_http_5xx`; only true upstream
  5xx responses may surface as `provider_http_5xx` in diagnostics or turn
  failure kinds.
- Runtime model failover may prefer an explicit `fallback_model_id` chain, but
  missing or exhausted chain links must fall through to the healthy compatible
  model pool. Absence of a per-model chain is not a valid reason to skip
  runtime failover when another active model satisfies the turn capability
  requirements.
- Runtime model failover must not carry the original model's forced protocol
  selection (`_runtime_force_wire_api` / `_runtime_force_protocol_path`) into the
  fallback adapter call. The fallback provider/model resolves its own
  `protocol_capabilities.primary_wire_api`; runtime guard keys such as
  `_runtime_disable_cross_protocol_fallback` still travel with the call.
- Provider-native or hosted web search is removed from AI dialogue runtime
  contracts. Provider configs and protocol capabilities must not expose hosted
  search, native search, `SearchProvider`, or search/fetch support as callable
  runtime capabilities for new turns.
- `openai_compatible` and Responses-style providers must not assemble hosted
  search request payloads, enable web-search tools because a model appears
  compatible, or forward search-specific provider kwargs. Stale config keys such
  as hosted-search support flags are unsupported and must be ignored or rejected
  at the runtime boundary rather than treated as activation.
- Adapter-specific events such as `response.web_search_call.*` may remain only
  in historical trace diagnostics. They are not completion evidence, progress
  evidence, or a provider capability signal for new AI dialogue turns.

## Ownership

- The runtime kernel owns protocol planning and fallback decisions.
- Adapters execute one protocol step; they do not invent fallback chains.
- Online search has no live runtime owner. Intent/tool orchestration must fail
  closed for online-search prompts, and adapters must never decide to activate,
  retry, or replace that removed capability.
- Guard semantics are defined by the runtime kernel and must not be redefined
per adapter.
- Low-level helpers may remain only for serialization, parsing, and historical
  diagnostics. They must not preserve retired live behavior or be promoted as
  package-level entrypoints again.

## Required Diagnostics

- TurnRecord must capture `protocol_path` and `fallback_history`.
- Usage and monitoring surfaces read the protocol path from TurnRecord, not
from adapter-local metadata.

## Prohibited Patterns

- Adapter-local fallback chains that bypass the runtime planner.
- Any hosted/native search, `SearchProvider`, or search/fetch execution chain
  for AI dialogue live paths.
- Hosted/native web search enabled for OpenAI-compatible gateways.
- Treating stale hosted-search config or provider search-progress events as a
  runtime capability.
- Treating a no-contract fallback chain as a valid runtime rule.
- Allowing callers to disable runtime guards at adapter entrypoints.
- Using top-level `wire_api` to create or override a runtime protocol contract.
- Mixing multiple protocols inside a single adapter call.
