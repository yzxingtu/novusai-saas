# WebResearch 2305 Fashion Ranking Smoke Report

Scenario ID: `WEBRESEARCH-2026-FASHION-RANKING`
Test type: smoke
Date: 2026-05-05
Runner: Codex main auditor
Environment: local backend/frontend, branch `codex/admin-account-ai-availability`
Provider / model: real AgentChatService path with platform WebResearchRuntime;
builtin `web_search` plus builtin `fetch_url`; hosted/native search skipped by
default
Historical bad conversation: `2305`
Fresh smoke conversation: `2310`
Related fresh smoke conversation: `2309`
Additional same-code resmoke conversation: `2313`
Playwright screenshots:
`smoke-runs/2026-05-05-webresearch-2305-fashion-ranking/playwright-2310-fashion-ranking-detail.png`
and `smoke-runs/2026-05-05-webresearch-2305-fashion-ranking/webresearch-2309-fashion-ranking-detail.png`
Smoke evidence status: `pass`
Relevant GREEN commits:
`0259f4a38`, `43456b670`

## Prompt

```text
查一下 2026年最热门的 女性裙子款式排行！
```

## Bug Being Proved Fixed

`BUG-2026-05-05-2305` originally stopped after a Baidu note/video style
candidate. CLI diagnostics for historical conversation `2305` showed
`turn_outcome=failed`, `termination_reason=low_query_relevance`,
`evidence_status=partial`, `fetched_urls=[]`, `answer_source=none`, and
`web_research_relevance_profile=leaderboard`.

The current code must classify the same prompt family as
`fashion_trend_ranking`, fetch deterministic trusted fashion sources before
Baidu low-relevance candidates can terminate the run, and render a Chinese
ranked fashion answer rather than returning the conservative no-evidence
fallback.

## Required Observable Outcome

- Default provider path is platform-owned `builtin:web_search` +
  `builtin:fetch_url`.
- Hosted/native search is not required for an OpenAI-compatible provider.
- The query profile is `fashion_trend_ranking`, not generic `leaderboard`.
- Trusted fashion seeds are included before Baidu wrapper/note candidates.
- Accepted fetched pages populate `fetched_urls` and `answer_source=fetched_body`.
- The visible answer is a Chinese ranked list of 2026 dress/skirt styles.
- The visible answer does not contain the fallback text
  `没有拿到与问题足够相关、可核实的内容`.
- The visible answer does not leak raw English teaser snippets such as
  `From leggy minis`.

## Commands / UI Path

```text
cd backend
python -m app.cli ai conversation show 2305 --tail 12 --diagnostics-only --json
python -m app.cli ai conversation show 2310 --tail 12 --diagnostics-only --json
python -m app.cli ai conversation show 2310 --tail 2 --json
python scripts\verify_tool_policy_logging.py --agent-id 59 --user-id 1 --message "查一下 2026年最热门的 女性裙子款式排行！"
```

Browser path:

```text
Open http://localhost:5666/admin/ai/conversations
Open conversation 2310 from the admin conversation table
Verify runtime diagnostics and message flow in the detail drawer
Capture screenshot to playwright-2310-fashion-ranking-detail.png
Open conversation 2313 from the admin conversation table
Verify the latest same-code resmoke diagnostics and message flow in the detail
drawer
```

## CLI Diagnostics Snapshot

Historical conversation `2305` remains a historical failure:

```json
{
  "conversation_id": 2305,
  "turn_outcome": "failed",
  "termination_reason": "low_query_relevance",
  "partial_exit_reason": "low_query_relevance",
  "final_output_source": "partial_output",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "partial",
  "fetched_urls": [],
  "answer_source": "none",
  "web_research_failure_kind": "low_query_relevance",
  "web_research_relevance_profile": "leaderboard",
  "web_research_relevance_rejection_count": 1
}
```

Fresh real-dialogue smoke `2310`:

```json
{
  "conversation_id": 2310,
  "turn_outcome": "success",
  "termination_reason": "completed",
  "final_output_source": "recovery_evidence",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "fetched_urls": [
    "https://www.vogue.com/article/spring-2026-dress-trends",
    "https://www.marieclaire.com/fashion/summer-fashion/summer-fashion-trends-2026/"
  ],
  "rejected_urls": [],
  "answer_source": "fetched_body",
  "web_research_failure_kind": null,
  "web_research_relevance_profile": "fashion_trend_ranking",
  "web_research_relevance_rejection_count": 0
}
```

Additional same-code real-dialogue resmoke `2313`:

```json
{
  "conversation_id": 2313,
  "turn_outcome": "success",
  "termination_reason": "completed",
  "final_output_source": "recovery_evidence",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "fetched_urls": [
    "https://www.marieclaire.com/fashion/summer-fashion/summer-fashion-trends-2026/"
  ],
  "rejected_urls": [],
  "answer_source": "fetched_body",
  "web_research_failure_kind": null,
  "web_research_relevance_profile": "fashion_trend_ranking",
  "web_research_relevance_rejection_count": 0
}
```

The `2313` run is useful because Vogue returned a transient fetch error, yet the
platform runtime still completed from the remaining accepted Marie Claire body
evidence instead of falling back to a failed/partial low-relevance answer.

Visible answer excerpt from `2310`:

```text
基于已抓取的Vogue、Marie Claire等可核实来源，可整理为 2026 女性裙装热门款式参考排行：
1. 迷你裙/短款连衣裙
2. 碎花连衣裙
3. 蕾丝裙/蕾丝细节
...
来源：Vogue、Marie Claire。
```

## Playwright Evidence

The admin conversation detail drawer for `2310` displayed:

- provider event `evidence_status=completed`;
- provider event `answer_source=fetched_body`;
- `web_research_relevance_profile=fashion_trend_ranking`;
- fetched URLs for Vogue and Marie Claire;
- assistant message content headed `2026 女性裙装热门款式参考排行`;
- no raw English source teaser as the final answer.

The admin conversation detail drawer for latest resmoke `2313` was also opened
in Playwright and displayed:

- provider event `evidence_status=completed`;
- provider event `answer_source=fetched_body`;
- intent plan `web_research completed`;
- assistant message content headed `2026 女性裙装热门款式参考排行`;
- Marie Claire cited as the accepted source;
- no no-evidence fallback text and no raw English teaser as the final answer.

The earlier screenshot
`playwright-2309-fashion-ranking-detail-failed.png` is retained only as a
superseded wrong-button/browser-attempt artifact. It is not the accepted smoke
evidence. The accepted screenshot is
`playwright-2310-fashion-ranking-detail.png`.

`browser_console_messages onlyErrors=true` returned no errors during the final
2310 and 2313 drawer checks.

## Judge

Status: `pass`

Checklist:

- [x] Historical 2305 was inspected and remains recorded as failed historical
      evidence.
- [x] Fresh 2310 real-dialogue smoke completed the same prompt family.
- [x] Fresh 2313 same-code resmoke completed the same prompt family even when
      Vogue fetch failed and Marie Claire was the accepted source.
- [x] `fetched_urls` contains Vogue and Marie Claire.
- [x] `answer_source=fetched_body` and `final_output_source=recovery_evidence`.
- [x] Visible answer is a Chinese ranked fashion list.
- [x] The no-evidence fallback text is absent.
- [x] Raw English source snippets are not used as the final answer.

Residual note:

This smoke proves the current code path for the fashion ranking prompt family.
It does not rewrite the historical `2305` turn record, so `2305` itself should
continue to be described as the original failure anchor.
