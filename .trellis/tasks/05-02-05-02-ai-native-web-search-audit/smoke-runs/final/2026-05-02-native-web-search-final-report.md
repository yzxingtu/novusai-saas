# Historical Only

This smoke report is superseded by the 05-05 and 05-08 online-search
retirement work. Do not use it as current acceptance, current smoke
expectation, or evidence to restore WebResearch, provider-hosted/native search,
`web_search`, or `fetch_url`.

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

## Supplemental Second-Pass Addendum

After the final smoke report, a deeper second pass identified and covered four
additional native-first edges:

- Sync and streaming Responses conversion must mark native hosted search as
  observed when `response.tool_usage.web_search.num_requests > 0`, even if the
  provider response has no `web_search_call` output item or URL citation.
- Generic research prompts where "tool", "skill", or "call" are the research
  subject must remain native-first. Only explicit requests to use or call a
  search tool/skill, or direct `web_search` / `fetch_url` naming, should
  activate the builtin path first.
- Follow-on `web_research` rounds after an earlier tool round must preserve the
  `native_web_search_first:<intent>` retry policy and complete via
  `native_web_search` evidence without forcing redundant builtin search.
- When forced Responses hosted search times out or has a provider connection
  failure before meaningful output, runtime-v2 may fall back to the retained
  builtin `web_search` / `fetch_url` function-tool schema through
  `chat_completions`.
- Responses-only providers cannot legally cross to `chat_completions`; for
  those providers, hosted-search failure before meaningful output now retries
  the same Responses protocol with the hosted override disabled and the
  retained builtin `web_search` / `fetch_url` function tools enabled.
- Forced hosted-search payloads must send only the provider hosted
  `web_search` tool, not unrelated function tools that could satisfy required
  tool choice before native search runs.
- Responses streaming keeps hosted-search progress as terminal native evidence,
  and typed `response.failed` / `response.error` events preserve timeout
  details for fallback classification.
- Responses create-stage calls and required-tool streams are now bounded even
  when the compatible SDK does not expose a normal async timeout surface; a
  required stream that produces no tool call or text before the deadline raises
  a typed timeout instead of letting the browser SSE wait expire.
- Fetch-only follow-up rounds after search evidence no longer re-force hosted
  native search. They use the retained builtin `fetch_url` path directly, which
  avoids wasting the smoke budget on a second native-search attempt after search
  candidates already exist.

## Commands Run

Structural / contract:

```powershell
cd backend
python scripts/check_prompt_contracts.py
```

Result: passed in the second pass.

Backend behavioral / structural target set:

```powershell
cd backend
python -m pytest -p no:cacheprovider tests/ai/test_web_search_request_policy.py tests/ai/engine/test_tool_router.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_protocol_runtime_context.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/adapters/test_openai_native_web_search_parser.py tests/ai/adapters/test_openai_responses_stream_support.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_ai_provider_service.py tests/ai/engine/test_protocol_turn_session.py tests/ai/engine/test_query_engine_partial_contract.py tests/services/test_conversation_engine_prepare_execution.py tests/ai/engine/test_turn_executor.py tests/test_openai_adapter_responses.py::test_runtime_query_engine_required_empty_without_tool_calls_fails tests/test_openai_adapter_responses.py::test_runtime_query_engine_progress_only_does_not_satisfy_required_tool_contract -q
```

Result: 189 passed after the second-pass fixes before C1 final rerun; the
adapter/model-policy subsets were rerun after the final timeout and fetch-only
changes.

Lint / format:

```powershell
python -m ruff check <changed backend files and tests>
python -m ruff format --check <changed backend files and tests>
```

Result: passed.

Browser e2e smoke:

```powershell
cd frontend
pnpm -F @vben/web-antd exec playwright test __tests__/e2e/ai-chat.spec.ts -g "C1" --project=chromium --trace on
```

Result: passed against the current working-tree backend on port 8006. The C1
scenario exercised provider-native search first, native/provider timeout and
connection fallback, builtin/public search fallback, fetch_url follow-up, and
final assistant SSE completion without hitting the browser-side SSE timeout.

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
