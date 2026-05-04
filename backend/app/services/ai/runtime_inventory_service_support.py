"""
Runtime inventory payload shaping helpers.
运行时能力清单输出整形辅助。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.ai.runtime import AIRuntimeInventoryService
from app.ai.skills.resolution_contracts import SkillResolveIssue, issue_matches_skill
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.models.ai.agent import Agent
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider
from app.schemas.ai.invalid_ai_runtime_input import (
    filter_invalid_ai_runtime_references,
    filter_invalid_ai_runtime_tools,
)


def _stable_unique_texts(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _inventory_selected_tool_names(payload: dict[str, Any]) -> list[str]:
    names: list[Any] = []
    for source in payload.get("sources") or []:
        if not isinstance(source, dict):
            continue
        metadata = source.get("metadata")
        if not isinstance(metadata, dict):
            continue
        names.extend(list(metadata.get("inventory_selected_tool_names") or []))
    return _stable_unique_texts(filter_invalid_ai_runtime_references(names))


def _inventory_selected_skill_names(payload: dict[str, Any]) -> list[str]:
    names: list[Any] = []
    for source in payload.get("sources") or []:
        if not isinstance(source, dict):
            continue
        metadata = source.get("metadata")
        if not isinstance(metadata, dict):
            continue
        names.extend(list(metadata.get("inventory_selected_skill_names") or []))
    return _stable_unique_texts(filter_invalid_ai_runtime_references(names))


def _web_research_pair_from_inventory(payload: dict[str, Any]) -> bool:
    tool_names = set(_inventory_selected_tool_names(payload))
    return {"web_search", "fetch_url"}.issubset(tool_names)


def _project_inventory_web_research_availability(payload: dict[str, Any]) -> bool:
    if not _web_research_pair_from_inventory(payload):
        return False

    web_research_items = [
        dict(item)
        for item in payload.get("web_research") or []
        if isinstance(item, dict)
    ]
    if not web_research_items:
        web_research_items = [
            {
                "name": "web_research",
                "kind": "execution_tool",
                "source": "tool_registry",
            }
        ]

    projected_items: list[dict[str, Any]] = []
    projected = False
    for item in web_research_items:
        if str(item.get("name") or "").strip() != "web_research":
            projected_items.append(item)
            continue
        metadata = dict(item.get("metadata") or {})
        metadata.update(
            {
                "has_web_search": True,
                "has_fetch_url": True,
                "availability_basis": "inventory_selected_tools",
            }
        )
        item.update(
            {
                "status": "available",
                "reason": None,
                "metadata": metadata,
            }
        )
        projected_items.append(item)
        projected = True

    if not projected:
        projected_items.append(
            {
                "name": "web_research",
                "kind": "execution_tool",
                "status": "available",
                "reason": None,
                "metadata": {
                    "has_web_search": True,
                    "has_fetch_url": True,
                    "availability_basis": "inventory_selected_tools",
                },
                "source": "tool_registry",
            }
        )
    payload["web_research"] = projected_items
    payload["disabled_capabilities"] = [
        item
        for item in payload.get("disabled_capabilities") or []
        if not (
            isinstance(item, dict)
            and str(item.get("name") or "").strip() == "web_research"
            and str(item.get("reason") or "").strip()
            in {"web_research_tools_unavailable", "incomplete_research_tool_pair"}
        )
    ]
    return True


def _normalized_skill_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata or {})
    for key in (
        "resolved_tool_names",
        "startup_preview_tool_names",
        "startup_preview_semantic_families",
    ):
        if key in normalized:
            normalized[key] = _stable_unique_texts(
                filter_invalid_ai_runtime_references(list(normalized.get(key) or []))
            )
    return normalized


def _issue_payload(issue: SkillResolveIssue | Any) -> dict[str, Any]:
    if hasattr(issue, "to_dict"):
        return issue.to_dict()
    return dict(issue or {})


def _skill_resolution_issues(
    *,
    skill_result: SkillResolveResult,
    skill_id: Any | None = None,
    skill_name: str = "",
) -> list[SkillResolveIssue]:
    return [
        issue
        for issue in list(getattr(skill_result, "resolution_issues", []) or [])
        if issue_matches_skill(issue, skill_id=skill_id, skill_name=skill_name)
    ]


def _resolution_status_from_issues(
    *,
    metadata: dict[str, Any],
    issues: list[SkillResolveIssue],
) -> tuple[str | None, str | None]:
    metadata_status = str(metadata.get("resolution_status") or "").strip()
    metadata_reason = str(metadata.get("resolution_reason") or "").strip()
    if metadata_status:
        return metadata_status, metadata_reason or None
    if not issues:
        return None, None
    status = "degraded" if bool(metadata.get("has_execution_tools")) else "unavailable"
    return status, issues[0].code


def build_skill_items(
    items: list[dict[str, Any]],
    *,
    skill_result: SkillResolveResult,
) -> list[dict[str, Any]]:
    descriptor_by_name = {
        str(getattr(descriptor, "name", "") or "").strip(): descriptor
        for descriptor in (skill_result.capability_descriptors or [])
        if str(getattr(descriptor, "name", "") or "").strip()
    }

    enriched_items: list[dict[str, Any]] = []
    for item in items:
        skill_name = str(item.get("name") or "").strip()
        descriptor = descriptor_by_name.get(skill_name)
        if descriptor is None:
            enriched_items.append(dict(item))
            continue

        enriched_item = dict(item)
        metadata = _normalized_skill_metadata(dict(descriptor.metadata or {}))
        if metadata:
            enriched_item["metadata"] = {
                **dict(enriched_item.get("metadata") or {}),
                **metadata,
            }
        issues = _skill_resolution_issues(
            skill_result=skill_result,
            skill_id=metadata.get("skill_id"),
            skill_name=skill_name,
        )
        status, reason = _resolution_status_from_issues(
            metadata=metadata,
            issues=issues,
        )
        if status in {"degraded", "unavailable"}:
            enriched_item["status"] = status
            enriched_item["reason"] = reason
            enriched_item["metadata"] = {
                **dict(enriched_item.get("metadata") or {}),
                "resolution_issues": [_issue_payload(issue) for issue in issues]
                or list(metadata.get("resolution_issues") or []),
            }
        source = str(getattr(descriptor, "source", "") or "").strip()
        if source:
            enriched_item["source"] = source
        enriched_items.append(enriched_item)
    return enriched_items


def provider_payload(provider: AIProvider | None) -> dict[str, Any]:
    if provider is None:
        return {
            "id": None,
            "code": None,
            "name": None,
            "type": None,
            "status": "unavailable",
            "reason": "provider_not_selected",
        }
    status = "available" if bool(provider.is_active) else "degraded"
    return {
        "id": provider.id,
        "code": provider.code,
        "name": provider.name,
        "type": provider.type,
        "status": status,
        "reason": None if status == "available" else "provider_inactive",
    }


def model_payload(
    model: AIModel | None,
    runtime_caps: dict[str, Any],
) -> dict[str, Any]:
    if model is None:
        return {
            "id": None,
            "code": None,
            "name": None,
            "type": None,
            "status": "unavailable",
            "reason": "model_not_selected",
        }
    status = "available" if bool(model.is_active) else "degraded"
    payload = {
        "id": model.id,
        "code": model.code,
        "name": model.name,
        "type": model.type,
        "status": status,
        "reason": None if status == "available" else "model_inactive",
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
    }
    for key in (
        "supports_function_calling",
        "supports_streaming",
        "supports_vision",
        "supports_audio",
        "supports_video",
    ):
        if key in runtime_caps:
            payload[key] = runtime_caps[key]
    return payload


def build_knowledge_base_items(
    kb_bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for binding in kb_bindings:
        kb_id = binding.get("knowledge_base_id")
        if kb_id is None:
            continue
        suppressed = bool(binding.get("platform_suppressed"))
        enabled = bool(binding.get("enabled", True))
        if suppressed:
            status = "degraded"
            reason = "platform_binding_suppressed"
        elif enabled:
            status = "available"
            reason = None
        else:
            status = "unavailable"
            reason = "binding_disabled"
        items.append(
            {
                "name": str(binding.get("kb_name") or f"knowledge_base:{kb_id}"),
                "kind": "context_provider",
                "status": status,
                "reason": reason,
                "metadata": {
                    "knowledge_base_id": int(kb_id),
                    "binding_scope": binding.get("binding_scope"),
                    "scope": binding.get("kb_scope"),
                    "document_count": int(binding.get("kb_document_count") or 0),
                    "owner_tenant_id": binding.get("kb_owner_tenant_id"),
                    "owner_tenant_name": binding.get("kb_owner_tenant_name"),
                },
                "source": "agent_kb_binding",
            }
        )
    if items:
        return items
    return [
        {
            "name": "knowledge_base",
            "kind": "context_provider",
            "status": "unavailable",
            "reason": "no_effective_knowledge_base_binding",
            "metadata": {},
            "source": "agent_kb_binding",
        }
    ]


def build_extension_items(
    *,
    tools: list[ToolDefinition],
    skill_result: SkillResolveResult,
) -> list[dict[str, Any]]:
    extensions: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "tool_names": [],
            "skill_names": [],
            "package_names": [],
            "startup_preview_tool_names": [],
            "startup_preview_semantic_families": [],
            "resolution_issues": [],
        }
    )

    for tool in filter_invalid_ai_runtime_tools(tools):
        plugin_name = str(getattr(tool, "source_plugin", "") or "").strip()
        if not plugin_name:
            continue
        bucket = extensions[plugin_name]
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if tool_name and tool_name not in bucket["tool_names"]:
            bucket["tool_names"].append(tool_name)
        package_name = str(getattr(tool, "source_package_name", "") or "").strip()
        if package_name and package_name not in bucket["package_names"]:
            bucket["package_names"].append(package_name)
        skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        if skill_name and skill_name not in bucket["skill_names"]:
            bucket["skill_names"].append(skill_name)

    for descriptor in skill_result.capability_descriptors or []:
        metadata = dict(descriptor.metadata or {})
        plugin_name = str(metadata.get("source_plugin") or "").strip()
        if not plugin_name:
            continue
        bucket = extensions[plugin_name]
        skill_name = str(descriptor.name or "").strip()
        if skill_name and skill_name not in bucket["skill_names"]:
            bucket["skill_names"].append(skill_name)
        package_name = str(metadata.get("package_name") or "").strip()
        if package_name and package_name not in bucket["package_names"]:
            bucket["package_names"].append(package_name)
        for tool_name in _stable_unique_texts(
            filter_invalid_ai_runtime_references(
                list(metadata.get("startup_preview_tool_names") or [])
            )
        ):
            if tool_name not in bucket["startup_preview_tool_names"]:
                bucket["startup_preview_tool_names"].append(tool_name)
        for family in _stable_unique_texts(
            filter_invalid_ai_runtime_references(
                list(metadata.get("startup_preview_semantic_families") or [])
            )
        ):
            if family not in bucket["startup_preview_semantic_families"]:
                bucket["startup_preview_semantic_families"].append(family)
        for issue in list(metadata.get("resolution_issues") or []):
            if issue not in bucket["resolution_issues"]:
                bucket["resolution_issues"].append(issue)

    for issue in list(getattr(skill_result, "resolution_issues", []) or []):
        plugin_name = str(getattr(issue, "source_plugin", "") or "").strip()
        if not plugin_name:
            continue
        bucket = extensions[plugin_name]
        issue_payload = _issue_payload(issue)
        if issue_payload not in bucket["resolution_issues"]:
            bucket["resolution_issues"].append(issue_payload)
        if issue.skill_name and issue.skill_name not in bucket["skill_names"]:
            bucket["skill_names"].append(issue.skill_name)
        if issue.package_name and issue.package_name not in bucket["package_names"]:
            bucket["package_names"].append(issue.package_name)

    items: list[dict[str, Any]] = []
    for plugin_name, bucket in sorted(extensions.items()):
        issues = list(bucket["resolution_issues"] or [])
        tool_names = sorted(bucket["tool_names"])
        if tool_names and not issues:
            status = "available"
            reason = None
        elif tool_names:
            status = "degraded"
            reason = str((issues[0] or {}).get("code") or "plugin_runtime_degraded")
        else:
            status = "unavailable"
            reason = str((issues[0] or {}).get("code") or "no_resolved_plugin_tools")

        metadata = {
            "tool_names": tool_names,
            "skill_names": sorted(bucket["skill_names"]),
            "package_names": sorted(bucket["package_names"]),
            "startup_preview_tool_names": sorted(bucket["startup_preview_tool_names"]),
            "startup_preview_semantic_families": sorted(
                bucket["startup_preview_semantic_families"]
            ),
        }
        if issues:
            metadata["resolution_issues"] = issues
        items.append(
            {
                "name": plugin_name,
                "kind": "extension",
                "status": status,
                "reason": reason,
                "metadata": metadata,
                "source": "plugin_runtime",
            }
        )
    return items


def shape_manifest_payload(
    *,
    scope: str,
    tenant_id: int | None,
    agent: Agent,
    manifest: Any,
    kb_bindings: list[dict[str, Any]],
    skill_result: SkillResolveResult,
    tools: list[ToolDefinition],
) -> dict[str, Any]:
    payload = manifest.to_dict()
    payload["skills"] = build_skill_items(
        list(payload.get("skills") or []),
        skill_result=skill_result,
    )
    runtime_caps = dict(payload.get("runtime_model_capabilities") or {})
    provider = getattr(getattr(agent, "model", None), "provider", None)
    payload["scope"] = scope
    payload["tenant_id"] = tenant_id
    payload["provider"] = provider_payload(provider)
    payload["model"] = model_payload(getattr(agent, "model", None), runtime_caps)
    payload["knowledge_bases"] = build_knowledge_base_items(kb_bindings)
    payload["extensions"] = build_extension_items(
        tools=tools,
        skill_result=skill_result,
    )
    inventory_web_research_pair = _project_inventory_web_research_availability(payload)

    summary = AIRuntimeInventoryService.build_compact_summary(manifest)
    inventory_tool_names = _inventory_selected_tool_names(payload)
    inventory_skill_names = _inventory_selected_skill_names(payload)
    summary.update(
        {
            "selection_semantics": "inventory_snapshot",
            "selection_live": False,
            "live_turn_bound": False,
            "inventory_tool_count": len(inventory_tool_names),
            "inventory_selected_tool_names": inventory_tool_names,
            "inventory_skill_count": len(inventory_skill_names),
            "inventory_selected_skill_names": inventory_skill_names,
            "tool_count": len(payload.get("tools") or []),
            "skill_count": len(payload.get("skills") or []),
            "knowledge_base_count": len(
                [
                    item
                    for item in (payload.get("knowledge_bases") or [])
                    if item.get("status") == "available"
                ]
            ),
            "knowledge_base_names": [
                item.get("name")
                for item in (payload.get("knowledge_bases") or [])
                if item.get("status") == "available"
            ],
            "extension_names": [
                item.get("name") for item in (payload.get("extensions") or [])
            ],
            "disabled_capability_names": [
                item.get("name")
                for item in (payload.get("disabled_capabilities") or [])
            ],
            "web_research_status": next(
                (
                    str(item.get("status"))
                    for item in (payload.get("web_research") or [])
                    if str(item.get("name") or "").strip() == "web_research"
                ),
                "unavailable",
            ),
            "agent_name": str(getattr(agent, "name", "") or "").strip() or None,
            "agent_owner_tenant_id": getattr(agent, "owner_tenant_id", None),
            "manifest_version": payload.get("manifest_version"),
        }
    )
    if inventory_web_research_pair:
        summary["web_research_pair_complete"] = True
        summary["web_research_status"] = "available"
        continuation_families = _stable_unique_texts(
            list(summary.get("continuation_capable_families") or []) + ["web_research"]
        )
        summary["continuation_capable_families"] = continuation_families
    payload["summary"] = summary
    payload.setdefault("boundaries", {})
    payload["boundaries"]["scope_context"] = scope
    payload["boundaries"]["selection_semantics"] = "inventory_snapshot"
    payload["boundaries"]["selection_live"] = False
    payload["boundaries"]["live_turn_bound"] = False
    return payload


def build_empty_manifest(
    *,
    scope: str,
    tenant_id: int | None,
    agent_code: str | None,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "tenant_id": tenant_id,
        "agent_id": None,
        "provider": {
            "id": None,
            "code": None,
            "name": None,
            "type": None,
            "status": "unavailable",
            "reason": "agent_not_selected",
        },
        "model": {
            "id": None,
            "code": None,
            "name": None,
            "type": None,
            "status": "unavailable",
            "reason": "agent_not_selected",
        },
        "runtime_model_capabilities": {},
        "tools": [],
        "skills": [],
        "knowledge_bases": [
            {
                "name": "knowledge_base",
                "kind": "context_provider",
                "status": "unavailable",
                "reason": "agent_not_selected",
                "metadata": {},
                "source": "agent_kb_binding",
            }
        ],
        "memory": [
            {
                "name": "memory",
                "kind": "context_provider",
                "status": "unavailable",
                "reason": "agent_not_selected",
                "metadata": {},
                "source": "request.flags",
            }
        ],
        "web_research": [
            {
                "name": "web_research",
                "kind": "execution_tool",
                "status": "unavailable",
                "reason": "agent_not_selected",
                "metadata": {},
                "source": "tool_registry",
            }
        ],
        "extensions": [],
        "disabled_capabilities": [
            {
                "name": "agent_resolution",
                "kind": "context_provider",
                "status": "degraded",
                "reason": "agent_not_selected",
                "metadata": {"agent_code": agent_code},
                "source": "runtime_inventory",
            }
        ],
        "boundaries": {
            "scope_context": scope,
            "selection_semantics": "inventory_snapshot",
            "selection_live": False,
            "live_turn_bound": False,
            "write_operations_require_confirmation": True,
        },
        "sources": [],
        "manifest_version": "runtime-capability-manifest/v1",
        "summary": {
            "selected_skill_names": [],
            "turn_skill_activation_applied": False,
            "turn_skill_activation_reason": None,
            "selection_semantics": "inventory_snapshot",
            "selection_live": False,
            "live_turn_bound": False,
            "context_line": "",
            "context_source_kinds": [],
            "tool_families": [],
            "web_research_pair_complete": False,
            "continuation_capable_families": [],
            "provider": None,
            "model": None,
            "tool_count": 0,
            "skill_count": 0,
            "knowledge_base_count": 0,
            "knowledge_base_names": [],
            "extension_names": [],
            "disabled_capability_names": ["agent_resolution"],
            "web_research_status": "unavailable",
            "agent_name": None,
            "manifest_version": "runtime-capability-manifest/v1",
        },
    }


__all__ = [
    "build_empty_manifest",
    "shape_manifest_payload",
]
