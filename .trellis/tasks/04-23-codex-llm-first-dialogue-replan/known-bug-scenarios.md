# Known Bug Scenarios (Living Document)

> 本文件是 AI 对话"实际不对"的症状活档。每一条代表**用户或 QA 观察到、需要被 RED 测试复现、被 fix
> 后转绿**的具体场景。
>
> 规范：`.trellis/spec/ai-runtime/testing-discipline.md §6`

## Status 生命周期

```
reported → reproduced_locally → red_test_written → fix_in_progress → fixed_with_green_test
                                                                    └── regressed（若再失败）
```

只要一条处于 `fixed_with_green_test`，它对应的 RED→GREEN 测试必须永久驻留在
`backend/tests/regressions/` 或 `frontend/.../__tests__/regressions/`，删除或放宽其断言视为回归。

## PR 引用格式

任何声称"修复 bug"的 PR，必须在 PR body 引用至少一条本文件的 bug_id，并提交对应的 RED→GREEN 测试
commits。PR 审核（parent agent 或人类 reviewer）必须核对这条引用确实存在且测试真的红过。

---

## 当前条目

> **首次填充由用户或 QA 直接追加**。Codex 子代理不得先行伪造 bug 条目以绑定自己的工作量。
> 首条填充模板如下。

### BUG-2026-04-23-000 (template, not active)

- **reporter**: (待填)
- **report_date**: 2026-04-23
- **reproduction_prompt**: (待填 — 具体用户输入文字)
- **preconditions**: (待填 — 哪个页面、agent、是否绑定 KB、是否有安装 skill、是否有 thread memory)
- **current_wrong_behavior**: (待填 — AI 实际输出了什么错误内容、缺了什么 tool call、卡在哪个阶段)
- **expected_behavior**: (待填 — 应该做什么)
- **status**: `template_only`
- **notes**: 本条仅作模板。填充实际 bug 时请新增 BUG-2026-04-23-001 起号。

---

### BUG-2026-05-06-2345-time-shortcircuit-provider-call 时间查询已命中 get_current_time，却仍然依赖上游模型

- **reporter**: user
- **report_date**: 2026-05-06
- **reproduction_prompt**: `现在是几点钟 ？`
- **preconditions**:
  - `conversation_id=2345`
  - agent: `猫娘智能体` (`agent_id=59`)
  - only live runtime tool inventory: `get_current_time`
  - intent plan: `time_query`, `family=time_ops`, `shortcircuit=true`
- **current_wrong_behavior**:
  - CLI diagnostics for conversation 2345 show `completed_by_tool_names=["get_current_time"]`
  - the same turn still recorded `protocol_path="responses"`
  - budget usage still included `prompt_tokens_used=1062` and `completion_tokens_used=124`
  - final metadata showed `final_output_source="assistant"` and `post_tool_completion_state="llm_follow_up"`
  - user-visible console also contained upstream provider connection/retry logs around the same dialogue sequence
- **expected_behavior**:
  - deterministic `time_query` should execute the platform built-in `get_current_time` directly
  - no initial provider call is needed before the local tool runs
  - no post-tool model follow-up is needed to format the final time answer
  - final output should be deterministic trusted tool evidence, not upstream assistant text
- **status**: `fixed_with_green_test`
- **fixed_by_regression**:
  - `backend/tests/regressions/test_bug_2026_05_06_2345_time_shortcircuit_provider_call.py`
- **notes**:
  - This fix is intentionally scoped to `time_query + get_current_time`.
  - Generic business tools still keep the normal post-tool LLM follow-up path when they need natural-language synthesis.
  - Retired online-search paths (`web_search`, `fetch_url`, hosted/native search) are not involved and must not be restored.

---

### BUG-2026-04-24-001 上游 502 后用户卡死 3+ 分钟，最终被 HTTP 取消，无 partial / failover / interruption

- **reporter**: user
- **report_date**: 2026-04-24
- **reproduction_prompt**: 正常对话一轮（模型=gpt-5.4，上游 `api.asxs.top`）
- **preconditions**:
  - provider_type: openai_compatible
  - wire_api: responses
  - upstream: `api.asxs.top/v1/responses`
  - model: gpt-5.4
  - 上游 Cloudflare 返回 `502 origin_bad_gateway`，`retry_after: 60`
- **current_wrong_behavior**（trace_id=7a74a4fc-331a-48dc-a1e3-0bab33a63b7e）：
  - `01:13:07` 起第一次 Responses stream 请求
  - `openai._base_client` 自动重试 2 次，每次等 60 秒（由 SDK 默认 `max_retries=2` 驱动）
  - `01:15:22` 协议 stream error 502 抛出
  - **同一时刻**又起一次 `stream=False` 的 Responses chat 请求（sync rescue），再被 SDK retry 60 秒
  - `01:16:26` uvicorn `RequestResponseCycle.run_asgi` 触发 `CancelledError`，整个 turn 终止
  - **全程无 model failover、无 partial_exit、无 interruption 文案、无 SSE 降级事件**；用户前端只看到"卡死"然后连接断开
- **expected_behavior**:
  - 首次 502 抛出后 **秒级** 进入 runtime 决策（而不是被 SDK 吞 60+ 秒）
  - 按 `.trellis/spec/ai-runtime/provider-contracts.md` 触发 runtime model failover 切到健康兼容模型
  - 若 failover 也失败，按 `.trellis/spec/ai-runtime/recovery-stop-loss.md §Scenario Terminal Provider Failure` 输出**自然语言 interruption 文案**（"新闻来源被系统中断了，请稍后再试" 风格），**禁止** 3 分钟静默
  - 用户端收到 SSE 终态事件并看到中断文案，而不是连接被 reset
- **status**: `reported`
- **root_cause_hypotheses（2026-04-24 报告时）**（需 Codex / A1 owner 确认）：
  1. `backend/app/ai/adapters/openai_compatible/client_factory.py:11-15` 构造 `AsyncOpenAI(**kwargs)` 时**未传 `max_retries`**，导致 SDK 走默认值 2；上游 502 + `retry_after=60` 使每次等 60 秒
  2. `backend/app/ai/runtime/query_engine.py:103-125` `_apply_page_ui_latency_guards` 只对 `ui_*` 工具族注入 `max_retries=0`；**非 UI 对话从未设置此 override**
  3. `backend/app/ai/runtime/query_engine.py:27` `_SYNC_RESCUE_MAX_ATTEMPTS=3` 与 SDK 默认 retries=2 叠乘，最坏情况 6 × 60s = 360 秒阻塞
  4. `backend/app/ai/engine/conversation_runtime_bridge.py:248-310` 的 runtime failover 可能被 SDK 层 retry 阻断而从未触发；或 Cloudflare 502 未被分类为 `is_retryable(AIGatewayError)` 以致 `should_record_runtime_failure` 返回 False
  5. uvicorn `CancelledError` 冒泡但未被 `stream_execution_runtime.py` 翻译成 `partial_exit` + interruption text 写入 SSE
- **impact level**: P0（用户级体验完全失败，且是 Codex "做完了" 声明的反面证据）
- **notes**:
  - 这是用户原话 "codex 就说运行成功 但我实际测试 AI 对话就一直不对" 的**具体实例**
  - 必须走 `testing-discipline.md §6.2` 的 RED → GREEN 流程：先写一个 behavioral regression 测试复现 60 秒阻塞链条，再做修复
  - 关联 smoke scenario: `SCENARIO-006 Terminal provider 502 must surface interruption within 10 seconds`
  - 2026-04-25 证据刷新（working tree + 本次实际跑过的 behavioral）：
    `backend/app/ai/adapters/openai_compatible/client_factory.py:10-20` 现已默认
    `max_retries=0`；`backend/app/ai/runtime/query_engine.py:27-32,104-124` 现已把
    `_SYNC_RESCUE_MAX_ATTEMPTS` 收敛到 `1`，并为所有 turn 默认注入
    `_runtime_client_max_retries_override=0`；该 override 在
    `backend/app/ai/adapters/openai_compatible/protocol_runtime_context.py:81-84`
    被透传。
  - 2026-04-25 已跑 behavioral：
    `pytest backend/tests/ai/adapters/test_openai_client_no_sdk_retry.py -q` → `2 passed`；
    `pytest backend/tests/ai/engine/test_query_engine_partial_contract.py::test_runtime_query_engine_applies_max_retry_override_to_non_ui_turns -q`
    → `1 passed`；
    `pytest backend/tests/ai/engine/test_structured_orchestration_runtime.py::test_stream_llm_chunks_retries_with_runtime_failover_before_first_chunk -q`
    → `1 passed`；
    `pytest backend/tests/services/test_stream_handler_real_stream.py::test_interrupted_calls_on_complete_with_partial_result -q`
    → `1 passed`。
  - 上述结果只能证明 code-level seam 与部分 behavioral contract 已变绿，**不能**替代
    bug-specific RED→GREEN regression chain，也**不能**替代 `SCENARIO-006` 的 real-dialogue
    smoke artifact。
  - 2026-04-29 已新增 bug-specific 常驻回归：
    `pytest backend/tests/regressions/test_bug_2026_04_24_001_provider_502_interruption.py -q`
    覆盖三条关键链路：SDK `max_retries=0`、502 首包失败不递归 sync rescue、以及
    `provider_http_5xx -> provider_error` 的可读 done/interruption 终态。
  - 2026-04-25 任务目录下**已存在**
    `.trellis/tasks/04-23-codex-llm-first-dialogue-replan/smoke-runs/mainline-closure/2026-04-25T08-00-00+08-00-report.md`
    归档，但它只覆盖 cross-surface shell 与 `B3|O2|S1|T6|T7|T15` focused subset，
    **不是** `SCENARIO-006` 的 dedicated closeout artifact。
  - 因此本条 status 在本次刷新后仍保持 `reported`：当前仓内虽然已有 bug-specific 常驻回归测试，
    但仍缺历史 RED commit 证据链，也仍未见 `SCENARIO-006` 的 dedicated smoke 运行记录。

---

### BUG-2026-05-04-2276 Required `fetch_url` web research finalized raw search results

- **reporter**: user
- **report_date**: 2026-05-04
- **reproduction_prompt**:
  ```
  帮我搜索一下2025年大模型使用token排行 可以吗？
  ```
- **preconditions**:
  - conversation_id: `2276`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - provider: OpenAI-compatible Responses upstream, native hosted web search fallback
- **current_wrong_behavior**:
  - First turn persisted `final_output_source=recovery_evidence` and `turn_outcome=success`.
  - The only completed evidence was `web_search`; no `fetch_url` skill/tool message existed for turn 1.
  - User-visible assistant content was a raw search result title list with Baidu redirect URLs.
  - `ai root-cause --conversation-id 2276 --turn 1 --json` reported `status=success` even though the required fetch step never completed.
- **expected_behavior**:
  - Required web research must not complete from search-only evidence when `fetch_url` remains required.
  - If the retry model omits the required `fetch_url` tool call, runtime should synthesize a narrow `fetch_url` call from the candidate URL and continue through the normal tool executor.
  - Historical diagnostics/root-cause should classify search-only recovery as `raw_search_only_recovery_finalized` instead of authoritative success.
- **status**: `fixed_with_green_test`
- **notes**:
  - Added regression coverage:
    `backend/tests/regressions/test_bug_2026_05_04_2276_required_fetch_url_recovery.py`.
  - Related behavioral/structural coverage:
    `backend/tests/ai/engine/test_partial_exit_user_output.py`,
    `backend/tests/ai/engine/test_turn_executor.py`,
    `backend/tests/ai/engine/test_stream_generation_pipeline.py`,
    `backend/tests/services/test_turn_failure_normalizer.py`,
    `backend/tests/services/test_runtime_diagnostics_service.py`.
  - Real provider/e2e smoke is deliberately not run for this closeout because the user requested read-only Playwright validation and explicitly said not to run e2e.

---

### BUG-2026-05-04-2280 Recovered `fetch_url` answer finalized only a preface line

- **reporter**: user
- **report_date**: 2026-05-04
- **reproduction_prompt**:
  ```
  查一下大模型排行榜 2026  水平排行！
  ```
- **preconditions**:
  - conversation_id: `2280`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - final_output_source: `recovery_evidence`
- **current_wrong_behavior**:
  - `web_search` and `fetch_url` both succeeded, and diagnostics/root-cause correctly reported `success/completed`.
  - The persisted final assistant content was only:
    `01 榜单来源与权重 目前（2026年1月20日），大模型排行榜主要参考 四条权威数据线 ：`
  - The successful `fetch_url` body contained the requested Top 10 ranking, but recovery output rendering kept only the first preface section.
- **expected_behavior**:
  - Completed `fetch_url` recovery may be trusted only when the fetched evidence can produce answer-quality user-visible text.
  - For ranked/list bodies, recovery output must preserve the useful ranked body lines rather than clipping to title/description metadata or the first preface line.
  - Historical read models may repair this display from existing successful `fetch_url` evidence without mutating persisted conversation rows.
- **status**: `fixed_with_green_test`
- **notes**:
  - Local RED reproduced before the fix with:
    `backend/tests/regressions/test_bug_2026_05_04_2280_fetch_recovery_preview.py`,
    failing because the inline body preview did not include rank 10.
  - Added regression coverage:
    `backend/tests/regressions/test_bug_2026_05_04_2280_fetch_recovery_preview.py`.
  - Related behavioral coverage:
    `backend/tests/ai/engine/test_partial_exit_user_output.py`,
    `backend/tests/ai/engine/test_turn_executor.py`.
  - Real provider/e2e smoke is deliberately not run for this closeout because the user requested read-only Playwright validation and explicitly said not to run e2e.

---

### BUG-2026-05-04-2281 Recovered `fetch_url` answer finalized generic fetched URL

- **reporter**: user
- **report_date**: 2026-05-04
- **reproduction_prompt**:
  ```
  查一下大模型排行榜 2026  水平排行！
  ```
- **preconditions**:
  - conversation_id: `2281`
  - trace_id: `c892f655-5464-401e-a932-115be3dce426`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - final_output_source: `recovery_evidence`
- **current_wrong_behavior**:
  - Hosted/native web search was unavailable, then builtin `web_search` and
    `fetch_url` both produced successful evidence.
  - The final synthesis/provider stream timed out after tool evidence existed.
  - Recovery finalized the assistant answer as only
    `Fetched https://mp.weixin.qq.com/...`, even though the successful
    `fetch_url` body contained answer facts such as
    `Qwen3.5-Max-Preview首度亮相`, `1464分`, and
    `阿里位列全球前五、中国第一`.
- **expected_behavior**:
  - Generic `Fetched https://...` fetch status is not answer-quality evidence
    for a completed `web_research` recovery.
  - When successful `fetch_url` body text contains substantive answer facts,
    recovery and historical read-model repair must prefer body lines over the
    generic status summary.
- **status**: `fixed_with_green_test`
- **notes**:
  - Local RED reproduced before the fix with:
    `backend/tests/ai/engine/test_partial_exit_user_output.py::test_update_intent_statuses_uses_body_when_fetch_summary_is_generic_fetched_url`,
    failing because `cached_result` was `Fetched https://mp.weixin.qq.com/s/example`.
  - Added regression coverage:
    `backend/tests/regressions/test_bug_2026_05_04_2281_generic_fetched_url_recovery.py`.
  - Related behavioral coverage:
    `backend/tests/ai/engine/test_partial_exit_user_output.py`,
    `backend/tests/regressions/test_bug_2026_05_04_2280_fetch_recovery_preview.py`.
  - Real provider/e2e smoke was not run for this focused recovery rendering fix;
    the existing conversation 2281 read-model check was rerun through CLI.

---

### BUG-2026-05-04-2282 Required fetch_url was abandoned after successful search on elapsed budget exit

- **reporter**: user
- **report_date**: 2026-05-04
- **reproduction_prompt**:
  ```text
  查一下大模型排行榜 2026  水平排行！
  ```
- **preconditions**:
  - conversation_id: `2282`
  - trace_id: `d13613c9-ec7e-4904-855a-3b72230f8993`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - final_output_source: `budget_fallback`
- **current_wrong_behavior**:
  - Hosted/native web search was unavailable or timed out, then builtin
    `web_search` succeeded and returned candidate URLs.
  - The turn elapsed budget had already crossed the normal limit, so recovery
    returned a partial/budget fallback while the required `fetch_url` completion
    signal remained unattempted.
  - The user saw only “这些来源还需要继续核验...” even though runtime had enough
    deterministic candidate URL evidence to call `fetch_url`.
- **expected_behavior**:
  - Successful `web_search` evidence with retained candidate URLs must narrow
    the `web_research` intent to required `fetch_url`.
  - Runtime should synthesize and execute the deterministic `fetch_url` call
    before partial-exit finalization when the projected tool-round count remains
    within budget.
  - If elapsed budget is exceeded after this synthetic fetch succeeds, recovery
    should use fetched body evidence and skip another provider synthesis call.
- **status**: `fixed_with_green_test`
- **notes**:
  - Added regression coverage:
    `backend/tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py`.
  - Related contracts updated in
    `.trellis/spec/ai-runtime/recovery-stop-loss.md`.
  - Existing historical conversation 2282 has no persisted `fetch_url` evidence,
    so the read model must not invent a completed answer for that already-failed
    turn; the fix applies to new/replayed turns.
  - Real provider/e2e smoke was not run for this focused turn-loop recovery fix.

---

### BUG-2026-05-05-2285 Irrelevant WebResearch evidence was marked completed

- **reporter**: user
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下大模型排行榜 2026  水平排行！
  ```
- **preconditions**:
  - conversation_id: `2285`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin search/fetch providers
- **current_wrong_behavior**:
  - Runtime fetched a Baijiahao/DBC 德本咨询 article whose body discussed AI
    “投毒”、GEO、OpenClaw、token 调用量和安全风险.
  - The body did not answer the requested “2026 大模型水平排行榜”.
  - Diagnostics still promoted the turn as completed/success:
    `evidence_status=completed`, `answer_source=fetched_body`,
    `final_output_source=recovery_evidence`, and UI showed “已完成”.
- **expected_behavior**:
  - Search/fetch completion is not enough to complete a web research answer.
  - Fetched pages must pass deterministic query-relevance before they can become
    `fetched_urls`, citations, `recovery_evidence`, or a completed answer.
  - Low-relevance pages must be recorded as rejected/skipped evidence with
    `failure_kind=low_query_relevance`; if no accepted evidence remains, the turn
    must finish as partial/failed rather than success/completed.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression added at:
    `backend/tests/regressions/test_bug_2026_05_05_2285_irrelevant_web_research_evidence.py`.
  - RED commit:
    `dd45f86fd test(ai): reproduce 2285 irrelevant web research evidence`.
  - GREEN implementation commit:
    `6be3a378b808687a5503bd850e07230f1a3eb926` (`fix(ai): reject irrelevant web research evidence`).
  - The fix adds deterministic WebResearch query-relevance gating, rejects
    low-relevance fetched pages before they can become `fetched_urls`,
    citations, `recovery_evidence`, or completed state, and downgrades stale
    historical projections for conversation 2285 to failed/partial.
  - Fresh real-dialogue smoke conversation `2290` rejected the same
    low-relevance Baijiahao page with `failure_kind=low_query_relevance`,
    `fetched_urls=[]`, `answer_source=none`, and
    `final_output_source=partial_output`.
  - Playwright verification opened admin conversation `2290`; the detail drawer
    rendered `失败归因=来源相关性不足`, intent `web_research=failed`, provider
    event `evidence_status=partial`, and the assistant message card `异常`.

---

### BUG-2026-05-05-2293 LLM leaderboard query stopped after rejecting noisy public-search candidates

- **reporter**: user
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下大模型排行榜 2026 水平排行！
  ```
- **preconditions**:
  - conversation_id: `2293`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin search/fetch providers
- **current_wrong_behavior**:
  - The relevance gate correctly rejected the previous low-quality / low-relevance
    source, but the runtime only searched the raw Chinese query through the
    public Baidu backend.
  - Search candidates were noisy or low-trust: advertising/product pages,
    Zhihu/video/Taobao content, and the same OpenClaw/GEO-style article family.
  - After three failed or rejected fetch attempts, the turn ended as
    `low_query_relevance` and showed “The assistant could not finish this turn /
    没有拿到与问题足够相关、可核实的内容”.
- **expected_behavior**:
  - A domain-recognized `llm_leaderboard` query must not stop at noisy generic
    public-search candidates.
  - Runtime should expand the search plan and/or add platform-owned trusted
    leaderboard source candidates such as Artificial Analysis before declaring
    failure.
  - Trusted candidates still must go through `fetch_url` and the same relevance
    gate; they must not become an answer if fetch or relevance fails.
  - A successful trusted fetched source should complete WebResearch with
    `fetched_urls` populated, `answer_source=fetched_body`, and no
    `low_query_relevance` terminal failure.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression added at:
    `backend/tests/regressions/test_bug_2026_05_05_2293_llm_leaderboard_authority_fallback.py`.
  - RED commit:
    `e44930175 test(ai): reproduce 2293 leaderboard authority fallback failure`.
  - GREEN commits add platform-owned authority/query expansion for the
    `llm_leaderboard` profile and prove conversation-style WebResearch can reach
    accepted evidence instead of a clean but useless failure:
    `d805a0f86`, `69659e730`, `e236d6b64`.
  - This entry closes the source-selection/authority fallback class only. The
    later `BUG-2026-05-05-2311` entry separately covers completed leaderboard
    evidence being rendered as raw English source snippets.

---

### BUG-2026-05-05-2295 Fashion ranking query stopped on Baidu Images blocked_url

- **reporter**: user
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下 2026年最热门的 女性裙子款式排行！
  ```
- **preconditions**:
  - conversation_id: `2295`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - Public Baidu search returned a Baidu Images vertical-search page whose title
    echoed the user query.
  - The result passed low-confidence filtering, became the only fetch candidate,
    and `fetch_url` returned `blocked_url` because the page had no readable main
    content.
  - The user saw process-only "结果整理/本轮过程" fragments, "找到 2 条来源", and
    a generic retry/failure answer instead of a useful or transparent outcome.
- **expected_behavior**:
  - Search-result wrapper pages such as `image.baidu.com/search/*` must not be
    accepted as answer-quality evidence just because their title repeats the
    query.
  - Platform WebResearch must distinguish the default builtin
    `web_search -> fetch_url -> evidence -> answer` path from optional
    provider-native/hosted search. Native search is not a default fallback unless
    explicitly configured and normalized into WebResearch evidence.
  - If only wrapper/low-confidence candidates are found, the turn should degrade
    to "no directly verifiable search results" / candidate-exhausted style
    diagnostics instead of attempting `fetch_url` on the wrapper and ending as
    `blocked_url`.
  - Frontend must not expose process-only "结果整理/本轮过程" as final answer body.
- **status**: `fixed_with_green_test`
- **notes**:
  - Behavioral regression coverage:
    `backend/tests/ai/test_web_search_orchestrator.py::test_public_html_filters_baidu_image_wrapper_result_as_no_results`
    and
    `backend/tests/ai/web_research/test_runtime.py::test_runtime_skips_search_wrapper_candidate_without_fetching`.

---

### BUG-2026-05-05-2305 Fashion ranking query used generic/LLM-style leaderboard relevance and stopped after one Baidu vertical candidate

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下 2026年最热门的 女性裙子款式排行！
  ```
- **preconditions**:
  - conversation_id: `2305`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - Runtime selected platform WebResearch through
    `builtin:web_search -> builtin:fetch_url`.
  - Public Baidu search returned only one useful-looking candidate, a Baidu
    note/video vertical result:
    `https://www.baidu.com/s?pd=note...&sa=vs_video_top_ugc`.
  - The turn ended as failed/partial with:
    `turn_outcome=failed`, `termination_reason=low_query_relevance`,
    `evidence_status=partial`, `fetched_urls=[]`, `answer_source=none`,
    and `web_research_relevance_profile=leaderboard`.
  - The user-visible answer said the system found candidates but had no
    sufficiently relevant/verifiable content, rather than producing a useful
    fashion trend/ranking answer.
  - Local RED testing showed the fashion prompt was treated as generic
    `leaderboard`, fashion trend pages were rejected as `low_relevance`, and the
    runtime did not expand beyond the single weak original-query search result.
- **expected_behavior**:
  - Non-LLM fashion ranking/trend queries must not inherit LLM leaderboard
    required terms or LLM trusted-source policy.
  - The query planner and relevance gate should use a fashion/trend-ranking
    profile whose required evidence terms match the prompt: 2026 freshness,
    women's dresses/skirts, styles, trends, and ranking/list markers.
  - If the original public search only yields wrappers or low-confidence
    vertical pages, the platform-owned `search -> fetch -> evidence -> answer`
    chain should expand to better search queries before declaring failure.
  - Relevant fashion/trend sources must still pass `fetch_url` and deterministic
    relevance before they can populate `fetched_urls`, citations, or completed
    WebResearch evidence.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression added at:
    `backend/tests/regressions/test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py`.
  - RED command before the fix:
    `python -m pytest tests\regressions\test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py -q`
    failed because the plan profile was `leaderboard`, the fashion page
    relevance was `low_relevance`, and only one search query was attempted.
  - This is related to but distinct from `BUG-2026-05-05-2295`: 2295 covered
    Baidu Images wrapper / blocked_url behavior, while 2305 covers domain
    relevance/profile mismatch plus missing query expansion for the same prompt
    family.
  - GREEN implementation adds a `fashion_trend_ranking` WebResearch profile,
    query expansion for 2026 women/dress trend ranking prompts, fashion-specific
    deterministic relevance, and candidate ordering that fetches relevant trend
    sources before weak Baidu vertical candidates.
  - GREEN command:
    `python -m pytest backend/tests/regressions/test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py backend/tests/ai/web_research/test_runtime.py::test_runtime_skips_search_wrapper_candidate_without_fetching backend/tests/ai/test_web_search_orchestrator.py::test_public_html_filters_baidu_image_wrapper_result_as_no_results -q`
    → `5 passed`.
  - Frontend display guard also covers this prompt family by suppressing
    blocked_url/generic retry copy and process-only residuals as final answer
    body; targeted vitest for `ChatMessageContentBlock.test.ts` and
    `use-ai-chat.test.ts` passed with `65 passed`.
  - This is behavioral + structural evidence only. It does not replace a
    real-dialogue smoke artifact for the full testing-discipline milestone gate.
  - Fresh smoke conversations `2309` and `2310` now complete with
    `web_research_relevance_profile=fashion_trend_ranking`,
    `fetched_urls=[Vogue, Marie Claire]`, `answer_source=fetched_body`, and
    Chinese ranked fashion answers. Smoke artifact:
    `.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2305-fashion-ranking/report.md`.

---

### BUG-2026-05-05-2308 Fashion ranking completed with raw English source snippets

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下 2026年最热门的 女性裙子款式排行！
  ```
- **preconditions**:
  - conversation_id: `2308`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime accepted Vogue / Marie Claire fetched evidence
- **current_wrong_behavior**:
  - The turn reached `turn_outcome=success`, `evidence_status=completed`,
    `answer_source=fetched_body`, and `final_output_source=recovery_evidence`.
  - The assistant content was still raw English source preview text such as
    `From leggy minis...` and `Here, the fashion trends shaping summer 2026...`
    instead of a Chinese ranked answer.
- **expected_behavior**:
  - For Chinese `fashion_trend_ranking` prompts, accepted fetched evidence must
    be rendered as a Chinese ranked fashion answer.
  - Raw English source descriptions or page teaser text must not be treated as
    the final answer when deterministic evidence is available.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression commit:
    `3a0ad7f15 test(ai): reproduce 2308 fashion recovery answer quality failure`.
  - GREEN implementation commit:
    `43456b670 fix(ai): complete fashion web research on trusted seeds`.
  - Behavioral regression:
    `backend/tests/regressions/test_bug_2026_05_05_2308_fashion_recovery_answer_quality.py`.
  - GREEN command:
    `python -m pytest tests\regressions\test_bug_2026_05_05_2308_fashion_recovery_answer_quality.py -q`
    -> `1 passed`.
  - Fresh smoke conversations `2309` and `2310` verified the visible answer is
    a Chinese ranked list and does not expose the raw English source snippets.

---

### BUG-2026-05-05-2299 Fashion ranking query with zero public-search results ended as no_answer_quality_evidence

- **reporter**: user
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下 2026年最热门的 女性裙子款式排行！
  ```
- **preconditions**:
  - conversation_id: `2299`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - CLI evidence from `python -m app.cli ai conversation show 2299 --json` showed
    `completion_reason=no_answer_quality_evidence`,
    `evidence_status=failed`, `answer_source=none`,
    `web_research_failure_kind=no_answer_quality_evidence`.
  - The builtin public Baidu backend returned zero accepted results with
    `status=no_results` and
    `failure_reason=public:baidu returned only low-confidence results`.
  - Because the turn retained the failed search status, WebResearch did not
    produce accepted fetched evidence for the exact user-visible query even
    though this prompt family has deterministic 2026 fashion trend seed sources.
- **expected_behavior**:
  - The platform WebResearch query plan for `fashion_trend_ranking` must still
    inject and fetch 2026 trusted fashion trend seeds when the public search
    backend returns zero or low-confidence results.
  - If those fetched seed pages pass deterministic relevance and contain body
    evidence, the canonical WebResearch evidence must be `completed` with
    `answer_source=fetched_body`, not `partial/failed` inherited from the public
    search backend.
  - Adjacent bug fixes for `blocked_url` (2295) or low-relevance Baidu vertical
    pages (2305) must not be used to close this zero-results failure unless a
    same-failure 2299 regression is present.
- **status**: `fix_in_progress`
- **notes**:
  - RED regression added at:
    `backend/tests/regressions/test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py::test_2299_no_baidu_results_still_fetches_2026_fashion_trusted_seeds`.
  - RED command before the fix failed because evidence stayed `partial` after
    trusted seed fetches:
    `python -m pytest backend/tests/regressions/test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py::test_2299_no_baidu_results_still_fetches_2026_fashion_trusted_seeds -q`.
  - GREEN implementation promotes planned trusted-seed candidate sets to a
    completed search result set before evidence normalization, so accepted
    fetched body evidence can complete the turn instead of inheriting Baidu
    `no_results`.
  - This is structural + behavioral evidence. Real-dialogue smoke/replay remains
    required before claiming full milestone/regression-suite green.

---

### BUG-2026-05-05-2304 Fashion ranking query stopped after a low-relevance Baidu note candidate

- **reporter**: user
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下 2026年最热门的 女性裙子款式排行！
  ```
- **preconditions**:
  - conversation_id: `2304`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - CLI evidence from `python -m app.cli ai conversation show 2304 --json` showed
    the first assistant turn ended with `completion_reason=low_query_relevance`,
    `evidence_status=partial`, `answer_source=none`, and
    `web_research_failure_kind=low_query_relevance`.
  - The only candidate URL was a Baidu `/link` "精选笔记" result. After fetch,
    deterministic relevance rejected it as unrelated/insufficient evidence.
  - The turn used `web_research_relevance_profile=leaderboard` and had no
    `query_profile`, `planned_search_queries`, or `trusted_seed_count`
    diagnostics, so the fashion-specific trusted sources were never reached.
- **expected_behavior**:
  - The prompt must be classified as `fashion_trend_ranking`, not generic
    `leaderboard`.
  - Low-relevance Baidu note or vertical-search candidates must not be the only
    evidence path for 2026 fashion ranking prompts.
  - The platform WebResearch plan should fetch trusted 2026 fashion trend seeds
    first, and accepted fetched body evidence should complete the turn with
    `answer_source=fetched_body`.
- **status**: `fix_in_progress`
- **notes**:
  - Same-ID/same-failure behavioral regression:
    `backend/tests/regressions/test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py::test_2304_low_relevance_baidu_note_does_not_stop_fashion_trusted_seed_fetch`.
  - The regression simulates the 2304 Baidu "精选笔记" low-relevance candidate and
    asserts that trusted Vogue / Marie Claire fashion sources are fetched before
    the low-relevance Baidu candidate can terminate the turn.
  - Current HEAD passes this regression because the fashion query profile and
    trusted-seed fetch path from the 2299/2305 fixes now cover 2304 as well.
  - No dedicated RED commit was preserved for this adjacent conversation-id
    regression. It is kept as post-fix coverage and must not be used by itself
    as a Trellis §6.2 RED->GREEN closure.

---

### BUG-2026-05-05-2311 LLM leaderboard completed with raw English source snippets and numeric fragments

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下大模型排行榜 2026  水平排行！
  ```
- **preconditions**:
  - conversation_id: `2311`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - CLI diagnostics showed `turn_outcome=success`,
    `termination_reason=completed`, `evidence_status=completed`,
    `answer_source=fetched_body`, `final_output_source=recovery_evidence`, and
    `web_research_relevance_profile=llm_leaderboard`.
  - The accepted fetched source was Artificial Analysis, while a noisy
    Baijiahao source was rejected.
  - Despite successful evidence, the assistant answer was raw English page copy
    plus orphan numeric fragments:
    `Comparison and ranking the performance of over 100 AI models...`,
    followed by lines such as `65.59`, `71.66`, `28.17`.
- **expected_behavior**:
  - For Chinese `llm_leaderboard` prompts, accepted leaderboard evidence must be
    rendered as a Chinese model-ranking answer with named models and metrics.
  - Raw English source descriptions or numeric columns must be considered
    replaceable evidence previews, not final user-facing answers.
  - The runtime may still report `answer_source=fetched_body`, but the visible
    answer must be assembled by the platform recovery/evidence layer.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression commit:
    `c5aedec2f test(ai): reproduce 2311 llm recovery answer quality failure`.
  - GREEN implementation commit:
    `79d063c5c fix(ai): render llm leaderboard recovery answers`.
  - Behavioral regression:
    `backend/tests/regressions/test_bug_2026_05_05_2311_llm_recovery_answer_quality.py`.
  - RED command failed with the expected assertion because the output was still
    `Comparison and ranking...` plus `65.59\n71.66`.
  - GREEN command:
    `python -m pytest tests\regressions\test_bug_2026_05_05_2311_llm_recovery_answer_quality.py -q`
    -> `2 passed`.
  - Fresh real-dialogue smoke conversation `2312` completed with
    `web_research_relevance_profile=llm_leaderboard`,
    `fetched_urls=["https://artificialanalysis.ai/leaderboards/models"]`,
    `answer_source=fetched_body`, and a Chinese answer headed
    `2026 大模型能力排行参考`.
  - Smoke artifact:
    `.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2311-llm-answer-quality/report.md`.

---

### BUG-2026-05-05-2315 AI news WebResearch accepted one stale source and dumped the article body

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  今日ai新闻查一下
  ```
- **preconditions**:
  - conversation_id: `2315`
  - agent: `15` / 智能助手
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - CLI diagnostics showed `turn_outcome=success`,
    `termination_reason=completed`, `evidence_status=completed`,
    `answer_source=fetched_body`, and `final_output_source=recovery_evidence`.
  - The fetched URL was a single NetEase repost:
    `https://www.163.com/dy/article/J1QO5JKJ05198CJN.html`.
  - The relevance profile was missing/null, so generic relevance marked the
    source as `unscored` with score `1.0`.
  - The visible answer copied a long article body directly, including old
    2024/5月10 AI daily items, instead of cross-checking current AI news and
    summarizing.
- **expected_behavior**:
  - Current/today AI news prompts must use a dedicated news relevance profile,
    not generic unscored acceptance.
  - A single stale or low-trust source must not complete the turn.
  - Completed AI-news research must be synthesized into a concise Chinese
    source-labeled summary; fetched article bodies must not be dumped directly.
- **status**: `fixed_with_green_test`
- **notes**:
  - RED regression commit:
    `0540196cb test(ai): reproduce 2315 ai news raw dump failure`.
  - GREEN implementation commit:
    `30e13ce0c fix(ai): require cross-checked evidence for ai news research`.
  - Regression coverage:
    `backend/tests/regressions/test_bug_2026_05_05_2315_ai_news_cross_check.py`.
  - GREEN targeted matrix:
    `python -m pytest tests\services\test_agent_chat_command_service_safe_partial.py tests\services\test_turn_failure_normalizer.py tests\regressions\test_bug_2026_05_05_2285_irrelevant_web_research_evidence.py tests\regressions\test_bug_2026_05_05_2293_llm_leaderboard_authority_fallback.py tests\regressions\test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py tests\regressions\test_bug_2026_05_05_2308_fashion_recovery_answer_quality.py tests\regressions\test_bug_2026_05_05_2311_llm_recovery_answer_quality.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research tests\ai\engine\test_turn_executor.py tests\ai\engine\test_cli_conversation_diagnostics.py tests\ai\engine\test_conversation_result_projector.py -q`
    passed `126`.
  - Structural checks:
    `python scripts\check_prompt_contracts.py`, targeted `ruff check`, and
    targeted `ruff format --check` all passed from `backend/`.
  - Fresh real-dialogue smoke:
    conversation `2321`, same prompt family `今日ai新闻查一下`, projected
    `turn_outcome=partial`, `evidence_status=partial`, `answer_source=none`,
    `web_research_relevance_profile=ai_news`, and did not leak the rejected
    NetEase/NVIDIA fetched body into the assistant answer.
  - Smoke artifact:
    `.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2315-ai-news-cross-check/report.md`.
  - This bug is distinct from the 2305/2311 leaderboard/fashion rendering
    issues because the missing contract is current-news source diversity and
    synthesis.

---

### BUG-2026-05-05-2326 AI news stopped after three noisy candidates and leaked generic retry process text

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下今日AI 新闻
  ```
- **preconditions**:
  - conversation_id: `2326`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - WebResearch runtime default path with builtin public search/fetch providers
- **current_wrong_behavior**:
  - CLI diagnostics for `conversation_id=2326` showed
    `turn_outcome=partial`, `termination_reason=insufficient_cross_checked_sources`,
    `evidence_status=partial`, and `web_research_relevance_profile=ai_news`.
  - The AI-news query plan produced 15 candidate URLs from three planned search
    queries, but runtime fetched only the first 3 candidates.
  - Only one source was accepted:
    `https://5gai.cctv.com/AI/index.shtml`; two Baijiahao candidates were
    rejected as `low_query_relevance`, so the turn stopped before later
    candidate sources could be fetched.
  - The persisted assistant content and `turn_flow.answer_card` used a Chinese
    safe partial message, but `turn_flow.error_surface.message` still contained
    the generic English fallback:
    `The assistant could not finish this turn. Please retry.`
- **expected_behavior**:
  - AI-news WebResearch must use a profile-aware fetch depth that can continue
    past the first three noisy public-search candidates until two independent
    relevant sources are accepted or the profile-specific cap is exhausted.
  - It must keep the evidence gate: if expanded fetch still cannot cross-check,
    the turn should remain partial without dumping fetched article bodies.
  - Historical and live UI should prefer the safe answer card/content and must
    not expose generic English retry text in transcript-first process surfaces.
- **status**: `fixed_with_green_test`
- **notes**:
  - CLI evidence command:
    `python -m app.cli ai conversation show 2326 --tail 8 --diagnostics-only --json`.
  - RED backend regression:
    `backend/tests/regressions/test_bug_2026_05_05_2326_ai_news_fetch_depth.py`
    failed because `BAIDU_REUTERS_WRAPPER` was not fetched under the current
    fixed `max_fetches=3` behavior.
  - RED frontend regression:
    `frontend/apps/web-antd/src/components/business/ai-chat-kernel/__tests__/ChatMessageKernel.test.ts`
    failed because the kernel overview rendered
    `The assistant could not finish this turn. Please retry.` instead of the
    safe Chinese answer digest for a 2326-style partial research turn.
  - GREEN implementation adds `fetch_candidate_depth=8` to the `ai_news`
    WebResearch query plan and uses the plan-specific effective fetch cap in
    runtime candidate selection while preserving early stop after enough
    independent accepted sources are found.
  - GREEN commands:
    `python -m pytest tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research\test_query_planning.py tests\ai\web_research\test_runtime.py tests\ai\engine\test_turn_flow_projector.py -q`
    → `42 passed`; broader AI runtime/WebResearch command → `136 passed`.
  - Fresh real-dialogue smoke:
    conversation `2329`, same prompt `查一下今日AI 新闻`, projected
    `turn_outcome=success`, `evidence_status=completed`,
    `answer_source=fetched_body`, and fetched both
    `https://5gai.cctv.com/AI/index.shtml` and `https://ainewstoday.net/`.
  - Playwright UI smoke:
    admin conversation detail for `2329` showed the corrected news digest,
    no generic English retry text, no generic channel/homepage descriptions,
    and no bad `Google Veo 3...：Uk Sovereign...` pairing.
  - Smoke artifact:
    `.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2326-2327-ai-news-depth-quality/report.md`.

---

### BUG-2026-05-05-2327 AI news completed with generic channel/homepage descriptions

- **reporter**: user / QA
- **report_date**: 2026-05-05
- **reproduction_prompt**:
  ```text
  查一下今日AI 新闻
  ```
- **preconditions**:
  - conversation_id: `2327`
  - agent: `59` / 猫娘智能体
  - owner_type: `platform_admin`
  - tools in scope: `web_search`, `fetch_url`
  - built from the current BUG-2026-05-05-2326 GREEN candidate after increasing
    `ai_news` fetch depth
- **current_wrong_behavior**:
  - CLI diagnostics for `conversation_id=2327` showed
    `turn_outcome=success`, `evidence_status=completed`,
    `answer_source=fetched_body`, and `web_research_relevance_profile=ai_news`.
  - The persisted assistant answer used generic site descriptions as the news
    digest:
    `聚焦数字中国建设，关注AI科技前沿...` and
    `AI News Today delivers AI news spanning...`.
  - The fetched bodies did contain concrete items such as
    `AI与科学仪器融合已到关键节点` and
    `Meta Is Tracking Employee Activity To Train Smarter AI Models`, but the
    structured renderer preferred page `description` fields before body-derived
    news items.
- **expected_behavior**:
  - A completed `ai_news` answer must render concrete news items extracted from
    accepted fetched bodies or article metadata.
  - Generic channel, homepage, or aggregator descriptions must not appear as
    final news bullets.
  - If fewer than two concrete items can be extracted, structured `ai_news`
    recovery must return no completed answer so the platform can fail closed
    instead of presenting filler text as success.
- **status**: `fixed_with_green_test`
- **notes**:
  - CLI evidence command:
    `python -m app.cli ai conversation show 2327 --tail 2 --json`.
  - RED backend regression:
    `backend/tests/regressions/test_bug_2026_05_05_2327_ai_news_digest_quality.py`
    fails because the current renderer chooses generic `description` text before
    body-derived news items.
  - GREEN implementation makes the AI-news structured renderer reject generic
    channel/homepage copy, match each `fetch_url` result to its own fetched
    page payload, extract concrete body headlines, and avoid pairing a headline
    with the next headline as its detail.
  - GREEN commands:
    `python -m pytest tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research\test_query_planning.py tests\ai\web_research\test_runtime.py tests\ai\engine\test_turn_flow_projector.py -q`
    → `42 passed`; broader AI runtime/WebResearch command → `136 passed`.
  - Fresh real-dialogue smoke:
    conversation `2329` rendered:
    `今日 AI 新闻摘要` with concrete bullets for
    `规范人工智能科技活动伦理治理` and
    `Google Veo 3 Is Transforming Ai Video Creation And Content Production`.
  - Scripted content checks for `2329`:
    `contains_generic_desc=False`, `contains_bad_pair=False`,
    `contains_retry=False`, `error_surface=null`.
  - Playwright UI smoke:
    admin conversation detail for `2329` showed the same corrected digest,
    with no browser console errors and no failed browser requests.
  - Smoke artifact:
    `.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2326-2327-ai-news-depth-quality/report.md`.

---

### BUG-2026-05-06-2340 Runtime context diagnostics rendered as fake sources after provider failure

- **reporter**: user / QA
- **report_date**: 2026-05-06
- **reproduction_prompt**:
  ```text
  帮我搜索一下2026年中国新能源汽车销量排行
  ```
- **preconditions**:
  - conversation_id: `2340`
  - assistant_message_id: `13413`
  - trace_id: `16136d2b-070d-45fd-8d2d-bea7f68aaed1`
  - agent: `59` / 猫娘智能体
  - online search runtime capability removed by task
    `05-05-remove-online-search-capability`
  - provider: ASXS / `gpt-5.5`
- **current_wrong_behavior**:
  - Runtime diagnostics correctly showed `intent=direct_reply`,
    `selected_tool_names=[]`, `candidate_tool_names=[]`,
    `tool_rounds_used=0`, and `failure_kind=provider_unavailable`.
  - Persisted/projected `turn_flow` incorrectly converted runtime diagnostic
    `context_sources` into three evidence/source chips:
    `skill_resolver`, `long_term_memory`, and `gpt-5.5`.
  - The retrieval stage was displayed as completed with `source_count=3`, so
    the UI showed `找到 3 条来源` and a completed-looking status even though
    the turn actually failed with `Connection error.`.
- **expected_behavior**:
  - `context_sources` remain diagnostics/inventory only and must not become
    answer evidence, retrieval counts, or source chips.
  - Provider-failed turns with no RAG/tool evidence must render as failed/error
    and either omit retrieval or show zero/skipped retrieval.
  - Existing polluted `turn_flow` payloads should be scrubbed by read-model
    normalization without requiring a data migration.
- **status**: `fixed_with_green_test`
- **notes**:
  - CLI evidence command:
    `python -m app.cli ai conversation show 2340 --tail 12 --diagnostics-only --json`
    showed honest terminal truth: failed provider layer, no tools, no tool
    rounds.
  - RED backend regression:
    `backend/tests/regressions/test_bug_2026_05_06_2340_turn_flow_context_sources.py`
    failed before implementation because runtime context sources became
    evidence and polluted stored turn_flow stayed source-counted.
  - RED frontend regression:
    `frontend/apps/web-antd/src/components/business/ai-chat-kernel/__tests__/ChatMessageKernel.test.ts`
    failed before implementation because the kernel rendered
    `turnRetrievalSummary` and `turnStageStatus.completed`.
    - GREEN implementation makes engine/read-model turn-flow evidence resolve
      from real RAG/tool evidence only, scrubs persisted title-only runtime
      evidence, downgrades retrieval refs to zero/skipped when evidence is
      removed, and makes frontend kernel/timeline failure state authoritative over
      stale completed retrieval chrome.
    - Follow-up CLI parity regression:
      `backend/tests/test_ai_conversation_cli.py` now verifies full
      `ai conversation show 2340 --json`-style output also replaces nested
      stored `metadata.turn_record.turn_flow` with the scrubbed canonical
      projection, so the audit command itself cannot keep showing
      `Retrieved 3 sources` or `source_count=3`.
    - Real-browser smoke:
      `frontend/apps/web-antd/__tests__/e2e/ai-chat-turn-flow-regression.spec.ts`
      mounts the real chat kernel in Chromium with the polluted 2340 payload and
      asserts that fake source chrome is not rendered.
    - Task record:
      `.trellis/tasks/05-06-turn-flow-runtime-context-source-scrub/`.

---

## 用户/QA 批量上报模板（粘贴即可）

对话遇到不对的场景，请用下面格式追加到本文件末尾（Codex 看到该条目会自动为其写 RED 测试）：

````markdown
### BUG-YYYY-MM-DD-NNN <一句话标题>

- **reporter**: <谁>
- **report_date**: YYYY-MM-DD
- **reproduction_prompt**:
  ```
  <对话里用户真实输入的完整文字，可多行>
  ```
- **preconditions**:
  - page_key: <或 N/A>
  - agent: <或 N/A>
  - bound KB ids: <或 N/A>
  - installed skills: <或 N/A>
  - thread memory state: <或 N/A>
  - 其他: <可选>
- **current_wrong_behavior**:
  <粘贴 AI 实际的错误回复，或描述它卡住 / 空输出 / 选错工具等>
- **expected_behavior**:
  <一句话描述正确应该怎样>
- **status**: `reported`
- **notes**: <任何额外线索，比如"从 conversation id 1234 抓的"、"只在 page_search 场景出现"等>
````

## Codex 子代理处理流程

1. 看到 `status=reported` 或 `reproduced_locally` 的条目，优先认领
2. 第一个 commit：复现测试（RED），status → `red_test_written`
3. 第二个 commit 或后续 commit：修复代码，同一测试变绿，status → `fixed_with_green_test`
4. PR 中引用 bug_id + RED commit hash + GREEN commit hash
5. 禁止跳过 RED 步骤直接提交 GREEN（违反 testing-discipline.md §6.2）

## 不允许的"关闭"理由

以下说辞不能关闭 bug（参考 `testing-discipline.md §6.3`）：

- "现有测试都通过了"
- "我在本地手动跑通了" （作为补充可以，但必须加自动化复现测试）
- "这是使用习惯问题" （除非用户显式确认且更新 UI 文案）
- "该路径已被 sunset" （若是，必须在 sunset-list.md 中明确标记且有迁移指引）
