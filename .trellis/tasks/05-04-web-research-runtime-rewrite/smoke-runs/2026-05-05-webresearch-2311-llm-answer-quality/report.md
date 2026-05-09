# Historical Only

This smoke report is superseded by the 05-05 and 05-08 online-search
retirement work. Do not use it as current acceptance, current smoke
expectation, or evidence to restore WebResearch, `web_search`, or `fetch_url`.

# WebResearch 2311 LLM Leaderboard Answer Quality Smoke Report

Scenario ID: `WEBRESEARCH-2026-LLM-RANKING-ANSWER-QUALITY`
Test type: smoke
Date: 2026-05-05
Runner: Codex main auditor
Environment: local backend/frontend, branch `codex/admin-account-ai-availability`
Provider / model: real AgentChatService path with platform WebResearchRuntime;
builtin `web_search` plus builtin `fetch_url`; hosted/native search skipped by
default
Historical bad conversation: `2311`
Fresh smoke conversation: `2312`
Additional same-code resmoke conversation: `2314`
Playwright screenshot:
`smoke-runs/2026-05-05-webresearch-2311-llm-answer-quality/playwright-2312-llm-ranking-detail.png`
Smoke evidence status: `pass`
RED commit:
`c5aedec2f test(ai): reproduce 2311 llm recovery answer quality failure`
GREEN commit:
`79d063c5c fix(ai): render llm leaderboard recovery answers`

## Prompt

```text
查一下大模型排行榜 2026  水平排行！
```

## Bug Being Proved Fixed

`BUG-2026-05-05-2311` was not a search/fetch failure. Historical conversation
`2311` had completed evidence from Artificial Analysis, but the final answer was
raw English page copy and orphan numeric fragments:

```text
Comparison and ranking the performance of over 100 AI models ...
65.59
71.66
28.17
```

The current code must render accepted `llm_leaderboard` evidence into a Chinese
model-ranking answer, and raw English source descriptions/numeric columns must
be treated as replaceable evidence previews rather than final user-facing
answers.

## Required Observable Outcome

- Default provider path is platform-owned `builtin:web_search` +
  `builtin:fetch_url`.
- Hosted/native search is not required for an OpenAI-compatible provider.
- The query profile is `llm_leaderboard`.
- Accepted fetched evidence may come from Artificial Analysis.
- Noisy Baidu/Baijiahao sources may be rejected without failing the turn if
  enough accepted authoritative evidence remains.
- The visible answer is a Chinese leaderboard summary with named models and
  metrics.
- The visible answer does not begin with the raw English page description
  `Comparison and ranking the performance`.
- The visible answer does not consist of orphan numeric fragments such as
  `65.59` and `71.66`.

## Commands / UI Path

```text
cd backend
python -m app.cli ai conversation show 2311 --tail 12 --diagnostics-only --json
python -m app.cli ai conversation show 2312 --tail 12 --diagnostics-only --json
python -m app.cli ai conversation show 2312 --tail 2 --json
python scripts\verify_tool_policy_logging.py --agent-id 59 --user-id 1 --message "查一下大模型排行榜 2026  水平排行！"
```

Browser path:

```text
Open http://localhost:5666/admin/ai/conversations
Open conversation 2312 from the admin conversation table
Verify runtime diagnostics and message flow in the detail drawer
Capture screenshot to playwright-2312-llm-ranking-detail.png
Open conversation 2314 from the admin conversation table
Verify the latest same-code resmoke diagnostics and message flow in the detail
drawer
```

## CLI Diagnostics Snapshot

Historical conversation `2311` remains the bad-output anchor:

```json
{
  "conversation_id": 2311,
  "turn_outcome": "success",
  "termination_reason": "completed",
  "final_output_source": "recovery_evidence",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "fetched_urls": [
    "https://artificialanalysis.ai/leaderboards/models"
  ],
  "rejected_urls": [
    "https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"
  ],
  "answer_source": "fetched_body",
  "web_research_failure_kind": null,
  "web_research_relevance_profile": "llm_leaderboard",
  "web_research_relevance_rejection_count": 1
}
```

Fresh real-dialogue smoke `2312`:

```json
{
  "conversation_id": 2312,
  "turn_outcome": "success",
  "termination_reason": "completed",
  "final_output_source": "recovery_evidence",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "fetched_urls": [
    "https://artificialanalysis.ai/leaderboards/models"
  ],
  "rejected_urls": [
    "https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"
  ],
  "answer_source": "fetched_body",
  "web_research_failure_kind": null,
  "web_research_relevance_profile": "llm_leaderboard",
  "web_research_relevance_rejection_count": 1
}
```

Additional same-code real-dialogue resmoke `2314`:

```json
{
  "conversation_id": 2314,
  "turn_outcome": "success",
  "termination_reason": "completed",
  "final_output_source": "recovery_evidence",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "fetched_urls": [
    "https://artificialanalysis.ai/leaderboards/models"
  ],
  "rejected_urls": [
    "https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"
  ],
  "answer_source": "fetched_body",
  "web_research_failure_kind": null,
  "web_research_relevance_profile": "llm_leaderboard",
  "web_research_relevance_rejection_count": 1
}
```

Visible answer excerpt from `2312`:

```text
基于已抓取的Artificial Analysis等可核实来源，可整理为 2026 大模型能力排行参考：
1. GPT-5.5 (xhigh/high)
2. Claude Opus 4.7 (max)
3. Gemini 3.1 Pro Preview
补充维度：
- 输出速度
- 延迟
- 价格
- 上下文窗口
来源：Artificial Analysis。
```

## Playwright Evidence

The admin conversation detail drawer for `2312` displayed:

- provider event `evidence_status=completed`;
- provider event `answer_source=fetched_body`;
- `web_research_relevance_profile=llm_leaderboard`;
- fetched URL `https://artificialanalysis.ai/leaderboards/models`;
- rejected Baijiahao URL retained in diagnostics;
- assistant message content headed `2026 大模型能力排行参考`;
- no raw English source description or orphan numeric column as the final answer.

The admin conversation detail drawer for latest resmoke `2314` was also opened
in Playwright and displayed:

- provider event `evidence_status=completed`;
- provider event `answer_source=fetched_body`;
- intent plan `web_research completed`;
- assistant message content headed `2026 大模型能力排行参考`;
- Artificial Analysis cited as the accepted source;
- no raw English source description or orphan numeric column as the final
  answer.

`browser_console_messages onlyErrors=true` returned no errors during the final
2312 and 2314 drawer checks.

## Judge

Status: `pass`

Checklist:

- [x] Historical 2311 was inspected and remains recorded as the raw-output
      failure anchor.
- [x] Fresh 2312 real-dialogue smoke completed the same prompt.
- [x] Fresh 2314 same-code resmoke completed the same prompt.
- [x] `fetched_urls` contains Artificial Analysis.
- [x] `answer_source=fetched_body` and `final_output_source=recovery_evidence`.
- [x] Visible answer is Chinese and contains named frontier models.
- [x] Raw English page description is not used as the final answer.
- [x] Orphan numeric fragments are not used as the final answer.
- [x] Baijiahao remains rejected evidence, not a citation.

Residual note:

The `2312` smoke accepted Artificial Analysis and rejected the noisy Baijiahao
source. LMArena was present as a candidate seed, but it was not part of the
accepted `fetched_urls` for this run. This is acceptable for this answer-quality
bug because the renderer fix is specifically proven on completed authoritative
fetched body evidence from Artificial Analysis.
