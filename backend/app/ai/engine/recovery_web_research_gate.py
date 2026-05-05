"""Web research recovery gating helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .recovery_result_normalizer import RecoveryResultNormalizer
from .recovery_tool_result_helpers import (
    _fetch_url_payload_is_accepted_for_web_research,
    extract_fetch_url_candidate_urls,
    latest_successful_tool_result,
    tool_attempted,
    web_search_result_count,
)
from .types import IntentPlan

WEB_RESEARCH_TERMINAL_CONTRACT_KEY = "web_research_terminal_contract"
WEB_RESEARCH_TERMINAL_NO_RESULT = "no_result"
WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE = "search_unavailable"

_WEB_RESEARCH_TERMINAL_CONTRACTS = frozenset(
    {
        WEB_RESEARCH_TERMINAL_NO_RESULT,
        WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE,
    }
)
_TERMINAL_CONTRACT_BY_GATE_REASON = {
    "search_no_results": WEB_RESEARCH_TERMINAL_NO_RESULT,
    "search_no_results_completed": WEB_RESEARCH_TERMINAL_NO_RESULT,
    "search_not_successful": WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE,
}
_WEB_RESEARCH_DIAGNOSTIC_KEYS = (
    "web_research_pipeline_id",
    "search_provider",
    "fetch_provider",
    "evidence_status",
    "candidate_urls",
    "fetched_urls",
    "rejected_urls",
    "evidence_quality",
    "answer_source",
    "web_research_failure_kind",
    "web_research_failure_layer",
    "web_research_relevance_profile",
    "web_research_relevance_rejection_count",
    "web_research_provider_disable_reason",
)
_WEB_RESEARCH_EVIDENCE_CONTAINER_KEYS = (
    "web_research_evidence",
    "web_research",
    "web_research_runtime",
)
_WEB_RESEARCH_DIAGNOSTICS_CONTAINER_KEYS = (
    "web_research_diagnostics",
    "webResearchDiagnostics",
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, Mapping) else {}
    raw_payload = getattr(value, "__dict__", None)
    return dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def _dedupe_text(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = _as_text(value)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping):
        return dict(result)
    raw_payload = getattr(result, "__dict__", None)
    return dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}


def _summary_payload(result: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(result.get("summary_payload"))


def _canonical_answer_source(quality: str | None) -> str:
    if quality == "body":
        return "fetched_body"
    if quality == "summary":
        return "fetched_summary"
    if quality == "snippet":
        return "search_snippet"
    return "none"


def _web_research_failure_layer(kind: str | None) -> str | None:
    if not kind:
        return None
    normalized = kind.strip().lower()
    if normalized.startswith("provider_") or normalized in {
        "search_exception",
        "search_failed",
        "fetch_exception",
        "fetch_failed",
    }:
        return "provider"
    if normalized in {
        "fetch_not_attempted",
        "no_answer_quality_evidence",
        "insufficient_cross_checked_sources",
        "raw_search_only_recovery_finalized",
        "missing_fetch_evidence",
    }:
        return "evidence"
    return "orchestration"


def normalize_web_research_provider_reason(reason: Any) -> str | None:
    """Return operator-safe optional-provider reason text.

    Old incidents stored provider-native wording in generic diagnostics. New
    read models keep the fact, but label it as an optional provider diagnostic
    rather than a live native-first execution path.
    """

    text = _as_text(reason)
    if not text:
        return None
    lowered = text.lower()
    replacements = {
        "native_web_search_first:web_research": (
            "optional_provider_skipped:builtin_default"
        ),
        "native_search_completed": "optional_provider_completed",
        "native_search_preferred": "optional_provider_preferred",
        "hosted_web_search_unavailable:": "optional_provider_unavailable:",
        "native_web_search_builtin_fallback": "optional_provider_builtin_recovery",
        "synthetic_builtin_web_search_fallback": "builtin_web_research_recovery",
    }
    for old, new in replacements.items():
        if lowered.startswith(old):
            return new + text[len(old) :] if old.endswith(":") else new
        if old in lowered:
            return new
    if lowered.startswith("native_"):
        return "optional_provider_" + text[len("native_") :]
    if lowered.startswith("hosted_"):
        return "optional_provider_" + text[len("hosted_") :]
    return text


def _urls_from_search_items(items: Any) -> list[str]:
    urls: list[Any] = []
    for item in _as_list(items):
        payload = _as_dict(item)
        urls.append(payload.get("url"))
    return _dedupe_text(urls)


def _urls_from_pages(pages: Any) -> list[str]:
    urls: list[Any] = []
    for item in _as_list(pages):
        payload = _as_dict(item)
        status = _as_text(payload.get("status")) or "completed"
        if status != "completed":
            continue
        urls.append(payload.get("url"))
    return _dedupe_text(urls)


def _project_from_canonical_evidence(value: Any) -> dict[str, Any]:
    payload = _as_dict(value)
    if not payload:
        return {}
    diagnostics = _as_dict(payload.get("diagnostics"))
    raw_diagnostics = _as_dict(diagnostics.get("raw"))
    pipeline_id = (
        _as_text(diagnostics.get("pipeline_id"))
        or _as_text(payload.get("pipeline_id"))
        or _as_text(raw_diagnostics.get("pipeline_id"))
    )
    search_provider = _as_text(diagnostics.get("search_provider")) or _as_text(
        payload.get("search_provider")
    )
    fetch_provider = _as_text(diagnostics.get("fetch_provider")) or _as_text(
        payload.get("fetch_provider")
    )
    evidence_status = _as_text(diagnostics.get("evidence_status")) or _as_text(
        payload.get("status")
    )
    candidate_urls = _dedupe_text(
        _as_list(diagnostics.get("candidate_urls"))
    ) or _urls_from_search_items(payload.get("search_results"))
    fetched_urls = _dedupe_text(
        _as_list(diagnostics.get("fetched_urls"))
    ) or _urls_from_pages(payload.get("fetched_pages"))
    rejected_urls = _dedupe_text(_as_list(diagnostics.get("rejected_urls")))
    evidence_quality = _as_text(diagnostics.get("evidence_quality")) or _as_text(
        payload.get("answer_quality")
    )
    answer_source = _as_text(diagnostics.get("answer_source")) or (
        _canonical_answer_source(evidence_quality)
    )
    failure_kind = _as_text(diagnostics.get("failure_kind")) or _as_text(
        payload.get("failure_kind")
    )
    provider_disable_reason = normalize_web_research_provider_reason(
        diagnostics.get("provider_disable_reason")
        or raw_diagnostics.get("provider_disable_reason")
    )
    projected = {
        "web_research_pipeline_id": pipeline_id,
        "search_provider": search_provider,
        "fetch_provider": fetch_provider,
        "evidence_status": evidence_status,
        "candidate_urls": candidate_urls,
        "fetched_urls": fetched_urls,
        "rejected_urls": rejected_urls,
        "evidence_quality": evidence_quality,
        "answer_source": answer_source,
        "web_research_failure_kind": failure_kind,
        "web_research_failure_layer": _web_research_failure_layer(failure_kind),
        "web_research_relevance_profile": _as_text(
            diagnostics.get("relevance_profile")
        ),
        "web_research_relevance_rejection_count": diagnostics.get(
            "relevance_rejection_count"
        ),
        "web_research_provider_disable_reason": provider_disable_reason,
    }
    return {key: value for key, value in projected.items() if value not in (None, [])}


def _project_from_existing_fields(
    source: Mapping[str, Any],
    *,
    allow_generic_failure_kind: bool = False,
) -> dict[str, Any]:
    payload = _as_dict(source)
    projected = {
        "web_research_pipeline_id": _as_text(
            payload.get("web_research_pipeline_id") or payload.get("pipeline_id")
        ),
        "search_provider": _as_text(payload.get("search_provider")),
        "fetch_provider": _as_text(payload.get("fetch_provider")),
        "evidence_status": _as_text(payload.get("evidence_status")),
        "candidate_urls": _dedupe_text(_as_list(payload.get("candidate_urls"))),
        "fetched_urls": _dedupe_text(_as_list(payload.get("fetched_urls"))),
        "rejected_urls": _dedupe_text(_as_list(payload.get("rejected_urls"))),
        "evidence_quality": _as_text(payload.get("evidence_quality")),
        "answer_source": _as_text(payload.get("answer_source")),
        "web_research_failure_kind": _as_text(
            payload.get("web_research_failure_kind")
            or payload.get("web_research_runtime_failure_kind")
            or (payload.get("failure_kind") if allow_generic_failure_kind else None)
        ),
        "web_research_provider_disable_reason": (
            normalize_web_research_provider_reason(
                payload.get("web_research_provider_disable_reason")
                or payload.get("provider_disable_reason")
            )
        ),
        "web_research_relevance_profile": _as_text(
            payload.get("web_research_relevance_profile")
            or payload.get("relevance_profile")
        ),
        "web_research_relevance_rejection_count": payload.get(
            "web_research_relevance_rejection_count",
            payload.get("relevance_rejection_count"),
        ),
    }
    if projected["web_research_failure_kind"]:
        projected["web_research_failure_layer"] = _web_research_failure_layer(
            projected["web_research_failure_kind"]
        )
    return {key: value for key, value in projected.items() if value not in (None, [])}


def _iter_metadata_projection_payloads(
    value: Any,
    *,
    _seen: set[int] | None = None,
) -> list[dict[str, Any]]:
    payload = _as_dict(value)
    if not payload:
        return []

    seen = _seen or set()
    marker = id(payload)
    if marker in seen:
        return []
    seen.add(marker)

    payloads = [payload]
    for key in (
        "metadata",
        "orchestration",
        "turn_diagnostics",
        "context_diagnostics",
        "last_run_summary",
    ):
        nested = _as_dict(payload.get(key))
        if nested:
            payloads.extend(_iter_metadata_projection_payloads(nested, _seen=seen))
    return payloads


def _iter_nested_projection_payloads(
    value: Any,
    *,
    max_depth: int = 8,
    _seen: set[int] | None = None,
) -> list[dict[str, Any]]:
    if max_depth < 0:
        return []

    seen = _seen or set()
    payload = _as_dict(value)
    if payload:
        marker = id(payload)
        if marker in seen:
            return []
        seen.add(marker)

        payloads = [payload]
        for child in payload.values():
            if isinstance(child, (Mapping, list, tuple)) or hasattr(child, "to_dict"):
                payloads.extend(
                    _iter_nested_projection_payloads(
                        child,
                        max_depth=max_depth - 1,
                        _seen=seen,
                    )
                )
        return payloads

    payloads: list[dict[str, Any]] = []
    for item in _as_list(value):
        payloads.extend(
            _iter_nested_projection_payloads(
                item,
                max_depth=max_depth - 1,
                _seen=seen,
            )
        )
    return payloads


def _find_canonical_web_research_projection(
    *sources: Mapping[str, Any],
) -> dict[str, Any]:
    metadata_payloads: list[dict[str, Any]] = []
    evidence_payloads: list[dict[str, Any]] = []
    for source in sources:
        payload = _as_dict(source)
        if not payload:
            continue
        metadata_payloads.extend(_iter_metadata_projection_payloads(payload))
        evidence_payloads.extend(_iter_nested_projection_payloads(payload))

    for payload in evidence_payloads:
        for key in _WEB_RESEARCH_EVIDENCE_CONTAINER_KEYS:
            projected = _project_from_canonical_evidence(payload.get(key))
            if projected:
                return projected

    for payload in metadata_payloads:
        for key in _WEB_RESEARCH_DIAGNOSTICS_CONTAINER_KEYS:
            projected = _project_from_existing_fields(
                _as_dict(payload.get(key)),
                allow_generic_failure_kind=True,
            )
            if projected:
                return projected

    for payload in metadata_payloads:
        direct = _project_from_existing_fields(payload)
        if direct:
            return direct

    return {}


def _urls_from_intent_metadata(intent_plan: Any) -> list[str]:
    urls: list[Any] = []
    for item in _as_list(intent_plan):
        intent = _as_dict(item)
        if _as_text(intent.get("family")) != "web_research":
            continue
        metadata = _as_dict(intent.get("metadata"))
        urls.extend(_as_list(metadata.get("fetch_url_candidate_urls")))
    return _dedupe_text(urls)


def _fetch_url_from_payload(payload: dict[str, Any]) -> str | None:
    summary = _summary_payload(payload)
    return (
        _as_text(summary.get("final_url"))
        or _as_text(summary.get("url"))
        or _as_text(summary.get("requested_url"))
        or _as_text(payload.get("result_link"))
    )


def _fetch_answer_quality(payload: dict[str, Any]) -> str:
    summary = _summary_payload(payload)
    if summary.get("ok") is False:
        return "none"
    output = _as_text(payload.get("output")) or ""
    summary_text = (
        _as_text(summary.get("summary")) or _as_text(payload.get("summary")) or ""
    )
    body_lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
        and not line.startswith(("Content from ", "Redirected from: ", "Title: "))
    ]
    if body_lines:
        return "body"
    if summary_text and not summary_text.lower().startswith("fetched http"):
        return "summary"
    return "none"


def _fetch_rejected_urls(summary_payload: dict[str, Any]) -> list[str]:
    urls: list[Any] = []
    urls.extend(_as_list(summary_payload.get("rejected_urls")))
    evidence = _as_dict(summary_payload.get("web_research_evidence"))
    diagnostics = _as_dict(evidence.get("diagnostics"))
    urls.extend(_as_list(diagnostics.get("rejected_urls")))
    for raw_page in _as_list(evidence.get("fetched_pages")):
        page = _as_dict(raw_page)
        if (
            page.get("failure_kind") == "low_query_relevance"
            or page.get("relevance_status") == "low_relevance"
        ):
            urls.append(page.get("url"))
    return _dedupe_text(urls)


def _fetch_relevance_profile(summary_payload: dict[str, Any]) -> str | None:
    evidence = _as_dict(summary_payload.get("web_research_evidence"))
    diagnostics = _as_dict(evidence.get("diagnostics"))
    for candidate in (
        summary_payload.get("relevance_profile"),
        diagnostics.get("relevance_profile"),
    ):
        text = _as_text(candidate)
        if text:
            return text
    for raw_page in _as_list(evidence.get("fetched_pages")):
        text = _as_text(_as_dict(raw_page).get("relevance_profile"))
        if text:
            return text
    return None


def _fetch_unaccepted_failure_kind(summary_payload: dict[str, Any]) -> str:
    evidence = _as_dict(summary_payload.get("web_research_evidence"))
    diagnostics = _as_dict(evidence.get("diagnostics"))
    for candidate in (
        summary_payload.get("relevance_reason"),
        summary_payload.get("failure_kind"),
        diagnostics.get("failure_kind"),
        evidence.get("failure_kind"),
    ):
        text = _as_text(candidate)
        if text:
            return text
    for raw_page in _as_list(evidence.get("fetched_pages")):
        page = _as_dict(raw_page)
        for candidate in (page.get("relevance_reason"), page.get("failure_kind")):
            text = _as_text(candidate)
            if text:
                return text
        if page.get("relevance_status") == "low_relevance":
            return "low_query_relevance"
    if _fetch_rejected_urls(summary_payload):
        return "low_query_relevance"
    return "no_answer_quality_evidence"


def _project_from_tool_results(
    *,
    tool_results: list[Any] | None,
    intent_plan: Any = None,
) -> dict[str, Any]:
    candidate_urls = _urls_from_intent_metadata(intent_plan)
    fetched_urls: list[str] = []
    rejected_urls: list[str] = []
    search_provider: str | None = None
    fetch_provider: str | None = None
    search_status: str | None = None
    search_failure: str | None = None
    fetch_failure: str | None = None
    relevance_profile: str | None = None
    evidence_quality = "none"
    saw_web_search = False
    saw_fetch = False

    for raw_result in tool_results or []:
        result = _tool_result_payload(raw_result)
        tool_name = _as_text(result.get("name"))
        if tool_name == "web_search":
            saw_web_search = True
            summary = _summary_payload(result)
            candidate_urls = candidate_urls or _urls_from_search_items(
                summary.get("items")
            )
            search_provider = (
                _as_text(summary.get("provider"))
                or _as_text(summary.get("selected_backend"))
                or "builtin-web-search"
            )
            search_status = _as_text(summary.get("status"))
            if not bool(result.get("success")):
                search_failure = (
                    _as_text(result.get("error_type"))
                    or _as_text(summary.get("failure_reason"))
                    or "search_failed"
                )
            elif search_status in {"failed", "upstream_error", "timeout"}:
                search_failure = (
                    _as_text(summary.get("failure_reason"))
                    or _as_text(summary.get("native_failure_kind"))
                    or "search_failed"
                )
        elif tool_name == "fetch_url":
            saw_fetch = True
            fetch_provider = "builtin-fetch-url"
            summary = _summary_payload(result)
            if bool(result.get("success")) and summary.get("ok") is not False:
                if not _fetch_url_payload_is_accepted_for_web_research(summary):
                    fetch_failure = _fetch_unaccepted_failure_kind(summary)
                    rejected_urls = _dedupe_text(
                        [*rejected_urls, *_fetch_rejected_urls(summary)]
                    )
                    relevance_profile = relevance_profile or _fetch_relevance_profile(
                        summary
                    )
                    continue
                url = _fetch_url_from_payload(result)
                if url and url not in fetched_urls:
                    fetched_urls.append(url)
                quality = _fetch_answer_quality(result)
                if quality == "body" or (
                    quality == "summary" and evidence_quality != "body"
                ):
                    evidence_quality = quality
            else:
                fetch_failure = (
                    _as_text(result.get("error_type"))
                    or _as_text(summary.get("error_type"))
                    or "fetch_failed"
                )

    if not any([saw_web_search, saw_fetch, candidate_urls, fetched_urls]):
        return {}

    if fetched_urls and evidence_quality != "none":
        evidence_status = "completed"
        failure_kind = None
    elif search_failure and not candidate_urls:
        evidence_status = "failed"
        failure_kind = search_failure
    elif fetch_failure:
        evidence_status = "partial"
        failure_kind = fetch_failure
    elif candidate_urls and not fetched_urls:
        evidence_status = "partial"
        failure_kind = "fetch_not_attempted"
    elif saw_fetch:
        evidence_status = "partial"
        failure_kind = "no_answer_quality_evidence"
    else:
        evidence_status = "failed"
        failure_kind = "search_failed"

    projected = {
        "search_provider": search_provider
        or ("builtin-web-search" if saw_web_search else None),
        "fetch_provider": fetch_provider
        or ("builtin-fetch-url" if saw_fetch else None),
        "evidence_status": evidence_status,
        "candidate_urls": candidate_urls,
        "fetched_urls": fetched_urls,
        "evidence_quality": evidence_quality,
        "answer_source": _canonical_answer_source(evidence_quality),
        "web_research_failure_kind": failure_kind,
        "web_research_failure_layer": _web_research_failure_layer(failure_kind),
        "rejected_urls": rejected_urls,
        "web_research_relevance_profile": relevance_profile,
        "web_research_relevance_rejection_count": len(rejected_urls),
    }
    return {key: value for key, value in projected.items() if value not in (None, [])}


def project_canonical_web_research_diagnostics(
    *,
    diagnostics_payload: Mapping[str, Any] | None = None,
    turn_record_payload: Mapping[str, Any] | None = None,
    intent_plan: Any = None,
    tool_results: list[Any] | None = None,
) -> dict[str, Any]:
    """Project canonical WebResearch evidence into stable diagnostic fields."""

    diagnostics = _as_dict(diagnostics_payload)
    turn_record = _as_dict(turn_record_payload)
    turn_metadata = _as_dict(turn_record.get("metadata"))
    turn_diagnostics = _as_dict(turn_metadata.get("turn_diagnostics"))

    projected = _find_canonical_web_research_projection(
        diagnostics,
        turn_record,
        turn_diagnostics,
    )
    if not projected:
        projected = _project_from_tool_results(
            tool_results=tool_results,
            intent_plan=(
                intent_plan
                if intent_plan is not None
                else diagnostics.get("intent_plan") or turn_record.get("intent_plan")
            ),
        )

    evidence_completed = _as_text(projected.get("evidence_status")) == "completed"
    if evidence_completed:
        projected["web_research_failure_kind"] = None
        projected["web_research_failure_layer"] = None

    provider_reason = projected.get("web_research_provider_disable_reason")
    if not provider_reason and not evidence_completed:
        for source in (diagnostics, turn_record, turn_diagnostics):
            for candidate_key in (
                "provider_disable_reason",
                "web_research_provider_disable_reason",
                "web_search_skip_native_reason",
                "auto_fetch_gate_reason",
            ):
                provider_reason = normalize_web_research_provider_reason(
                    source.get(candidate_key)
                )
                if provider_reason:
                    break
            if provider_reason:
                projected["web_research_provider_disable_reason"] = provider_reason
                break

    if projected.get("web_research_failure_kind") and not projected.get(
        "web_research_failure_layer"
    ):
        projected["web_research_failure_layer"] = _web_research_failure_layer(
            projected.get("web_research_failure_kind")
        )

    if projected:
        web_research_diagnostics = {
            key: projected.get(key)
            for key in _WEB_RESEARCH_DIAGNOSTIC_KEYS
            if projected.get(key) not in (None, [])
        }
        projected["web_research_diagnostics"] = web_research_diagnostics
    return projected


class RecoveryWebResearchGate:
    """Recovery helpers for web_research intents."""

    @staticmethod
    def normalized_url_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            url = str(item or "").strip()
            if url and url not in normalized:
                normalized.append(url)
        return normalized

    @staticmethod
    def extract_fetch_url_candidate_urls(
        tool_results: list[ToolResult] | None,
    ) -> list[str]:
        return extract_fetch_url_candidate_urls(tool_results)

    @staticmethod
    def sync_fetch_url_candidates(
        intent: IntentPlan,
        tool_results: list[ToolResult] | None = None,
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return
        candidate_urls = RecoveryWebResearchGate.extract_fetch_url_candidate_urls(
            tool_results
        )
        if not candidate_urls:
            return
        metadata = dict(intent.metadata or {})
        existing_urls = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        merged_urls = list(existing_urls)
        for url in candidate_urls:
            if url not in merged_urls:
                merged_urls.append(url)
        metadata["fetch_url_candidate_urls"] = merged_urls
        metadata["fetch_url_attempted_urls"] = (
            RecoveryWebResearchGate.normalized_url_list(
                metadata.get("fetch_url_attempted_urls")
            )
        )
        metadata["fetch_url_blocked_urls"] = (
            RecoveryWebResearchGate.normalized_url_list(
                metadata.get("fetch_url_blocked_urls")
            )
        )
        intent.metadata = metadata

    @staticmethod
    def latest_successful_tool_result(
        tool_name: str,
        tool_results: list[ToolResult] | None = None,
    ) -> ToolResult | None:
        return latest_successful_tool_result(tool_name, tool_results)

    @staticmethod
    def web_search_result_count(
        tool_results: list[ToolResult] | None = None,
    ) -> int | None:
        return web_search_result_count(tool_results)

    @staticmethod
    def set_auto_fetch_gate_reason(intent: IntentPlan, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        normalized_reason = str(reason or "").strip()
        metadata["auto_fetch_gate_reason"] = normalized_reason or None
        if metadata["auto_fetch_gate_reason"] is None:
            metadata.pop("auto_fetch_gate_reason", None)
        RecoveryWebResearchGate.sync_terminal_contract(metadata, normalized_reason)
        intent.metadata = metadata

    @staticmethod
    def clear_requires_fetch_url(intent: IntentPlan, *, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        metadata.pop("requires_fetch_url", None)
        normalized_reason = str(reason or "").strip()
        metadata["auto_fetch_gate_reason"] = normalized_reason or None
        RecoveryWebResearchGate.sync_terminal_contract(metadata, normalized_reason)
        intent.metadata = metadata

    @staticmethod
    def terminal_contract_for_gate_reason(reason: str) -> str | None:
        return _TERMINAL_CONTRACT_BY_GATE_REASON.get(str(reason or "").strip())

    @staticmethod
    def sync_terminal_contract(metadata: dict[str, Any], reason: str) -> None:
        contract = RecoveryWebResearchGate.terminal_contract_for_gate_reason(reason)
        if contract:
            metadata[WEB_RESEARCH_TERMINAL_CONTRACT_KEY] = contract
        else:
            metadata.pop(WEB_RESEARCH_TERMINAL_CONTRACT_KEY, None)

    @staticmethod
    def terminal_contract(intent: IntentPlan) -> str:
        metadata = dict(intent.metadata or {})
        explicit = str(metadata.get(WEB_RESEARCH_TERMINAL_CONTRACT_KEY) or "").strip()
        if explicit in _WEB_RESEARCH_TERMINAL_CONTRACTS:
            return explicit
        reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
        return RecoveryWebResearchGate.terminal_contract_for_gate_reason(reason) or ""

    @staticmethod
    def is_terminal_without_verified_fetch_answer(intent: IntentPlan) -> bool:
        if str(intent.family or "").strip() != "web_research":
            return False
        return (
            RecoveryWebResearchGate.terminal_contract(intent)
            in _WEB_RESEARCH_TERMINAL_CONTRACTS
        )

    @staticmethod
    def web_research_no_result_output(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryResultNormalizer._should_prefix_result_with_label(label):
            return _("关于{label}，我暂时没有找到可直接核实的搜索结果。").format(
                label=label
            )
        return _("我暂时没有找到可直接核实的搜索结果。")

    @staticmethod
    def is_completed_web_research_no_result(
        intent: IntentPlan,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
        successful_tool_names: set[str],
    ) -> bool:
        if str(intent.family or "").strip() != "web_research":
            return False
        if "web_search" not in successful_tool_names:
            return False
        candidate_urls = RecoveryWebResearchGate.normalized_url_list(
            (intent.metadata or {}).get("fetch_url_candidate_urls")
        )
        if candidate_urls:
            return False
        if tool_attempted(messages, "fetch_url", tool_results=tool_results):
            return False
        result_count = RecoveryWebResearchGate.web_search_result_count(tool_results)
        if result_count is None:
            return True
        return result_count <= 0

    @staticmethod
    def force_fetch_url_after_search(
        intent: IntentPlan,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
        successful_tool_names: set[str],
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return

        RecoveryWebResearchGate.sync_fetch_url_candidates(intent, tool_results)
        metadata = dict(intent.metadata or {})
        candidate_urls = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        attempted_urls = set(
            RecoveryWebResearchGate.normalized_url_list(
                metadata.get("fetch_url_attempted_urls")
            )
        )
        remaining_candidate_urls = [
            url for url in candidate_urls if url not in attempted_urls
        ]
        result_count = RecoveryWebResearchGate.web_search_result_count(tool_results)
        candidate_tool_names = {
            str(name or "").strip()
            for name in (
                list(intent.allowed_tool_names or [])
                + list(intent.preferred_tool_names or [])
                + list(intent.completion_signals or [])
            )
            if str(name or "").strip()
        }
        if (
            "fetch_url" not in candidate_tool_names
            or "web_search" not in candidate_tool_names
        ):
            return
        if "web_search" not in successful_tool_names:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="search_not_successful",
            )
            return
        if result_count is not None and result_count <= 0:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="search_no_results",
            )
            return
        if not candidate_urls:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="no_candidate_urls",
            )
            return
        if tool_attempted(messages, "fetch_url", tool_results=tool_results):
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="fetch_already_attempted",
            )
            return
        if not remaining_candidate_urls:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="candidate_urls_exhausted",
            )
            return

        intent.allowed_tool_names = ["fetch_url"]
        intent.preferred_tool_names = ["fetch_url"]
        intent.completion_signals = ["fetch_url"]
        intent.metadata["requires_fetch_url"] = True
        intent.metadata["auto_fetch_gate_reason"] = "candidate_urls_ready"
        intent.metadata.pop(WEB_RESEARCH_TERMINAL_CONTRACT_KEY, None)


__all__ = [
    "WEB_RESEARCH_TERMINAL_CONTRACT_KEY",
    "WEB_RESEARCH_TERMINAL_NO_RESULT",
    "WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE",
    "RecoveryWebResearchGate",
    "normalize_web_research_provider_reason",
    "project_canonical_web_research_diagnostics",
]
