# Native Web Search Final Smoke Report

Date: 2026-05-02

## Scope

Audit target: AI dialogue web research routing.

Policy verified:

- Generic `web_research` turns prefer provider-native Responses hosted
  `web_search` when the active OpenAI-compatible provider supports Responses
  and the effective upstream model supports native web search.
- Builtin or skill-pack `web_search` / `fetch_url` execute only when the user
  explicitly asks for the builtin/tool/skill path, or when native hosted search
  is unavailable.
- Native Responses evidence (`web_search_call`, stream progress, or URL
  citations) completes `web_research` recovery without forcing a second builtin
  search retry.

## Six-Agent Audit Summary

- A1 adapter/protocol: found Responses support checks were too strict and did
  not accept `protocol_capabilities.allowed_wire_apis`; native evidence parsing
  missed `output[].type == "web_search_call"`.
- A2 orchestration: confirmed the dedicated web-search runtime was mostly
  native-first, but generic dialogue routing still exposed builtin tools too
  early.
- A3 tool routing: found ordinary web intent was routed to builtin
  `web_search` / `fetch_url`; fixed with explicit builtin request detection and
  native-first fallback metadata.
- A4 recovery/contracts: found sync/stream model rounds and contract recovery
  did not consistently treat native search evidence as completing
  `web_research`; fixed for initial, retry, and post-tool contract paths.
- A5 UI/evidence: found the e2e C1 expectation was tied to builtin tool calls;
  updated it to accept hosted search progress, builtin fallback, or graceful
  hosted-search closure.
- A6 test coverage: found missing native-first behavioral coverage; added
  router, model policy, payload, adapter, parser, provider summary, contract,
  protocol, prepare, and turn-executor coverage.

## Commands Run

Structural / contract:

```powershell
cd backend
python scripts/check_prompt_contracts.py
```

Result: passed.

Backend behavioral / structural target set:

```powershell
cd backend
python -m pytest -p no:cacheprovider tests/ai/engine/test_tool_router.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/adapters/test_openai_native_web_search_parser.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_ai_provider_service.py tests/ai/engine/test_protocol_turn_session.py tests/services/test_conversation_engine_prepare_execution.py tests/ai/engine/test_turn_executor.py -q
```

Result: 142 passed.

Lint / format:

```powershell
python -m ruff check <changed backend files and tests>
python -m ruff format --check <changed backend files and tests>
```

Result: passed.

Browser e2e smoke:

```powershell
cd frontend
pnpm -F @vben/web-antd exec playwright test __tests__/e2e/ai-chat.spec.ts -g "C1" --project=chromium
```

Result: passed. The C1 scenario exercised the AI Chat web-search smoke path and
now accepts either provider hosted-search progress, builtin fallback search, or
an explicit graceful hosted-search closure.

## Testing Discipline Self-Check

- Test type(s) touched: structural, behavioral, smoke.
- LLM response mocking: backend behavioral tests use deterministic local
  adapter/payload/contract fixtures to verify routing and state transitions;
  no test asserts an answer merely because a mocked LLM returned that answer.
- Tool executor mocking: no new test relies on a mocked tool executor returning
  success as the only proof. Assertions cover payload shape, policy fields,
  native evidence, completed intents, and visible e2e behavior.
- Known bug chain: this task is an audit/fix request rather than a previously
  registered known-bug id. The new assertions fail if generic web research
  routes directly to builtin tools, if native hosted search is not forced when
  available, or if native evidence fails to complete web research.
- Weak assertions: new assertions verify concrete fields such as
  `tool_choice`, `tools`, protocol path, model name, policy reason, completed
  intents, backend key, and Playwright C1 scenario outcome.
- Real-dialogue smoke: Playwright C1 was executed through the real browser e2e
  harness. Backend target tests remain deterministic scripted coverage for
  adapter/runtime branches.
