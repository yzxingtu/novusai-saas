# Provider Contracts

## Goal

Protocol decisions must be explicit, testable, and owned by one layer.

## Scenario: Protocol Capability Contract Resolution

### 1. Scope / Trigger

- Trigger: provider config includes `wire_api` or `protocol_capabilities`, and
  the runtime must plan a protocol path for chat/stream/embedding/image calls.

### 2. Signatures

- `provider.config.protocol_capabilities`
  - `primary_wire_api: str`
  - `allowed_wire_apis: list[str]`
  - `allowed_cross_protocol_fallbacks: dict[str, list[str]]`
  - `allow_adapter_cross_protocol_fallback: bool`
- `provider.config.wire_api: str | None` (legacy fallback only)
- Runtime-owned flags (set by kernel, not adapters):
  - `_runtime_force_wire_api`
  - `_runtime_disable_cross_protocol_fallback`
  - `_runtime_disable_sync_rescue`

### 3. Contracts

- **Source of truth**: `protocol_capabilities.*` is authoritative when present.
- **Validation**:
  - `protocol_capabilities.primary_wire_api` must be a known protocol token and
    must be included in `allowed_wire_apis`.
  - Invalid tokens in `protocol_capabilities.*` raise
    `ProviderError(code="invalid_protocol_contract")`.
- **Legacy `wire_api`**:
  - Only consulted when `protocol_capabilities` is absent.
  - Must be included in the resolved allowed set; otherwise raise
    `ProviderError(code="unsupported_protocol")`.
  - `wire_api` may **not** widen a responses-only contract.
- **Responses-only providers**:
  - Must publish `allowed_wire_apis=["responses"]` and
    `allow_adapter_cross_protocol_fallback=False`.
  - Adapters must never construct `/chat/completions` for these providers.
- **Fallback map**:
  - When `allow_adapter_cross_protocol_fallback=True` and
    `allowed_wire_apis` has multiple protocols, a full fallback map may be
    auto-generated as a *transitional behavior*. This is not a replacement for
    explicit contracts and should be removed once all providers publish the
    map.
- **Ownership**:
  - The runtime kernel owns protocol planning and fallback decisions.
  - Adapters execute one protocol step and do not invent additional fallback
    strategies.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Unknown token in `protocol_capabilities.*` | Raise `ProviderError(invalid_protocol_contract)` |
| `primary_wire_api` not in `allowed_wire_apis` | Raise `ProviderError(invalid_protocol_contract)` |
| `wire_api` provided but not allowed | Raise `ProviderError(unsupported_protocol)` |
| Responses-only provider receives `chat_completions` request | Hard fail before request |
| `_runtime_disable_cross_protocol_fallback=True` | Planner returns single-protocol plan |
| `_runtime_disable_sync_rescue=True` | No sync rescue on stream failure |

### 5. Required Tests

- Responses-only provider never hits `/chat/completions`.
- Timeout/rate-limit/connection error matrix respects protocol plan.
- Stream and non-stream paths share the same protocol semantics.
- Protocol contract validation raises `ProviderError` for invalid tokens.

## Prohibited Patterns

- Hard-coded `["responses", "chat_completions"]` fallback chains without
  capability gating.
- Adapter-local “sync rescue” that bypasses runtime planner ownership.
- New protocol heuristics hidden in `chat()` / `stream_chat()` instead of the
  runtime planner + capability contract.
- Mixing web-search/image/audio branching into one protocol executor file.
