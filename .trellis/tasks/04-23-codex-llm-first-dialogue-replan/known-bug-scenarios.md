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

## 用户/QA 批量上报模板（粘贴即可）

对话遇到不对的场景，请用下面格式追加到本文件末尾（Codex 看到该条目会自动为其写 RED 测试）：

```markdown
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
```

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
