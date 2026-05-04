# Smoke / Replay Report (Superseded For Final Acceptance)

> 2026-05-05 update: this 2284 run is retained as historical evidence that the
> platform-owned builtin search/fetch chain executes. It is **not** final
> acceptance for BUG-2026-05-05-2285 because the later 2285 report proved that
> fetched-body success can still be irrelevant. Final acceptance moved to
> `smoke-runs/2026-05-05-webresearch-2285-relevance/report.md`, where
> low-relevance evidence is rejected and the UI/CLI show partial/error instead
> of completed/success.

Scenario ID: `WEBRESEARCH-2026-LLM-RANKING`
Test type: smoke/replay
Date: 2026-05-05
Runner: Codex main auditor
Environment: local backend, branch `codex/admin-account-ai-availability`
Provider / model: platform WebResearchRuntime default path; builtin `web_search`
  public Baidu backend plus builtin `fetch_url`; no hosted/native search selected
Conversation ID: 2284
Replay fixture: none; real AgentChatService smoke
Fixture hash: n/a
Smoke evidence status: `pass`

## Prompt

```text
查一下大模型排行榜 2026 水平排行！
```

## Required Capabilities

- Intent classification produces required `web_research`.
- Default search provider is builtin `web_search` unless an explicitly enabled
  optional provider is recorded with capability/config/smoke evidence.
- Default fetch provider is builtin `fetch_url`.
- Runtime controls fetch after search candidates exist.
- Final answer is synthesized or recovered from normalized WebResearch
  evidence, not raw search snippets or provider preamble text.

## Expected Observable Outcome

- `web_research_pipeline_id` is present.
- `search_provider` is present and is `builtin:web_search` for the default path.
- `fetch_provider` is present and is `builtin:fetch_url` for the default path.
- `candidate_urls` contains at least one source URL.
- `fetched_urls` contains at least one fetched page URL.
- `evidence_status` is `completed` or explicitly `partial` with a typed fetch
  failure; it must not be search-only success for this prompt.
- `evidence_quality` is `body` or `summary`; raw snippet-only evidence is fail.
- `answer_source` is `fetched_body` or `fetched_summary`; the enclosing
  `final_output_source` is `synthesis` or `recovery_evidence`.
- Final answer cites or names sources in a way traceable to fetched evidence.
- Ordinary `openai_compatible` default path does not set
  `_runtime_hosted_web_search_required=True`.

## Command / Run Log

Record the exact command or UI path used:

```text
cd backend
python scripts/verify_tool_policy_logging.py --agent-id 59 --user-id 1 --message "查一下大模型排行榜 2026  水平排行！"
python -m app.cli ai conversation show 2284 --tail 4 --diagnostics-only --json
```

Attach sanitized raw output or log excerpt:

```text
Real smoke run:
- conversation_id=2284
- intent metadata:
  web_research_runtime=platform
  search_provider=builtin_web_search
  fetch_provider=builtin_fetch_url
- web_search public attempt:
  backend=public:baidu
  status=success
  result_count=5
- chat completed:
  conversation=2284
  duration=3911ms

CLI diagnostics for 2284:
- turn_outcome=success
- termination_reason=completed
- final_output_source=recovery_evidence
- web_research_pipeline_id=web-research-1
- search_provider=builtin:web_search
- fetch_provider=builtin:fetch_url
- evidence_status=completed
- fetched_urls=["https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"]
- evidence_quality=body
- answer_source=fetched_body
- web_research_failure_kind=null
- web_research_provider_disable_reason=optional_provider_skipped:builtin_default

Related diagnostics also run on 2026-05-05:
- cd backend; python -m app.cli ai conversation show 2281 --tail 1 --diagnostics-only --json
- cd backend; python -m app.cli ai conversation show 2282 --tail 4 --diagnostics-only --json
- cd backend; python -m app.cli ai smoke --agent-id 59 --json
```

Required log evidence:

- The recorded run must include the canonical WebResearch diagnostics snapshot
  below, copied from runtime/read-model/CLI output.
- If using replay, include the fixture path and SHA-256 hash in this report.
- Do not mark the judge as pass when `fetched_urls` is empty for this prompt.
- Do not mark the judge as pass when `answer_source` is raw search snippets or
  provider preamble text.

## Diagnostics Snapshot

```json
{
  "conversation_id": 2284,
  "web_research_pipeline_id": "web-research-1",
  "search_provider": "builtin:web_search",
  "fetch_provider": "builtin:fetch_url",
  "evidence_status": "completed",
  "candidate_url_count": 5,
  "candidate_urls": [
    "http://www.baidu.com/link?url=ILFIYVIR-rBDjNPTnElToHOO_olMxxKN27C9t6XZqAIBuzH1_rC4itOzd0uQZ3VCcTVUep0R2UwDUAzxaC_YtWgLNCKOhNyr2QucMekhdnC"
  ],
  "fetched_urls": [
    "https://baijiahao.baidu.com/s?id=1860091565873698107&wfr=spider&for=pc"
  ],
  "evidence_quality": "body",
  "answer_source": "fetched_body",
  "final_output_source": "recovery_evidence",
  "optional_provider_skip_reason": "optional_provider_skipped:builtin_default",
  "hosted_search_required_default": false
}
```

## Judge

Status: `pass`

Pass/fail checklist:

- [x] Search provider was selected by platform WebResearch runtime.
- [x] Fetch provider ran after candidate URL selection.
- [x] Fetched evidence was normalized before answer/recovery.
- [x] Final answer did not rely on raw snippets alone.
- [x] Hosted/native provider search was absent by default or explicitly
      documented as opt-in.
- [x] No page runtime/current DOM fields were used.

Notes:

```text
This run exposed and then verified the final read-model projection fix:
canonical WebResearch evidence stored under turn_flow evidence now wins over
stale legacy top-level partial fields. Conversation 2283 was re-queried after
the fix and projects completed evidence; conversation 2284 is the fresh
real-dialogue smoke run used for final acceptance.
```
