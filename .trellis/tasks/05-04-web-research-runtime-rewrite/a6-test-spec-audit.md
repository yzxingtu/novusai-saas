# A6 Test And Spec Audit

Date: 2026-05-04
Owner: Worker A6

## Scope

- Audited canonical AI-runtime spec files for remaining native-first language.
- Audited `backend/tests/ai/**` and `backend/tests/regressions/**` for tests
  that still assert native-first hosted search, hosted-search-to-builtin
  fallback, or OpenAI-compatible hosted search default behavior.
- Created smoke/replay scaffold for prompt:
  `查一下大模型排行榜 2026 水平排行！`

## Spec Cleanup Result

- `tool-skill-governance.md` no longer describes builtin runtime search as
  "native search"; it now says platform-owned `web_search`.
- `recovery-stop-loss.md` now states that builtin search is the default
  provider path and must not be a query-engine fallback synthesized from hosted
  search progress-only output.
- Remaining canonical spec mentions of `native-first` / hosted-search-first are
  historical or explicitly prohibited examples, not positive guidance.

## Acceptance Gaps

- Smoke evidence is not yet present. The milestone cannot be called complete
  until a real-dialogue or approved replay artifact is attached under
  `smoke-runs/2026-05-04-webresearch-llm-ranking/`.
- The task has a command matrix in `check.jsonl`, but the test tree still
  contains old native-first assertions. Those tests should be rewritten or
  removed by the owning worker before running the full behavioral gate.
- Historical projection tests may retain old diagnostic strings only when the
  assertion proves historical records remain honest and does not validate the
  new live path.

## Obsolete Native-First Tests Found

| File | Current obsolete assertion | Required action |
|---|---|---|
| `backend/tests/ai/engine/test_tool_router.py` | `test_tool_router_*prefers_native_search` asserts empty candidate tools, `native_search_preferred=True`, and `fallback_tool_names`. | Rewrite these as behavioral default-provider routing tests: generic `web_research` should select builtin `web_search` + `fetch_url` as required/preferred tools, with no `native_search_preferred` metadata. |
| `backend/tests/ai/engine/test_model_policy.py` | `test_build_model_request_overrides_forces_responses_hosted_search_when_available` asserts `_runtime_hosted_web_search_required=True` and forced Responses protocol for generic web research. | Delete or rewrite to assert no hosted-search override for ordinary `openai_compatible`; add/keep a separate opt-in provider-capability test only if explicit hosted provider config and smoke evidence are represented. |
| `backend/tests/ai/engine/test_model_policy.py` | Tests still build `ToolUsePolicy(reason="native_web_search_first:web_research")`. | Replace the reason with the platform WebResearch reason or remove reason coupling from model-policy tests. |
| `backend/tests/ai/adapters/test_openai_request_payload_builders.py` | `test_build_responses_request_injects_required_hosted_search_override` and `test_build_responses_request_strips_all_function_tools_for_hosted_search_override` validate hosted search overriding function tools. | Delete if the override flag is removed; otherwise move to optional hosted-provider adapter tests and require explicit opt-in config. Ordinary request builders must keep builtin function tools by default. |
| `backend/tests/ai/adapters/test_openai_request_payload_builders.py` | Strip-runtime-fallback-key tests still mention `_runtime_native_web_search_fallback_*`. | Keep only as structural guard if production still strips legacy kwargs; rename to legacy-key stripping and avoid treating fallback as live acceptance. |
| `backend/tests/ai/adapters/test_openai_protocol_runtime_context.py` | `test_prepare_protocol_execution_context_bounds_non_stream_hosted_search_timeout` carries `_runtime_hosted_web_search_required=True`. | Retain only if the optional hosted-provider adapter still owns this explicit flag; otherwise rewrite around provider-search timeout config or delete. |
| `backend/tests/ai/engine/test_protocol_turn_session.py` | `test_protocol_turn_session_create_adds_hosted_search_builtin_fallback_chain` asserts hosted search creates a fallback chain into builtin tools. | Delete or rewrite as "runtime does not create hosted-search fallback chain"; optional hosted provider skip/failure should be diagnostics, not a protocol-chain mutation. |
| `backend/tests/ai/engine/test_protocol_turn_session.py` | `finalize_*_success_marks_protocol_fallback_recovered` uses `hosted_web_search_unavailable:*` as a generic protocol fallback reason. | Change fixtures to non-web protocol fallback reasons unless the test is explicitly historical diagnostics. |
| `backend/tests/ai/engine/test_query_engine_partial_contract.py` | `test_runtime_query_engine_*falls_back_from_hosted_search_*to_builtin_tools` asserts hosted-search-first fallback. | Delete or replace with WebResearchRuntime behavioral tests proving builtin default search/fetch progression and optional hosted provider skip diagnostics. |
| `backend/tests/ai/engine/test_query_engine_partial_contract.py` | `test_runtime_query_engine_*synthesizes_builtin_web_search_*` asserts `synthetic_builtin_web_search_fallback` and `native_web_search_builtin_fallback_*` metadata. | Delete for new live paths. If historical replay coverage is still needed, move to a regression file whose scope says historical-only and asserts that new diagnostics do not invent fetch evidence. |
| `backend/tests/ai/engine/test_turn_executor.py` | `test_turn_executor_preserves_native_search_first_for_follow_on_web_intent` asserts native-search completion and `completed_by_tool_names=["native_web_search"]`. | Rewrite as follow-on WebResearchRuntime/builtin-tool progression: weather turn completes, then web intent runs builtin search/fetch and completes from normalized evidence. |
| `backend/tests/ai/engine/test_turn_executor.py` | Several web-research tests still use `ToolUsePolicy(reason="native_web_search_first:web_research")`. | Replace with platform WebResearch reason and ensure assertions prove deterministic `search -> fetch -> evidence` progression, not native-first policy preservation. |
| `backend/tests/ai/test_web_search_orchestrator.py` | Native-first/public-fallback orchestration tests and `native_first_fallback_public` legacy strategy assertions. | A2-owned rewrite should split optional native provider readiness from default builtin provider behavior; legacy strategy config should be ignored or rejected, not treated as a fallback strategy. |
| `backend/tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py` | Regression fixture still seeds `native_search_preferred=True` and `ToolUsePolicy(reason="native_web_search_first:web_research")`. | A4-owned regression should be updated to platform WebResearch metadata/reason while preserving the core assertion: fetch is synthesized/deterministically run after search success before budget partial exit. |

## Historical Strings Allowed With Care

- `backend/tests/regressions/test_bug_2026_05_04_2276_required_fetch_url_recovery.py`
  contains `hosted_web_search_unavailable:provider_timeout` in historical
  diagnostics. This can remain if the test continues to prove old raw-search
  recovery is projected as failed and does not assert new live behavior.
- Old persisted conversations 2281/2282 may mention missing hosted/native
  evidence, but diagnostics must not fabricate a successful fetch for those
  historical records.

## Test Annotation Audit

- Files found with old native-first assertions already include `Test type:`
  annotations.
- Any newly written replacement tests must state `structural`, `behavioral`, or
  `smoke/replay` in the file docstring or directly above the test.
- Behavioral replacements must not mock LLM, tool executor, or intent planner
  into the desired answer. Use real executor boundaries or approved recorded
  fixtures, and assert concrete observable fields such as provider names,
  fetched URLs, evidence status, completed intent tool names, and final answer
  source.

## Verification Matrix To Run After Production Workers Land

| Gate | Command | Expected proof |
|---|---|---|
| structural | `cd backend; ruff check app/ai app/services/ai tests/ai tests/regressions` | No lint regressions in AI runtime/test paths. |
| structural | `cd backend; ruff format --check app/ai app/services/ai tests/ai tests/regressions` | Formatting stays stable. |
| structural | `cd backend; python scripts/check_prompt_contracts.py` | No fixed prompt text was introduced outside prompt resources. |
| behavioral | `cd backend; pytest tests/ai/engine/test_tool_router.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_request_payload_builders.py -q` | Builtin WebResearch default and OpenAI-compatible hosted-search-off behavior. |
| behavioral | `cd backend; pytest tests/ai/engine/test_turn_executor.py tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py -q` | Search success deterministically triggers fetch before final answer/recovery. |
| behavioral | `cd backend; pytest tests/ai/engine/test_query_engine_partial_contract.py tests/ai/test_web_search_orchestrator.py -q` | No hosted-search-first fallback remains as acceptance; optional provider paths normalize or skip. |
| known_bug | `cd backend; pytest tests/regressions/test_bug_2026_05_04_2276_required_fetch_url_recovery.py tests/regressions/test_bug_2026_05_04_2280_fetch_recovery_preview.py tests/regressions/test_bug_2026_05_04_2281_generic_fetched_url_recovery.py tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py -q` | Known web-research incidents remain covered without raw search-only recovery. |
| smoke/replay | Complete `smoke-runs/2026-05-04-webresearch-llm-ranking/report-template.md` from a real provider or approved replay. | Prompt produces canonical WebResearch evidence with fetched body/citation before synthesis or recovery. |

## 2026-05-05 A6 Follow-Up

- Rewrote `test_tool_router` native-first expectations so generic
  `web_research` selects builtin `web_search` + `fetch_url` candidate tools and
  does not stamp `native_search_preferred` / `fallback_tool_names` live metadata.
- Removed obsolete QueryEngine hosted-search-to-builtin fallback and synthetic
  builtin fallback tests. New default provider progression is covered by
  `backend/tests/ai/web_research/`.
- Rewrote `ProtocolTurnSession` coverage so forced protocol tests do not prove a
  hosted-search fallback chain; fallback-success fixtures now use generic
  protocol reasons rather than hosted-web-search reasons.
- Updated TurnExecutor, service, diagnostics, and 2282 regression fixtures away
  from `native_web_search_first:web_research` toward the platform-owned
  `web_research:builtin_pipeline` / canonical diagnostics language.
- Tightened the smoke/replay scaffold with explicit not-run status, replay
  approval requirements, fixture hash expectations, and fail-fast checks for
  empty `fetched_urls` or snippet-only answer sources.
- Smoke evidence remains absent. This scaffold still does not satisfy the
  milestone smoke gate until a real provider or approved replay run is attached.

## 2026-05-05 Main Auditor Closeout

- The obsolete-test table above is retained as the initial audit inventory, not
  as current state. The listed native-first live-path assertions have been
  rewritten or deleted.
- Residual matches for strings such as `native_search_preferred`,
  `native_web_search_first:web_research`, and
  `synthetic_builtin_web_search_fallback` are limited to Trellis historical
  notes, negative assertions, or operator-safe historical diagnostic
  normalization.
- The current verified command matrix is recorded in `audit.md`; result:
  `216 passed`, prompt contract passed, touched-path ruff check/format passed.
- `ai conversation show 2282 --tail 4 --diagnostics-only --json` now preserves
  empty `candidate_urls` / `fetched_urls` for the historical failed record rather
  than inventing a fetch.
- `ai smoke --agent-id 59 --json` now reports WebResearch available from the
  inventory-selected `web_search` + `fetch_url` pair while keeping
  `selection_live=false`.
- Real-dialogue or approved replay smoke for the LLM-ranking prompt remains the
  only unclosed milestone gate.
