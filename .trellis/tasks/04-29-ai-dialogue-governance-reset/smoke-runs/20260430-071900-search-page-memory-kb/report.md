# 2026-04-30 Search/Page/Memory/KB Smoke Report

## Scope

This is a targeted real E2E smoke run for the user-reported AI dialogue failures:

- Search cannot be used.
- Page awareness misses the main page content or is too slow.
- Page write flow must enter a real consent/write chain.
- Knowledge base retrieval must surface RAG evidence.
- Memory recall must not crash and short-term memory must recall the stored fact.

This artifact is not a full milestone closeout. It does not claim the whole AI dialogue rewrite is complete or release-ready.

## Environment

- Date: 2026-04-30
- Workspace: `E:\git_clone\novusai-saas-yudi`
- Branch: `codex/h5-root-main-hold-20260427`
- Frontend base URL: `http://localhost:5666`
- Backend API URL: `http://localhost:8000`
- Runner: Playwright Chromium, single worker

## Command

```powershell
$env:E2E_API_BASE_URL='http://localhost:8000'
$env:E2E_BASE_URL='http://localhost:5666'
$env:E2E_WORKERS='1'
pnpm --dir frontend/apps/web-antd exec playwright test --config=playwright.config.ts ai-chat.spec.ts --grep "C1|E1|P5|P7|T15|T16" --reporter=list
```

## Result

```text
Running 6 tests using 1 worker

ok 1 [chromium] AI Chat E2E > C: Web search > C1 - web_search is triggered (1.3m)
ok 2 [chromium] AI Chat E2E > E: Knowledge base RAG > E1 - formal knowledge base retrieval is surfaced (27.5s)
ok 3 [chromium] AI Chat E2E > P: Page deep operations > P5 - record creation enters consent or write chain (33.1s)
ok 4 [chromium] AI Chat E2E > P: Page deep operations > P7 - health page main region summary ignores nav shell (22.0s)
ok 5 [chromium] AI Chat E2E > T: Gap coverage > T16 - long-term memory query does not crash (21.4s)
ok 6 [chromium] AI Chat E2E > T: Gap coverage > T15 - short-term session memory recalls project code name (29.9s)

6 passed (3.6m)
```

## Rerun After Search/Page/Memory Hardening

Additional hardening was applied after the first run:

- Ordinary Responses chat requests now preserve the platform `web_search` function tool even if legacy provider config contains hosted-search rewrite fields.
- Local provider `provider_1.config.web_search` was normalized from legacy `public_providers: ["baidu", "so360"]` / hosted-rewrite fields to canonical Baidu-only fallback config.
- RAG diagnostics now only mark `kb_injected=true` when retrieval evidence exists.
- Memory extraction fallback now accepts common explicit phrasing such as `记住：...`, `记一下：...`, and `以后记得...`.
- The health page now exposes explicit `data-ai-main`, `data-ai-region`, `data-ai-section`, and stable `data-ai-action-id` markers for runtime page perception.

DB post-cleanup provider search config:

```text
{'id': 10, 'code': 'provider_1', 'web_search': {'enabled': True, 'max_results_cap': 8, 'native_timeout_seconds': 20, 'fallback_provider': 'baidu', 'fallback_timeout_seconds': 15}}
```

Rerun command:

```powershell
$env:E2E_API_BASE_URL='http://localhost:8000'
$env:E2E_BASE_URL='http://localhost:5666'
$env:E2E_WORKERS='1'
pnpm --dir frontend/apps/web-antd exec playwright test --config=playwright.config.ts ai-chat.spec.ts --grep "C1|E1|P5|P7|T15|T16" --reporter=list
```

Rerun result:

```text
Running 6 tests using 1 worker

ok 1 [chromium] AI Chat E2E > C: Web search > C1 - web_search is triggered (1.1m)
ok 2 [chromium] AI Chat E2E > E: Knowledge base RAG > E1 - formal knowledge base retrieval is surfaced (24.9s)
ok 3 [chromium] AI Chat E2E > P: Page deep operations > P5 - record creation enters consent or write chain (29.9s)
ok 4 [chromium] AI Chat E2E > P: Page deep operations > P7 - health page main region summary ignores nav shell (22.7s)
ok 5 [chromium] AI Chat E2E > T: Gap coverage > T16 - long-term memory query does not crash (20.5s)
ok 6 [chromium] AI Chat E2E > T: Gap coverage > T15 - short-term session memory recalls project code name (28.1s)

6 passed (3.2m)
```

## Scenario Mapping

| Scenario | User concern | Outcome |
|---|---|---|
| `C1` | Builtin web search is usable | PASS |
| `E1` | Knowledge base retrieval is visible in AI dialogue | PASS |
| `P5` | Page create/write path enters the consent/write chain | PASS |
| `P7` | Health page summary focuses on main content, not nav shell | PASS |
| `T16` | Long-term memory query path does not crash | PASS |
| `T15` | Short-term memory recalls the explicit project code name | PASS |

## Additional Targeted Verification

Backend targeted checks:

```text
13 passed in 2.71s
```

Covered files/scenarios:

- `backend/tests/services/test_memory_extraction_service.py`
- `backend/tests/services/test_conversation_service.py::TestConversationAccessHelpers::test_get_conversation_memory_state_checks_access_first`
- `backend/tests/services/test_conversation_service.py::TestConversationAccessHelpers::test_get_conversation_memory_state_attaches_long_term_preview`
- `backend/tests/ai/engine/test_turn_executor.py::test_turn_executor_reads_main_region_first_for_page_summary`
- `backend/tests/ai/engine/test_turn_executor.py::test_turn_executor_completes_page_summary_from_builtin_snapshot_without_provider_call`
- `backend/tests/test_openai_adapter_responses.py::test_build_responses_request_keeps_runtime_web_search_when_provider_search_enabled`

Backend lint:

```text
All checks passed!
```

Frontend targeted checks:

```text
2 test files passed, 45 tests passed
```

Covered files:

- `src/components/business/ai-slide-panel/__tests__/AIChatMemoryPanel.test.ts`
- `src/components/business/ai-runtime/__tests__/runtime-bridge.test.ts`

Additional targeted checks after hardening:

```text
Backend ruff: All checks passed!
Backend targeted tests: 27 passed in 3.24s
Frontend targeted tests: 3 test files passed, 46 tests passed
Stream cancellation/provider-timeout guard tests: 30 passed in 2.93s
```

## Remaining Caveats

- This smoke run proves the targeted scenarios above, not the full structural + behavioral + smoke + known-bug four-gate release standard.
- `T16` currently proves the long-term memory query path does not crash. The UI memory panel preview is additionally covered by a targeted frontend behavioral test, but a full browser smoke that opens the panel and verifies persisted long-term memory should still be added.
- The page write smoke proves the flow enters the consent/write chain. More complex button chains and rich-text real editing still need dedicated same-batch artifacts before release judgment.
