# WebResearch 2326/2327 AI News Depth And Digest Quality Smoke

Test type: smoke

## Scenario

- Scenario ID: `WEBRESEARCH-2026-AI-NEWS-DEPTH-QUALITY`
- Historical bad conversations: `2326`, `2327`
- Fresh smoke conversation: `2329`
- Prompt: `查一下今日AI 新闻`
- Scope: platform-owned `web_search -> fetch_url -> evidence -> answer` chain
- Expected result: current AI-news prompts must fetch beyond early noisy public
  candidates when the profile requires cross-checking, then render concrete
  source-labeled news bullets instead of generic channel/homepage descriptions.

## Historical Failures

Conversation `2326` failed closed too early:

- `turn_outcome=partial`
- `termination_reason=insufficient_cross_checked_sources`
- `evidence_status=partial`
- `web_research_relevance_profile=ai_news`
- 15 candidate URLs were available, but only the first 3 were fetched.
- Only `https://5gai.cctv.com/AI/index.shtml` was accepted before the runtime
  stopped.
- `turn_flow.error_surface.message` still exposed the generic English retry
  copy.

Conversation `2327` completed, but its answer was low quality:

- `turn_outcome=success`
- `evidence_status=completed`
- `answer_source=fetched_body`
- `web_research_relevance_profile=ai_news`
- The final answer used generic site descriptions such as
  `聚焦数字中国建设...` and `AI News Today delivers AI news spanning...`
  instead of concrete fetched news items.

## Fix Evidence

- RED commit for 2326:
  `190eaac97 test(ai): reproduce 2326 ai news partial failure`
- RED commit for 2327:
  `b95d41fc4 test(ai): reproduce 2327 ai news generic digest`
- GREEN implementation commit: recorded in the final commit that includes this
  smoke report.
- `ai_news` query planning now carries `fetch_candidate_depth=8`.
- WebResearch runtime computes an effective fetch cap from the plan, while still
  keeping early stop once enough independent accepted sources are found.
- The AI-news structured renderer now avoids generic channel/homepage
  descriptions, matches each `fetch_url` result to its own fetched page payload,
  extracts concrete body headlines, and does not use the next headline as the
  current headline's detail.
- Terminal turn-flow failures now prefer the safe fallback answer over generic
  process retry text.

## Commands

Run from `E:\git_clone\novusai-saas-yudi\backend` unless noted.

```powershell
python -m pytest tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py tests\ai\web_research\test_query_planning.py tests\ai\web_research\test_runtime.py tests\ai\engine\test_turn_flow_projector.py -q
python -m pytest tests\services\test_agent_chat_command_service_safe_partial.py tests\services\test_turn_failure_normalizer.py tests\services\test_conversation_turn_flow_projector.py tests\ai\engine\test_cli_conversation_diagnostics.py tests\ai\engine\test_conversation_result_projector.py tests\ai\engine\test_turn_executor.py tests\ai\web_research tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2315_ai_news_cross_check.py -q
python scripts\check_prompt_contracts.py
ruff check app\ai\engine\recovery_tool_result_helpers.py app\ai\engine\turn_flow_projector.py app\ai\web_research\query_planning.py app\ai\web_research\runtime.py tests\ai\engine\test_turn_flow_projector.py tests\ai\web_research\test_query_planning.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py
ruff format --check app\ai\engine\recovery_tool_result_helpers.py app\ai\engine\turn_flow_projector.py app\ai\web_research\query_planning.py app\ai\web_research\runtime.py tests\ai\engine\test_turn_flow_projector.py tests\ai\web_research\test_query_planning.py tests\regressions\test_bug_2026_05_05_2326_ai_news_fetch_depth.py tests\regressions\test_bug_2026_05_05_2327_ai_news_digest_quality.py

# from E:\git_clone\novusai-saas-yudi\frontend\apps\web-antd
pnpm exec vitest run src/components/business/ai-chat-kernel/__tests__/ChatMessageKernel.test.ts src/components/business/ai-chat-kernel/__tests__/TurnTimeline.test.ts src/components/business/ai-chat-panel/__tests__/ChatMessageContentBlock.test.ts src/components/business/ai-chat-panel/__tests__/use-ai-chat.test.ts
pnpm exec eslint apps/web-antd/src/components/business/ai-chat-kernel/turn-stage-presentation.ts apps/web-antd/src/components/business/ai-chat-kernel/__tests__/ChatMessageKernel.test.ts

# real-dialogue smoke / real browser verification
python scripts\verify_tool_policy_logging.py --agent-id 59 --user-id 1 --message "查一下今日AI 新闻"
python -m app.cli ai conversation show 2329 --tail 8 --diagnostics-only --json
python -m app.cli ai conversation show 2329 --tail 2 --json
```

## Results

- Targeted 2326/2327/2315 + WebResearch/projection regression set:
  `42 passed`.
- Broader AI runtime/WebResearch regression set: `136 passed`.
- Prompt contract check: passed.
- Targeted ruff check: passed.
- Targeted ruff format check: passed.
- Frontend targeted vitest set: `84 passed`.
- Frontend targeted eslint: `0 errors`; existing
  `vue/one-component-per-file` warnings remain in `ChatMessageKernel.test.ts`.
- Fresh CLI smoke created conversation `2329`.

Key compact diagnostics for `2329`:

```text
turn_outcome=success
termination_reason=completed
final_output_source=recovery_evidence
evidence_status=completed
answer_source=fetched_body
web_research_relevance_profile=ai_news
search_provider=builtin:web_search
fetch_provider=builtin:fetch_url
fetched_urls=[
  "https://5gai.cctv.com/AI/index.shtml",
  "https://ainewstoday.net/"
]
rejected_urls=[
  "https://baijiahao.baidu.com/s?id=1864336909927346035&wfr=spider&for=pc",
  "https://baijiahao.baidu.com/s?id=1864035867509140983&wfr=spider&for=pc",
  "https://www.nvidia.cn/"
]
```

Visible assistant content for `2329`:

```text
今日 AI 新闻摘要：
1. 规范人工智能科技活动伦理治理：记者7日获悉，工业和信息化部等十部门近日联合印发《人工智能科技伦理审查与服务办法（试行）》（以下简称《办法》），为我国人工智能科技伦理审查与服务工作提供了明确指引。（来源：央视网数智频道-人工智能）
2. Google Veo 3 Is Transforming Ai Video Creation And Content Production：页面列出的时间为 Apr 30, 2026。（来源：AI News Today）
来源：央视网数智频道-人工智能、AI News Today。
```

Scripted content assertions:

```text
contains_generic_desc=False
contains_bad_pair=False
contains_retry=False
error_surface=null
```

## Playwright

Local UI target:

```text
http://localhost:5666/admin/ai/conversations
```

Validation:

- Used local dev admin bootstrap to open the real admin frontend.
- Found the table row with `rowid=2329` and title `查一下今日AI 新闻`.
- Opened the conversation detail drawer through the operation-column button.
- Verified the drawer shows `对话详情`, the prompt, `今日 AI 新闻摘要`, and the
  concrete `Google Veo 3...` item.
- Verified the drawer does not contain:
  - `The assistant could not finish this turn. Please retry.`
  - `聚焦数字中国建设`
  - `delivers AI news spanning`
  - `Daily trending Artificial Intelligence`
  - `Google Veo 3...：Uk Sovereign...`
- Browser console errors: none.
- Failed browser requests: none.

Screenshots:

```text
.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2326-2327-ai-news-depth-quality/playwright-conversation-2329-row.png
.trellis/tasks/05-04-web-research-runtime-rewrite/smoke-runs/2026-05-05-webresearch-2326-2327-ai-news-depth-quality/playwright-conversation-2329-detail.png
```

## Cross-Audit

- Root cause category: test coverage gap plus implicit assumption.
- 2326 root cause: `ai_news` required two independent sources but inherited a
  global `max_fetches=3`, so noisy early candidates exhausted the fetch cap.
- 2327 root cause: completed AI-news rendering preferred metadata descriptions
  before concrete body-derived items.
- Prevention: bug-specific RED tests now cover profile-aware fetch depth,
  concrete AI-news digest extraction, generic-copy suppression, and the fresh
  browser-visible smoke result.

## Judge

Pass.

The current code path no longer stops the AI-news search/fetch chain after the
first three noisy candidates, no longer treats generic channel/homepage
descriptions as final news bullets, and the real admin UI renders the corrected
2329 answer without generic retry text or bad headline-detail pairing.
