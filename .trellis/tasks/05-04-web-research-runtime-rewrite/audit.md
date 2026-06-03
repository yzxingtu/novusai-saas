# Main Auditor Log

## 2026-05-04 Start

Path: `deep`

User direction is explicit: this is a new-system rewrite, not another compatibility patch. The old native-first audit from 05-02 is superseded because it encoded the now-rejected assumption that provider hosted search should be preferred for generic `web_research`.

## Initial Risk Register

- Existing canonical spec still says generic web research should prefer provider-native hosted search. This must be rewritten before implementation is judged.
- Existing tests assert `native_search_preferred`, `_runtime_hosted_web_search_required`, and hosted-search fallback behavior. Those tests are now evidence of old behavior, not acceptance criteria.
- Existing working tree contains unrelated or previous-session modifications. Subagents must not revert changes outside their ownership scopes.
- Conversation 2282 has no persisted `fetch_url` evidence. CLI/read-model code must not fabricate an answer for that historical turn.
- Earlier on 2026-05-04, one launch attempt was blocked by the local collaboration tool limit. On resume, six subagents were available and completed A1-A6. Main thread audited and integrated their work.

## Audit Standard

- Reject surface patches that only invert a boolean in `model_policy.py`.
- Reject fallback chains where the LLM/provider decides whether fetch happens after search candidates exist.
- Reject adapter-local fallback chains for hosted/native search.
- Reject behavioral tests that mock the LLM/tool executor into the expected answer.
- Require a single evidence schema and one runtime owner for WebResearch completion truth.

## 2026-05-04 A6 Test/Spec Audit

Worker A6 added the detailed test/spec audit at `a6-test-spec-audit.md`.

Key deltas:

- Canonical spec cleanup found no remaining positive native-first guidance after
  narrowly updating `tool-skill-governance.md` and `recovery-stop-loss.md`.
- The initial test tree still contained obsolete assertions for
  `native_search_preferred`, `_runtime_hosted_web_search_required`,
  hosted-search-to-builtin protocol fallback, and
  `synthetic_builtin_web_search_fallback`. A1/A4/A6 rewrote or deleted those
  live-path expectations. Remaining string matches are either Trellis historical
  notes, negative assertions, or historical diagnostic normalization.
- Smoke/replay evidence is still missing. The scaffold lives under
  `smoke-runs/2026-05-04-webresearch-llm-ranking/` and must be completed from a
  real provider run or approved replay before milestone acceptance.

## 2026-05-05 Main Auditor Verification

Six subagents completed their ownership slices:

- A1: OpenAI-compatible hosted/native search gate. Hosted search is default-off
  and requires explicit provider capability plus smoke/replay evidence.
- A2: Provider-neutral `app.ai.web_research` core with contracts, routing,
  deterministic candidate selection, normalization, diagnostics, and builtin
  provider adapters.
- A3: Builtin `web_search` default path now runs platform/public search
  directly; native-first/public-fallback behavior is removed from the builtin
  orchestrator.
- A4: `TurnExecutor` routes platform-marked generic `web_research` intents into
  `WebResearchRuntime`, converts normalized evidence to `web_search` /
  `fetch_url` `ToolResult`s, and finalizes/recoveries from fetched evidence.
- A5: CLI/read-model/turn-flow diagnostics project canonical WebResearch fields
  and do not fabricate historical `fetched_urls`.
- A6: Obsolete native-first tests were rewritten/deleted and the smoke scaffold
  was tightened.

Additional main-thread audit fix:

- `ai smoke --agent-id 59` initially produced a false `web_research_tools_unavailable`
  warning because the inventory snapshot had `web_search` + `fetch_url` only in
  resolver inventory, not live turn-selected tools. `runtime_inventory_service`
  and `runtime_diagnostics_support` now project inventory-pair availability with
  `availability_basis=inventory_selected_tools` while preserving
  `selection_live=false`.

Verified commands:

- `cd backend; pytest tests/ai/engine/test_tool_router.py tests/ai/engine/test_protocol_turn_session.py tests/ai/engine/test_query_engine_partial_contract.py tests/ai/web_research tests/ai/test_web_search_orchestrator.py tests/ai/engine/test_turn_executor.py tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_native_web_search_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_protocol_runtime_context.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/engine/test_cli_conversation_diagnostics.py tests/ai/engine/test_turn_flow_projector.py tests/services/test_conversation_engine_prepare_execution.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_runtime_inventory_service.py -q`
  - Result: `216 passed`.
- `cd backend; python scripts/check_prompt_contracts.py`
  - Result: passed.
- Touched backend Python files only: `python -m ruff check ...`
  - Result: passed.
- Touched backend Python files only: `python -m ruff format --check ...`
  - Result: `51 files already formatted`.
- `cd backend; python -m app.cli ai conversation show 2281 --tail 1 --diagnostics-only --json`
  - Result: success. Historical record has no canonical
    `web_research_pipeline_id`/`fetched_urls`, but the old turn is still
    explainable as `final_output_source=recovery_evidence`.
- `cd backend; python -m app.cli ai conversation show 2282 --tail 4 --diagnostics-only --json`
  - Result: success. Historical record remains failed with
    `termination_reason=elapsed_budget_exceeded`, `final_output_source=budget_fallback`,
    `candidate_urls=[]`, and `fetched_urls=[]`; no missing fetch evidence is
    fabricated.
- `cd backend; python -m app.cli ai smoke --agent-id 59 --json`
  - Result: `overall_status=green`; `web_research_contract=available` from
    inventory-selected `web_search` + `fetch_url` pair, with
    `selection_live=false`.
- `cd backend; pytest tests/services/test_runtime_diagnostics_service.py tests/services/test_runtime_inventory_service.py -q`
  - Result: `24 passed`; covers the CLI diagnostics/smoke helper layer touched
    by the inventory snapshot fix.

Milestone status:

- Structural, behavioral, known-bug regression, CLI historical replay, prompt
  contract, touched-path lint/format, and CLI capability-smoke gates are green.
- Real-dialogue or approved replay smoke for prompt
  `查一下大模型排行榜 2026 水平排行！` is still not run. Per
  `.trellis/spec/ai-runtime/testing-discipline.md`, this task must remain
  active and must not be claimed completed until that artifact is attached.

## 2026-05-05 Final Smoke And Projection Fix

The required real-dialogue smoke was run through the real AgentChatService path:

- `cd backend; python scripts/verify_tool_policy_logging.py --agent-id 59 --user-id 1 --message "查一下大模型排行榜 2026  水平排行！"`
  - Result: created `conversation_id=2284`.
  - Runtime intent metadata selected `web_research_runtime=platform`,
    `search_provider=builtin_web_search`, and `fetch_provider=builtin_fetch_url`.
  - Public builtin search returned `status=success`, `result_count=5`.
  - Chat completed successfully without hosted/native provider search.
- `cd backend; python -m app.cli ai conversation show 2284 --tail 4 --diagnostics-only --json`
  - Result: `web_research_pipeline_id=web-research-1`,
    `search_provider=builtin:web_search`, `fetch_provider=builtin:fetch_url`,
    `evidence_status=completed`, `fetched_urls=["https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"]`,
    `evidence_quality=body`, `answer_source=fetched_body`,
    `final_output_source=recovery_evidence`, and no `fetch_not_attempted`
    failure.

The first real smoke (`conversation_id=2283`) had already proved runtime
execution was correct but exposed one remaining read-model bug: compact CLI
diagnostics preferred stale top-level partial fields over canonical
`turn_flow.evidence[].summary_payload.web_research_evidence`. Main auditor fixed
the projection order so canonical WebResearch evidence is searched first across
nested evidence containers, then explicit WebResearch diagnostics, and only then
historical direct fields. CLI hydration now lets canonical WebResearch projection
overwrite or clear stale WebResearch fields. This preserves old-record honesty
without preserving an old live runtime path.

Additional final verification:

- `cd backend; pytest tests/ai/engine/test_cli_conversation_diagnostics.py tests/services/test_conversation_diagnostics_projector_support.py tests/services/test_runtime_inventory_service.py -q`
  - Result: `27 passed`.
- `cd backend; pytest tests/ai/engine/test_tool_router.py tests/ai/engine/test_protocol_turn_session.py tests/ai/engine/test_query_engine_partial_contract.py tests/ai/web_research tests/ai/test_web_search_orchestrator.py tests/ai/engine/test_turn_executor.py tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_native_web_search_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_protocol_runtime_context.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/engine/test_cli_conversation_diagnostics.py tests/ai/engine/test_turn_flow_projector.py tests/services/test_conversation_engine_prepare_execution.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_runtime_inventory_service.py -q`
  - Result: `217 passed`.
- `cd backend; pytest tests/services/test_runtime_diagnostics_service.py tests/services/test_runtime_inventory_service.py -q`
  - Result: `24 passed`.
- `cd backend; python scripts/check_prompt_contracts.py`
  - Result: passed.
- `cd backend; python -m ruff check app/ai/engine/recovery_web_research_gate.py app/cli_commands/ai_snapshot.py tests/ai/engine/test_cli_conversation_diagnostics.py tests/services/test_conversation_diagnostics_projector_support.py`
  - Result: passed.
- `cd backend; python -m ruff format --check app/ai/engine/recovery_web_research_gate.py app/cli_commands/ai_snapshot.py tests/ai/engine/test_cli_conversation_diagnostics.py tests/services/test_conversation_diagnostics_projector_support.py`
  - Result: `4 files already formatted`.

Final status: structural, behavioral, known-bug, CLI historical replay, prompt
contract, lint/format, capability smoke, and real-dialogue smoke gates are all
green. The task can move from `active` to `completed`.

## 2026-05-05 Playwright And Cross-Layer Audit

User explicitly asked whether Playwright, commit, and cross-audit had been done.
Main auditor resumed from the completed runtime rewrite and added the missing
browser/cross-layer evidence before commit.

Playwright real browser verification:

- Opened `http://localhost:5666/admin/ai/conversations` against the running
  frontend (`5666`) and backend (`8000`) with the existing admin session.
- Opened conversation `2284` from the admin conversations table.
- Verified the drawer rendered the persisted real-dialogue result:
  `web_research_runtime`, `builtin:web_search`, `builtin:fetch_url`,
  `evidence_status=completed`, the `web_search` tool call, the `fetch_url` tool
  call, and fetched URL
  `https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc`.
- Network verification included:
  `GET http://localhost:8000/admin/ai/conversations?page[number]=1&page[size]=15&sort=-created_at -> 200`
  and
  `GET http://localhost:8000/admin/ai/conversations/2284?message_limit=200&message_skip=0 -> 200`.
- Screenshot artifact copied to
  `output/playwright/webresearch-2284-detail.png` for local inspection.

Cross-layer audit:

- `git diff --name-only -- backend/app/api backend/migrations frontend`
  returned no touched files. This rewrite did not add controllers, migrations,
  frontend page code, or frontend page-runtime behavior.
- `rg` checks confirmed no live imports remain for
  `runtime_fallback_flags`, `runtime_info_with_web_search_fallback_flags`,
  `hosted_web_search_fallback_observed`, `NativeModelSearchProvider`, or
  `web_search.orchestration`.
- The old, now-unused
  `backend/app/ai/web_search/orchestration/native_provider.py` was deleted
  after audit showed no live import. Optional provider-hosted native search
  remains only behind explicit AIGateway/adapter capability gates; it is not
  part of the builtin WebResearch path.
- `page_context`, `page_session_id`, `pageop_*`, and `ui_*` matches in the
  searched test/spec tree are negative guard tests or canonical retirement
  guidance, not newly introduced live runtime input paths. No API/controller
  surface was touched.
- Remaining native/fallback strings in live code are historical diagnostic
  normalization in `recovery_web_research_gate.py` or explicit optional-adapter
  tests that assert hosted/native keys are stripped or gated. They are not
  runtime fallback chains.

Main auditor conclusion:

- Platform-owned chain is now:
  `web_research intent -> WebResearchRuntime -> builtin:web_search -> builtin:fetch_url -> canonical WebResearchEvidence -> answer/projection`.
- Generic WebResearch no longer depends on LLM/provider fallback to decide
  whether fetch happens.
- OpenAI-compatible hosted/native search is default-off and remains an optional
  provider capability only when explicit config plus smoke/replay evidence
  proves support.

Final post-audit verification after deleting the unused native-first provider:

- `cd backend; python -m pytest tests/ai/engine/test_tool_router.py tests/ai/engine/test_protocol_turn_session.py tests/ai/engine/test_query_engine_partial_contract.py tests/ai/web_research tests/ai/test_web_search_orchestrator.py tests/ai/engine/test_turn_executor.py tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py tests/ai/engine/test_model_policy.py tests/ai/adapters/test_openai_native_web_search_policy.py tests/ai/adapters/test_openai_request_payload_builders.py tests/ai/adapters/test_openai_protocol_runtime_context.py tests/ai/adapters/test_openai_adapter_native_web_search.py tests/ai/engine/test_cli_conversation_diagnostics.py tests/ai/engine/test_turn_flow_projector.py tests/services/test_conversation_engine_prepare_execution.py tests/services/test_conversation_engine_exception_passthrough.py tests/services/test_runtime_inventory_service.py tests/ai/test_gateway_native_web_search.py tests/ai/adapters/test_gateway_native_web_search_bridge.py -q`
  - Result: `224 passed`.
- Touched Python files only:
  `python -m ruff check <65 changed/untracked Python files>`
  - Result: passed.
- Touched Python files only:
  `python -m ruff format --check <65 changed/untracked Python files>`
  - Result: `65 files already formatted`.
- `cd backend; python scripts/check_prompt_contracts.py`
  - Result: passed.
- `git diff --check`
  - Result: passed with only line-ending warnings.
- `cd backend; python -m app.cli ai smoke --agent-id 59 --json`
  - Result: `overall_status=green`; WebResearch contract available from
    inventory-selected `web_search` + `fetch_url`.
- `cd backend; python -m app.cli ai conversation show 2284 --tail 4 --diagnostics-only --json`
  - Result: still shows completed canonical evidence with builtin search/fetch
    and fetched URL.
- `cd backend; python -m app.cli ai conversation show 2282 --tail 4 --diagnostics-only --json`
  - Result: historical failed record remains honest with empty `fetched_urls`.

## 2026-05-05 Reopened For BUG-2026-05-05-2285

User reported conversation `2285` for prompt
`查一下大模型排行榜 2026  水平排行！`: the assistant returned an irrelevant
article about AI 投毒 / GEO / OpenClaw / token usage and the UI marked it
completed. Main auditor retracted the 2284 final acceptance claim: conversation
2284 proved the platform-owned builtin search/fetch chain executes, but it did
not prove fetched evidence was relevant enough to answer the query.

Known-bug discipline:

- RED commit: `dd45f86fd test(ai): reproduce 2285 irrelevant web research evidence`.
- RED test:
  `backend/tests/regressions/test_bug_2026_05_05_2285_irrelevant_web_research_evidence.py`.
- GREEN commit: pending final commit hash for this implementation closeout.

Implementation audit:

- Added deterministic WebResearch relevance scoring for LLM-leaderboard queries.
- Rejected low-relevance fetched pages before they can become `fetched_urls`,
  citations, answer-quality evidence, `recovery_evidence`, or completed state.
- Turn executor now returns partial/error for unaccepted evidence and marks the
  WebResearch intent failed.
- CLI/read-model/turn-flow projections downgrade stale completed states when
  WebResearch evidence is unaccepted.
- Follow-up cross-audit found two projection backdoors. Main thread fixed both:
  fallback `fetch_url` tool-result projection now reuses the WebResearch
  acceptance helper, and turn-flow no longer treats rejected candidate URLs as
  retrieved/completed evidence.
- Frontend admin/tenant zh-CN/en-US locales now include the WebResearch failure
  kind labels so `low_query_relevance` renders as `来源相关性不足` in the admin
  diagnostics card instead of a missing i18n key.

Verification evidence:

- `cd backend; python -m app.cli ai conversation show 2285 --tail 8 --diagnostics-only --json`
  - Result: `turn_outcome=failed`, `final_output_source=partial_output`,
    `evidence_status=partial`, `fetched_urls=[]`,
    `rejected_urls=["https://www.cnblogs.com/bykj123/p/19608875"]`,
    `answer_source=none`, `web_research_failure_kind=blocked_url`,
    `web_research_relevance_profile=llm_leaderboard`.
- `cd backend; python -m app.cli ai conversation show 2290 --tail 8 --diagnostics-only --json`
  - Result: `turn_outcome=failed`, `termination_reason=low_query_relevance`,
    `partial_exit_reason=low_query_relevance`,
    `final_output_source=partial_output`, `evidence_status=partial`,
    `fetched_urls=[]`,
    `rejected_urls=["https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"]`,
    `answer_source=none`, `web_research_failure_kind=low_query_relevance`,
    `web_research_relevance_rejection_count=1`.
- Focused regression/projection tests:
  `python -m pytest tests\ai\engine\test_cli_conversation_diagnostics.py::test_web_research_tool_result_projection_rejects_low_relevance_fetch tests\ai\engine\test_turn_flow_projector.py::test_build_turn_flow_view_model_does_not_retrieve_rejected_web_research_candidates -q`
  - Result: `2 passed`.
- Focused ruff/format on projection fixes:
  - `python -m ruff check app\ai\engine\recovery_web_research_gate.py app\ai\engine\recovery_tool_result_helpers.py app\ai\engine\turn_flow_projector.py tests\ai\engine\test_cli_conversation_diagnostics.py tests\ai\engine\test_turn_flow_projector.py`
    passed.
  - `python -m ruff format --check ...`
    passed after formatting the touched files.
- Playwright real browser:
  - Opened `http://localhost:5666/admin/ai/conversations`.
  - Opened conversation `2290`.
  - Verified `失败归因=来源相关性不足`, `web_research failed`,
    provider event `evidence_status=partial` / `answer_source=none`, retry
    `return_partial low_query_relevance`, and assistant message card `异常`.
  - Verified browser console after reload only showed Vite debug messages; the
    previous missing translation warning was gone.
  - Screenshot copied to
    `output/playwright/webresearch-2290-low-relevance-detail-translated.png`.

Final acceptance is now based on relevance rejection for 2285/2290, not on the
superseded 2284 fetched-body success.

## 2026-05-05 Final Commit Closeout

GREEN implementation commit:

- `6be3a378b808687a5503bd850e07230f1a3eb926`
  (`fix(ai): reject irrelevant web research evidence`)

Final verification after the GREEN code commit:

- `cd backend; python -m pytest --basetemp ..\.tmp\pytest-temp`
  - Result: `2950 passed, 4 skipped, 2 warnings`.
- `cd backend; python scripts\check_prompt_contracts.py`
  - Result: passed.
- Touched backend Python files:
  - `python -m ruff check ...`
  - Result: passed.
  - `python -m ruff format --check ...`
  - Result: `43 files already formatted`.
- `cd backend; python -m app.cli ai smoke --agent-id 59 --json`
  - Result: `overall_status=green`; WebResearch contract available from
    inventory-selected `web_search` + `fetch_url`.
- `cd backend; python -m app.cli ai conversation show 2285 --tail 8 --diagnostics-only --json`
  - Result: historical conversation `2285` projects as failed/partial with
    `fetched_urls=[]`, rejected URL
    `https://www.cnblogs.com/bykj123/p/19608875`,
    `answer_source=none`, and
    `web_research_relevance_profile=llm_leaderboard`.
- `cd backend; python -m app.cli ai conversation show 2290 --tail 8 --diagnostics-only --json`
  - Result: fresh smoke conversation `2290` projects as failed/partial with
    `termination_reason=low_query_relevance`, `fetched_urls=[]`,
    `answer_source=none`, and rejected Baijiahao URL.
- `pnpm --dir frontend check:type:antd`
  - Result: passed.
- `pnpm --dir frontend exec prettier --check` for touched admin/tenant AI
  locale JSON files
  - Result: passed.
- `pnpm --dir frontend lint`
  - Result: failed on pre-existing unrelated stylelint/prettier issues in AI
    chat CSS/Vue and docs files. The files changed by this 2285 relevance fix
    on the frontend are locale JSON files and passed targeted formatting/type
    checks.

Final cross-audit result:

- No live `page_context`, `page_session_id`, `pageop_*`, or `ui_*` runtime path
  was introduced.
- Live WebResearch remains platform-owned:
  `intent -> WebResearchRuntime -> builtin:web_search -> builtin:fetch_url ->
  relevance gate -> canonical evidence -> answer/projection`.
- OpenAI-compatible hosted/native search remains default-off and only available
  through explicit optional-provider capability gates.
