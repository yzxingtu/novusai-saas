# Service Layer

## Goal

AI application services expose business use cases, persistence seams, and
operator read models. Runtime protocol planning and low-level policy stay in
the runtime/kernel packages.

## Stable Facades And Parts

Service modules follow a stable facade plus parts layout. Keep the facade names
stable for imports and API wiring, then push logic down into command/query/
projector/support modules.

Observed stable facades:

- `backend/app/services/ai/agent_chat_service.py`
- `backend/app/services/ai/conversation_service.py`
- `backend/app/services/ai/monitoring_service.py`
- `backend/app/services/ai/runtime_diagnostics_service.py`
- `backend/app/services/ai/runtime_inventory_service.py`
- `backend/app/services/ai/runtime_cli_bridge.py`

Observed parts and support seams:

- command orchestration: `agent_chat_command_service.py`,
  `agent_chat_stream_bootstrap_service.py`, `agent_chat_stream_support.py`
- query services: `agent_chat_query_service.py`,
  `monitoring_*_query_service.py`, `runtime_diagnostics_query_service.py`
- projectors: `agent_chat_turn_projection_service.py`,
  `agent_chat_turn_projection_support.py`,
  `conversation_diagnostics_projector.py`,
  `monitoring_read_model_projector.py`,
  `runtime_diagnostics_turn_projector.py`
- conversation facade mixins: `conversation_facade_mixins.py`,
  `conversation_read_model_service.py`
- runtime supports: `agent_chat_runtime_support.py` plus focused helper modules
  (billing, memory, interaction, trust policy)

## Runtime Capability Manifest And Inventory

Runtime capability manifest building is a service-layer responsibility, but the
payload is built from runtime contracts.

Rules:

- `RuntimeInventoryService` builds a runtime capability manifest from
  `app.ai.runtime` contracts. It resolves agent, model, provider, KB bindings,
  tool/skill selections, and context state, then delegates to
  `AIRuntimeInventoryService.build_manifest(...)`.
- The service is responsible for shaping provider/model/knowledge-base/extension
  payloads and manifest `summary` fields, but it must not re-implement runtime
  policy.
- Extension entries are derived from tool/skill metadata (plugin and package
  sources) and are reported as read-model inventory only.
- Manifest assembly is read-only. It must not mutate chat state, call engines,
  or write logs.
- The manifest is the canonical read model for runtime capability inventory.
  Other services (doctor/smoke/diagnostics) consume it rather than rebuilding
  ad-hoc summaries.
- Scope is explicit (`runtime` vs `cli`). The service normalizes scope values
  without adding policy.

## Runtime CLI Bridge

CLI bridging is a thin adapter, never the owner of business logic.

Rules:

- `AIRuntimeCliBridge` only routes CLI operations to existing services. It uses
  dynamic imports and gracefully returns `not_available` fallbacks.
- The CLI bridge must not query the database or build manifests itself. It
  instantiates services and forwards the request.
- Dispatch adapts `RuntimeCliScope` into method kwargs only when the service
  method accepts those parameters (signature-aware routing).
- `RuntimeCliScope` is a pure transport container. It only carries `tenant_id`,
  `agent_id`, and `agent_code` and is safe to pass across CLI boundaries.
- If no candidate service exists, the bridge returns a safe fallback or raises
  a `RuntimeCliDependencyMissing` error with candidate references.

## Command Vs Query Vs Projection

Command services:

- Orchestrate live execution, validation, and persistence.
- Example: `AgentChatCommandService` drives chat/stream execution,
  writes conversation messages, updates stats, and triggers memory capture.
- Streaming orchestration and preflight are isolated in
  `AgentChatStreamBootstrapService` and `AgentChatStreamPersistenceOrchestrator`.

Query services:

- Read-only, no orchestration, no persistence.
- Example: `AgentChatQueryService` validates agent state and sanitizes
  knowledge-base IDs; monitoring and diagnostics query services pull lists and
  call-log data.

Projectors:

- Convert raw models/logs into read models and diagnostics payloads.
- Example: `AgentChatTurnProjectionService` builds `context_diagnostics` and
  `last_run_summary`. `MonitoringReadModelProjector` and
  `RuntimeDiagnosticsTurnProjector` normalize call-log and conversation-turn
  diagnostics into operator-facing shapes.

Support modules:

- Provide narrowly-scoped helpers to keep facades small.
- Example: `AgentChatRuntimeSupport` delegates billing, memory, and trust-policy
  helpers to focused modules.

## Diagnostics And Read-Model Flow

Diagnostics data flows through stable read-model channels:

- Command services write turn diagnostics and summaries into conversation
  persistence (`context_diagnostics`, `last_run_summary`, `turn_record`, etc.).
- Call logs carry request metadata; monitoring and diagnostics projectors read
  `turn_diagnostics` and related fields from that payload.
- Monitoring services aggregate call logs and conversation detail, then project
  actor identity using snapshot-first logic.
- Call-trace details are projected with `MonitoringCallTraceProjector` and
  query filters are centralized in `MonitoringQuerySupport` to avoid duplicate
  filter logic in controllers.
- Runtime diagnostics services merge conversation-turn diagnostics with call-log
  diagnostics to generate root-cause output and recommended actions.
- Manifest checks in runtime diagnostics are derived from the inventory manifest
  and stored check support helpers.
- Diagnostics service orchestration may trigger registry maintenance tasks
  (for example, starter pack sync), but those actions remain explicit opt-in
  entrypoints.

## Error And Status Flow

- Command services raise `BusinessException`/`NotFoundException` for user-facing
  failures and allow log/persistence guards to convert them into response
  payloads.
- Diagnostics services use call-log status, turn diagnostics, and conversation
  metadata to classify failures. They must not infer runtime policy from
  controller parameters or frontend flags.
- Read models must be snapshot-first for actor identity; live identity data is
  a fallback only.

## Required Split

- compatibility facades that preserve stable public service names
- command services for chat execution, streaming, and memory persistence
- query services for conversation history, monitoring, and runtime diagnostics
- projection services for read models and operator-friendly diagnostics
- orchestration and support modules for stream bootstrapping and post-turn
  side effects
- runtime helper delegation to `app.ai.runtime` contracts for shared policies

## Core Service Responsibilities

- Build request context, call the engine or runtime kernel, and persist results.
- Inject session memory context before context assembly.
- Hydrate persisted thread/session memory policy (for example polluted memory
  mode) before context assembly, even when session-memory prompt text is not
  injected into the current turn.
- Persist session memory and long-term memory capture after the turn.
- When streaming persistence uses a separate callback/session for conversation
messages, any post-turn long-term memory writes that still use the primary
request DB session must be explicitly committed or rolled back in that tail
path.
- Project turn diagnostics and read models for monitoring and operators.
- Assemble runtime capability manifests for operator tooling and CLI surfaces.

## Rules

- Controllers depend on command or query services, not engine internals.
- Query services must not execute live orchestration.
- Command services must not rebuild frontend view models; use projectors.
- Service-to-service coupling must go through stable contracts.
- When a service becomes a facade, new logic belongs in support or projector
  modules rather than growing the facade.
- Facades and facade-mixin modules must bind directly to their extracted
  collaborators. Dynamic self-import of the facade module to recover service
  classes, parser functions, or logging helpers is compatibility debt, not an
  allowed live owner pattern.
- Shared policy logic belongs in runtime helper contracts, not copied into
  services.
- Memory-related service helpers must reuse
  `app.ai.runtime.memory_policy` for polluted-mode normalization and
  external-context policy reads; do not re-declare trigger registries or raw
  `memory_context_polluted` / `memory_pollution_reason` cleanup in each
  service/support file.
- Conversation-level polluted mode belongs in a dedicated memory-policy store
  service. `SessionMemoryService` owns session-memory facts only; it must not
  remain a side-channel persistence owner for polluted-mode truth.
- `ConversationService` clear/read paths should depend on
  `ConversationMemoryStateService`; raw `SessionMemoryService` stays the
  lower-level fact store behind that helper instead of re-entering the
  conversation facade as a patch-compat shim.
- Conversation memory services must distinguish non-destructive polluted-mode
  reset from full conversation-memory clear. Resetting policy state may keep
  session-memory facts, while clear/delete paths remove both session-memory
  facts and conversation-policy state.
- The service-layer transport contract must preserve that split:
  `DELETE .../memory-state` clears both stores, while
  `POST .../memory-state/reset-pollution` returns the refreshed merged
  `MemoryState` read model after clearing only conversation-level polluted mode.
- CLI bridge modules may not become logic owners; they only delegate.

## Expected Shape

- Agent chat service as a facade over runtime support helpers, memory support,
  and stream persistence helpers.
- Conversation service as a facade over query and projector seams.
- Monitoring services as query plus projector pairs.
- Diagnostics services as query plus projector pairs for runtime insights.
- Runtime inventory service as the owner of capability manifests, consumed by
  diagnostics and CLI.

## Prohibited Patterns

- One service owning routing, execution, billing, memory, and projection in a
  single file.
- Query services performing mutations or orchestration.
- Service-local copies of protocol, trust, or tool-risk logic that drift from
  runtime contracts.
- CLI bridge embedding read-model or diagnostics logic instead of delegating.
