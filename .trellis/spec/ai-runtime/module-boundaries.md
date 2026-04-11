# Module Boundaries

## Goal

Keep the AI stack modular enough that one subsystem can change without forcing
unrelated rewrites.

## Canonical Layers

1. `contracts`
2. `runtime kernel`
3. `provider layer`
4. `intent + context pipeline`
5. `tool runtime`
6. `application services`
7. `observability`
8. `frontend AI shell`

## Ownership

- `contracts`
  - owns stable DTOs, protocol capability types, intent types, context
    contribution types, turn results, diagnostics projections
- `runtime kernel`
  - owns turn orchestration, protocol planning, round execution, stream
    aggregation, stop-loss decisions
- `provider layer`
  - owns request building, single-protocol execution, response mapping, provider
    error translation
- `intent + context pipeline`
  - owns intent classification, memory/RAG/page/context contribution decisions
- `tool runtime`
  - owns skill resolution, tool catalog building, tool execution, page runtime,
    hosted web-search orchestration
- `application services`
  - owns business commands and query/read models exposed to controllers
- `observability`
  - owns diagnostics projection, replay artifacts, runtime inventory, operator
    views
- `frontend AI shell`
  - owns UI composition and state distribution, but not backend business logic

## Current Canonical Entrypoints (2026-04, Transitional)

- intent classification entrypoint: `backend/app/ai/engine/intent_planner.py`
  (emits `IntentPlan` list; `IntentSet` is target-state only)
- context pipeline entrypoint: `backend/app/ai/context/engine.py` +
  `backend/app/ai/context/orchestrator.py`
- protocol planning: `backend/app/ai/runtime/protocol_planner.py`
- protocol execution (openai-compatible): `backend/app/ai/adapters/openai_compatible/`
- streaming runtime: `backend/app/ai/engine/stream_handler.py` +
  `backend/app/ai/engine/stream_generation_support.py`
- application services: `backend/app/services/ai/*`
- frontend AI shell: `frontend/apps/web-antd/src/components/business/ai-chat-panel/*`
  (split in progress)

## Allowed Dependencies

- `runtime kernel -> contracts`
- `provider layer -> contracts`
- `intent + context pipeline -> contracts`
- `tool runtime -> contracts`
- `application services -> contracts`
- `application services -> runtime kernel`
- `application services -> provider layer`
- `application services -> intent + context pipeline`
- `application services -> tool runtime`
- `observability -> contracts`
- `observability -> application services` only through published read models
- `frontend AI shell -> frontend shared contracts`

## Forbidden Dependencies

- `runtime kernel -> services.ai`
- `provider layer -> runtime kernel strategy modules`
- `intent classifier -> memory/RAG execution side effects`
- `context pipeline -> provider protocol selection`
- `tool runtime -> application service internals`
- `frontend shell -> ad-hoc reconstruction of backend runtime semantics`
- cross-layer imports that bypass a published contract

## Cohesion Rules

- one module should have one dominant reason to change
- if a module simultaneously handles transport, policy, persistence, and UI
  semantics, it is too large
- every facade must delegate to smaller collaborators instead of staying as a
  renamed giant file

## Size Rules

- Python production file target: `<= 600` lines
- provider/protocol file target: `<= 400` lines
- Vue SFC target: `<= 450` lines
- TS composable target: `<= 500` lines
- any production file above `1000` lines is mandatory-split work

## Prohibited Patterns

- one “god service” coordinating commands, queries, persistence, and projection
- adapter-local protocol fallback competing with runtime planner fallback
- intent classification that directly performs retrieval work
- UI shells that contain stream state machine logic inline
- cyclic imports between `app.ai.*` subpackages
