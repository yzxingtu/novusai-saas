# Historical Only

This smoke scaffold is superseded by the 05-05 and 05-08 online-search
retirement work. Do not use it as current acceptance, current smoke
expectation, or evidence to restore WebResearch, `web_search`, or `fetch_url`.

# WebResearch Smoke Scaffold: 2026 LLM Ranking

Prompt:

```text
查一下大模型排行榜 2026 水平排行！
```

Purpose:

- Prove the new platform-owned WebResearch pipeline runs
  `search -> fetch -> evidence -> answer` for a real dialogue or approved replay.
- Prove ordinary `openai_compatible` execution does not require hosted/native
  provider search by default.
- Preserve enough diagnostics that reviewers can verify fetched page evidence
  and final answer source without relying on raw search snippets.

Artifacts to attach in this directory:

- `report-template.md`, copied or completed as the actual run report.
- `fixtures/<fixture-id>.json`, if using an approved replay fixture.
- `fixtures/<fixture-id>.sha256`, if using a replay fixture.
- Optional raw CLI/SSE logs with secrets removed.

This scaffold is not itself a passing smoke run. Milestone acceptance requires
the report to be filled from a real provider run or an approved recorded replay.

Replay approval checklist:

- The fixture must come from a real dialogue run, not a hand-authored ideal LLM
  answer.
- The fixture or log must include canonical WebResearch diagnostics:
  `web_research_pipeline_id`, `search_provider`, `fetch_provider`,
  `candidate_urls`, `fetched_urls`, `evidence_status`, `evidence_quality`, and
  `answer_source`.
- The judge must fail search-only success for this prompt. At least one fetched
  page URL and body or summary evidence is required.
- Ordinary `openai_compatible` default execution must show hosted/native search
  was not required; optional hosted search can pass only when the run records an
  explicit capability/config opt-in plus smoke evidence.
