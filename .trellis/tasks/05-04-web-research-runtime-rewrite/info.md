# Architecture Notes

## Target Shape

```text
IntentPlan(web_research)
  -> WebResearchRuntime
       -> SearchProviderRouter
            -> BuiltinWebSearchProvider (default)
            -> OpenAIHostedSearchProvider (optional, explicit official/provider-smoked only)
            -> Future Gemini/Claude/Mistral providers (optional)
       -> FetchProviderRouter
            -> BuiltinFetchUrlProvider (default)
       -> QueryRelevanceGate
            -> accepts only query-relevant fetched evidence
            -> rejects/skips low-relevance or blocked sources
       -> EvidenceNormalizer
            -> WebResearchEvidence
       -> AnswerEvidenceBridge
            -> normal synthesis prompt context
            -> recovery_evidence fallback
       -> WebResearchDiagnostics
            -> TurnRecord / turn_ledger / CLI / read models
```

The LLM may synthesize the final answer from evidence, but it must not decide whether the platform should search or fetch once a `web_research` intent is required.

## Canonical Evidence Schema Draft

```python
@dataclass(frozen=True)
class WebResearchEvidence:
    query: str
    status: Literal["completed", "partial", "failed"]
    search_provider: str
    fetch_provider: str
    search_results: list[SearchEvidenceItem]
    fetched_pages: list[PageEvidence]
    citations: list[CitationEvidence]
    answer_quality: Literal["body", "summary", "snippet", "none"]
    failure_kind: str | None
    diagnostics: dict[str, Any]

@dataclass(frozen=True)
class SearchEvidenceItem:
    title: str
    url: str
    snippet: str
    rank: int
    provider: str
    raw: Mapping[str, Any] | None = None

@dataclass(frozen=True)
class PageEvidence:
    url: str
    status: Literal["completed", "failed", "blocked", "skipped"]
    title: str
    body_text: str
    summary: str
    description: str
    answer_quality: Literal["body", "summary", "none"]
    relevance_status: Literal["accepted", "low_relevance", "not_checked"] | None
    relevance_reason: str | None
    provider: str
    raw: Mapping[str, Any] | None = None
```

The actual implementation may use Pydantic/dataclasses according to existing `app.ai` style, but the fields above are the minimum contract.

## Relevance Acceptance Contract

`search -> fetch` success is necessary but not sufficient. A fetched page is
accepted only after the platform relevance gate verifies it can answer the
requested research target.

For BUG-2026-05-05-2285 the prompt is:

```text
查一下大模型排行榜 2026  水平排行！
```

Pages centered on AI 投毒, GEO manipulation, OpenClaw safety, generic token
usage, or unrelated marketing/security topics must be rejected even when fetch
succeeds. Rejected evidence must remain observable through diagnostics, but it
must not become:

- `fetched_urls`
- citations
- `answer_source=fetched_body`
- `final_output_source=recovery_evidence`
- `tool_evidence_completed`
- completed/success terminal state

## New Ownership Rules

- `app.ai.web_research` or a focused package under `app.ai.web_search` owns provider-neutral orchestration.
- `app.ai.web_search` may keep public facades but should not own provider-native fallback policy.
- `app.ai.engine` consumes WebResearch runtime results; it should not reimplement provider selection or evidence quality.
- `app.ai.adapters.openai_compatible` may expose an optional hosted-search adapter, but it must not inject hosted search by default.
- Read models and CLI consume canonical WebResearch diagnostics and evidence.

## Deletion Targets

Search these first:

- `_runtime_hosted_web_search_required`
- `_runtime_native_web_search_fallback_variant`
- `native_web_search_first:web_research`
- `native_search_preferred`
- `synthetic_builtin_web_search_fallback`
- `native_web_search_builtin_fallback_*`
- `response_has_native_web_search_evidence`
- `hosted_web_search_unavailable`

Delete branches that exist only to make hosted/native search the primary path. Keep adapter parsing code only if it becomes an optional provider adapter with explicit capability gates.

## Provider Policy

### Builtin

- default `SearchProvider`
- always available when `web_search` tool is resolved
- output normalized from current public/native fallback search result format

### Fetch

- default `FetchProvider`
- deterministic after search candidates exist
- may skip only for blocked/unsafe/empty candidates with explicit evidence status

### OpenAI Hosted

- optional `SearchProvider`
- disabled by default for `openai_compatible`
- enabled only when provider config explicitly says hosted search is supported and a smoke/replay artifact exists
- returns the same `WebResearchEvidence`

### Gemini / Claude / Mistral

- future optional providers
- no special orchestration branches
- no per-model policy in TurnExecutor

## Testing Strategy

- Structural:
  - evidence schema serialization;
  - provider capability default values;
  - public facade imports.
- Behavioral:
  - generic web query runs builtin search/fetch by default;
  - search success with candidates triggers fetch without another model turn;
  - OpenAI-compatible provider does not send hosted search payload by default;
  - optional hosted provider output normalizes to the same schema;
  - provider answer synthesis failure after evidence recovers from evidence.
- Smoke/replay:
  - replay or real-dialogue case for the leaderboard prompt:
    `查一下大模型排行榜 2026 水平排行！`
  - accepted-evidence success case: search provider used, fetch provider used, evidence contains fetched page body/citation, final answer source is synthesis or recovery evidence, not raw search snippets.
  - rejection case for BUG-2026-05-05-2285: low-relevance fetched pages are rejected, `fetched_urls=[]`, `answer_source=none`, final output is partial/error, and browser diagnostics do not show completed/success.

## Main Auditor Checklist

- No new page runtime/current DOM fields.
- No LLM/provider-controlled fetch progression.
- No OpenAI-compatible hosted search default enablement.
- No test whose only proof is `mock.called`, `is not None`, or LLM stubbed ideal text.
- No read-model-only repair for new live malformed evidence.
- No native-first policy text left in canonical specs.
- Obsolete native-first tests are deleted/replaced, not merely skipped.
