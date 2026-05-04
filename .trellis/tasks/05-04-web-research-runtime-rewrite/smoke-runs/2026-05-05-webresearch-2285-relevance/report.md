# WebResearch 2285 Relevance Smoke Report

Scenario ID: `WEBRESEARCH-2026-LLM-RANKING-RELEVANCE`
Test type: smoke
Date: 2026-05-05
Runner: Codex main auditor
Environment: local backend/frontend, branch `codex/admin-account-ai-availability`
Provider / model: real AgentChatService path with platform WebResearchRuntime;
builtin `web_search` plus builtin `fetch_url`; hosted/native search skipped by
default
Historical bad conversation: `2285`
Fresh smoke conversation: `2290`
Playwright screenshot:
`smoke-runs/2026-05-05-webresearch-2285-relevance/webresearch-2290-low-relevance-detail-translated.png`
Smoke evidence status: `pass`
GREEN implementation commit:
`6be3a378b808687a5503bd850e07230f1a3eb926`

## Prompt

```text
查一下大模型排行榜 2026  水平排行！
```

## Bug Being Proved Fixed

`BUG-2026-05-05-2285` originally returned an irrelevant article about AI
“投毒”、GEO、OpenClaw/token usage/security and projected it as completed
WebResearch evidence. That must never be counted as success for an LLM
leaderboard query.

## Required Observable Outcome

- Default provider path is platform-owned `builtin:web_search` +
  `builtin:fetch_url`.
- Hosted/native search is not required for an OpenAI-compatible provider.
- Search and fetch may run, but low-relevance fetched pages are rejected.
- Rejected pages do not populate `fetched_urls`, citations, completed evidence,
  or recovery answer text.
- CLI/read-model/turn-flow/browser diagnostics show partial/error/failure, not
  completed/success.
- User-visible answer does not reproduce the irrelevant article body as if it
  answered the leaderboard question.

## Commands / UI Path

```text
cd backend
python -m app.cli ai conversation show 2285 --tail 8 --diagnostics-only --json
python -m app.cli ai conversation show 2290 --tail 8 --diagnostics-only --json
python -m app.cli ai smoke --agent-id 59 --json
```

Browser path:

```text
Open http://localhost:5666/admin/ai/conversations
Open conversation 2290 from the admin conversation table
Verify runtime diagnostics and message flow
Capture full-page screenshot to output/playwright/webresearch-2290-low-relevance-detail.png
```

## CLI Diagnostics Snapshot

Historical conversation `2285` after the fix:

```json
{
  "conversation_id": 2285,
  "turn_outcome": "failed",
  "final_output_source": "partial_output",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "partial",
  "fetched_urls": [],
  "rejected_urls": ["https://www.cnblogs.com/bykj123/p/19608875"],
  "answer_source": "none",
  "web_research_failure_kind": "blocked_url",
  "web_research_relevance_profile": "llm_leaderboard",
  "web_research_relevance_rejection_count": 1,
  "web_research_provider_disable_reason": "optional_provider_skipped:builtin_default"
}
```

Fresh real-dialogue smoke `2290`:

```json
{
  "conversation_id": 2290,
  "turn_outcome": "failed",
  "termination_reason": "low_query_relevance",
  "partial_exit_reason": "low_query_relevance",
  "final_output_source": "partial_output",
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "partial",
  "fetched_urls": [],
  "rejected_urls": ["https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"],
  "answer_source": "none",
  "web_research_failure_kind": "low_query_relevance",
  "web_research_relevance_profile": "llm_leaderboard",
  "web_research_relevance_rejection_count": 1,
  "web_research_provider_disable_reason": "optional_provider_skipped:builtin_default"
}
```

## Playwright Evidence

The admin conversation detail drawer for `2290` displayed:

- `失败归因 = 来源相关性不足` after the frontend i18n key fix;
- `部分返回原因 = low_query_relevance`;
- intent `web_research` status `failed`;
- provider event with `evidence_status=partial` and `answer_source=none`;
- retry event `return_partial` with
  `web_research_evidence_unaccepted=true`;
- assistant message card marked `异常`, not completed/success.

The first browser pass exposed a missing translation key for
`admin.ai.conversation.failureKindOptions.low_query_relevance`; the fix adds
admin/tenant zh-CN/en-US labels for all WebResearch failure kinds introduced by
this relevance gate. After reload, the console contained only Vite debug
messages and no missing i18n warning.

## Judge

Status: `pass`

Checklist:

- [x] Historical 2285 no longer projects the irrelevant evidence as completed.
- [x] Fresh 2290 real-dialogue smoke rejects the low-relevance fetched page.
- [x] `fetched_urls` stays empty when no accepted evidence exists.
- [x] `answer_source=none` and `final_output_source=partial_output`.
- [x] Browser detail shows failure/partial/error, not success/completed.
- [x] Hosted/native search remains default-off for the OpenAI-compatible path.

Residual note:

The top-level conversation row status remains `active/进行中` because that table
field represents conversation lifecycle, not turn evidence success. The detail
diagnostics and message-flow cards now carry the authoritative failed/partial
turn result.

Final command gates:

- Backend full suite: `2950 passed, 4 skipped, 2 warnings`.
- Prompt contracts: passed.
- Ruff check/format for touched backend Python files: passed.
- CLI smoke for agent `59`: `overall_status=green`.
- Frontend `check:type:antd`: passed.
- Prettier check for touched admin/tenant AI locale JSON files: passed.
- Full frontend lint remains blocked by unrelated pre-existing stylelint and
  Prettier issues outside the touched locale JSON files.
