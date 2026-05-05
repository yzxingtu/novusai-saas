# WebResearch 2315 AI News Cross-Check Smoke

Test type: smoke

## Scenario

- Scenario ID: `WEBRESEARCH-2026-AI-NEWS-CROSS-CHECK`
- Historical bad conversation: `2315`
- Fresh smoke conversation: `2321`
- Prompt: `今日ai新闻查一下`
- Scope: platform-owned `web_search -> fetch_url -> evidence -> answer` chain
- Expected result: current AI-news prompts must use `ai_news` relevance, refuse
  unverified or stale single-source evidence, and never expose fetched page
  bodies as the assistant answer when cross-checking fails.

## Historical Failure

Conversation `2315` was marked successful even though it fetched one stale
NetEase/163 repost:

- `turn_outcome=success`
- `termination_reason=completed`
- `evidence_status=completed`
- `answer_source=fetched_body`
- `final_output_source=recovery_evidence`
- `web_research_relevance_profile=null`
- visible answer copied a long old AI Daily article body

## Fix Evidence

- RED commit: `0540196cb test(ai): reproduce 2315 ai news raw dump failure`
- GREEN commit: `30e13ce0c fix(ai): require cross-checked evidence for ai news research`
- The runtime now detects `ai_news`, expands current AI-news queries, and
  requires two independent accepted sources.
- Same-host URL variants are counted as one independent source.
- Partial or insufficient evidence produces failed `fetch_url` tool results
  with empty output, so raw fetched bodies cannot become recovery output.
- Completed AI-news evidence renders as a concise source-labeled summary.

## Commands

Run from `E:\git_clone\novusai-saas-yudi\backend` unless noted.

```powershell
python -m pytest tests\services\test_agent_chat_command_service_safe_partial.py tests\services\test_turn_failure_normalizer.py tests\regressions\test_bug_2026_05_05_2285_irrelevant_web_research_evidence.py tests\regressions\test_bug_2026_05_05_2293_llm_leaderboard_authority_fallback.py tests\regressions\test_bug_2026_05_05_2305_generic_trend_ranking_search_plan.py tests\regressions\test_bug_2026_05_05_2308_fashion_recovery_answer_quality.py tests\regressions\test_bug_2026_05_05_2311_llm_recovery_answer_quality.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research tests\ai\engine\test_turn_executor.py tests\ai\engine\test_cli_conversation_diagnostics.py tests\ai\engine\test_conversation_result_projector.py -q
python scripts\check_prompt_contracts.py
python -m ruff check app\ai\web_research\query_planning.py app\ai\web_research\relevance.py app\ai\web_research\normalization.py app\ai\web_research\runtime.py app\ai\engine\recovery_tool_result_helpers.py app\ai\engine\turn_executor.py app\ai\engine\recovery_web_research_gate.py app\ai\engine\final_output_policy.py app\services\ai\agent_chat_command_service.py app\services\ai\turn_failure_normalizer.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research\test_query_planning.py tests\ai\web_research\test_evidence_schema.py tests\ai\engine\test_conversation_result_projector.py tests\services\test_agent_chat_command_service_safe_partial.py tests\services\test_turn_failure_normalizer.py
python -m ruff format --check app\ai\web_research\query_planning.py app\ai\web_research\relevance.py app\ai\web_research\normalization.py app\ai\web_research\runtime.py app\ai\engine\recovery_tool_result_helpers.py app\ai\engine\turn_executor.py app\ai\engine\recovery_web_research_gate.py app\ai\engine\final_output_policy.py app\services\ai\agent_chat_command_service.py app\services\ai\turn_failure_normalizer.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research\test_query_planning.py tests\ai\web_research\test_evidence_schema.py tests\ai\engine\test_conversation_result_projector.py tests\services\test_agent_chat_command_service_safe_partial.py tests\services\test_turn_failure_normalizer.py
python scripts\verify_tool_policy_logging.py --agent-id 15 --user-id 1 --message "今日ai新闻查一下"
python -m app.cli ai conversation show 2321 --tail 20 --diagnostics-only --json
python -m app.cli ai conversation show 2321 --tail 10 --json
```

## Results

- Targeted regression and WebResearch matrix: `126 passed`.
- Prompt contract check: passed.
- Targeted ruff check: passed.
- Targeted ruff format check: passed.
- Fresh CLI smoke created conversation `2321`.

Key compact diagnostics for `2321`:

```text
turn_outcome=partial
termination_reason=low_query_relevance
final_output_source=partial_output
evidence_status=partial
answer_source=none
web_research_failure_kind=low_query_relevance
web_research_relevance_profile=ai_news
search_provider=builtin:web_search
fetch_provider=builtin:fetch_url
fetched_urls=[]
rejected_urls=[
  "https://www.nvidia.cn/",
  "https://www.nvidia.cn/?adid=techblog-costperformance&utm_source=edgehub"
]
```

Visible assistant content for `2321`:

```text
我找到了候选来源，但没有拿到与问题足够相关、可核实的内容，因此不生成结论。
```

This is a pass for the 2315 class because the public search run only produced
unaccepted candidates. The platform refused to synthesize news, kept
`answer_source=none`, and did not dump page bodies.

## Playwright

Local UI target:

```text
http://127.0.0.1:5666/admin/ai/conversations
```

Validation:

- Opened the admin conversation list.
- Opened conversation `2321` detail drawer.
- Verified the runtime diagnostics show `evidence_status=partial` and
  `answer_source=none`.
- Verified the message card shows `异常`, not a completed/successful answer.
- Verified the visible answer is the safe partial text above.
- Verified no raw NetEase text such as `财联社AI daily`, `网易号`, `AAAI 2024`,
  `淘宝VisionPro` appeared in the UI.
- Verified no rejected NVIDIA homepage body text such as `NVIDIA Nemotron 3 Omni`
  appeared in the UI.

Screenshot:

```text
.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2315-ai-news-cross-check/playwright-conversation-2321-detail.png
```

## Judge

Pass.

The current code path no longer treats a single stale/low-trust AI-news source
as completed evidence, does not mark partial evidence as answer-quality output,
and does not expose fetched article bodies as the final assistant answer.
