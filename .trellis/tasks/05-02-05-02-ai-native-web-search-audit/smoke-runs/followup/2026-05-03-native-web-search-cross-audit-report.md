# Historical Only

This smoke report is superseded by the 05-05 and 05-08 online-search
retirement work. Do not use it as current acceptance, current smoke
expectation, or evidence to restore WebResearch, provider-hosted/native search,
`web_search`, or `fetch_url`.

# Native Web Search Cross-Audit Follow-up

Date: 2026-05-03

## Scope

Follow-up audit target: AI dialogue native Responses hosted web search vs
builtin/skill web-search routing.

User-facing contract:

- Generic current-information / web-research prompts prefer provider-native
  Responses hosted `web_search` when the active OpenAI-compatible provider and
  effective model support it.
- Builtin/skill `web_search` / `fetch_url` are first-round tools only when the
  user explicitly asks to use/call the builtin/search tool/skill path, or when
  native hosted search is unavailable/fails.
- Native evidence must complete `web_research` without causing redundant
  builtin retries.

## Six-Way Cross-Audit Findings

- Route policy: generic native-first and explicit builtin-first were correct,
  but short phrase matching misclassified some prompts where "search tool" was
  the research subject.
- Responses payload/stream: forced hosted payload stripped function tools
  correctly. Stream `response.output_text.done` needed citation/usage evidence
  backfill when compatible gateways omit `response.completed`.
- Runtime fallback: hosted search timeout, connection failure, progress-only,
  and Responses-only fallback paths were already covered and bounded on the
  main OpenAI-compatible runtime path.
- Test discipline: deterministic contract coverage is strong, but it remains
  distinct from real-dialogue smoke. This run therefore re-executed the browser
  C1 smoke against a fresh backend after the fixes.
- Frontend e2e: C1 is a real Chromium + real backend SSE path; it verifies
  search execution evidence or graceful hosted-search closure plus a non-empty
  final answer, not full citation-card visibility.
- Provider/config availability: main dialogue native availability checks were
  correct. Dedicated `web_search` readiness for trusted OpenAI-compatible hosts
  was tightened to require Responses support and respect
  `web_search.enabled=False`.

## Fixes Applied

- `request_policy.py` now ignores builtin/tool/skill phrases when they occur as
  the research subject, for examples such as "联网搜索如何使用搜索工具的最新资料"
  and "search how to call web search tool from Responses API".
- Responses stream handling now marks native hosted search evidence from
  `response.output_text.done` URL citations / tool usage and bounds direct
  required-output streams with the default stream timeout.
- Native readiness now rejects trusted OpenAI-compatible providers that do not
  support Responses or have provider-level web search disabled.
- Test coverage was extended for the above behavioral and structural contracts.

## Commands Run

Backend behavioral / structural target set:

```powershell
cd backend
python -m pytest -p no:cacheprovider tests/ai/test_web_search_request_policy.py tests/ai/test_web_search_native_readiness.py tests/ai/test_web_search_orchestrator.py tests/ai/engine/test_tool_router.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_protocol_runtime_context.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/adapters/test_openai_native_web_search_parser.py tests/ai/adapters/test_openai_responses_stream_support.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_ai_provider_service.py tests/ai/engine/test_protocol_turn_session.py tests/ai/engine/test_query_engine_partial_contract.py tests/services/test_conversation_engine_prepare_execution.py tests/ai/engine/test_turn_executor.py tests/test_openai_adapter_responses.py::test_runtime_query_engine_required_empty_without_tool_calls_fails tests/test_openai_adapter_responses.py::test_runtime_query_engine_progress_only_does_not_satisfy_required_tool_contract -q
```

Result: 222 passed.

Static / prompt checks:

```powershell
cd backend
python -m ruff check <targeted changed AI runtime files and tests>
python -m ruff format --check <targeted changed AI runtime files and tests>
python scripts/check_prompt_contracts.py
```

Result: passed.

Browser e2e smoke:

```powershell
cd frontend
$env:E2E_API_BASE_URL='http://localhost:8008'
$env:VITE_GLOB_API_URL='http://127.0.0.1:8008'
$env:TENANT_E2E_PORT='5674'
pnpm -F @vben/web-antd exec playwright test __tests__/e2e/ai-chat.spec.ts -g "C1" --project=chromium --trace on
```

Result: 1 passed in Chromium against the fresh backend on port 8008.

## Testing Discipline Self-Check

- Test types touched: behavioral, structural, smoke.
- LLM response mocking: no new test claims real-dialogue behavior from a
  hand-written LLM answer. Adapter stream tests remain structural fixtures.
- Tool executor mocking: no new test relies on a mocked tool executor returning
  success as the proof. Assertions cover routing decisions, metadata, stream
  evidence, provider readiness reasons, and C1 browser outcome.
- Weak assertions: new assertions check concrete booleans, tool lists, metadata
  flags, error codes, and readiness reasons.
- Real-dialogue smoke: Playwright C1 was rerun through the real browser and
  backend SSE path after the code changes.

