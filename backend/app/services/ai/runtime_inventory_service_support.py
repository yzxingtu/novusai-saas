"""
Runtime inventory payload shaping helpers.
运行时能力清单输出整形辅助。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.ai.runtime import AIRuntimeInventoryService
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.models.ai.agent import Agent
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider


def _stable_unique_texts(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalized_skill_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata or {})
    for key in (
        "resolved_tool_names",
        "startup_preview_tool_names",
        "startup_preview_semantic_families",
    ):
        if key in normalized:
            normalized[key] = _stable_unique_texts(list(normalized.get(key) or []))
    return normalized


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
        }
    )

    for tool in tools:
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
            list(metadata.get("startup_preview_tool_names") or [])
        ):
            if tool_name not in bucket["startup_preview_tool_names"]:
                bucket["startup_preview_tool_names"].append(tool_name)
        for family in _stable_unique_texts(
            list(metadata.get("startup_preview_semantic_families") or [])
        ):
            if family not in bucket["startup_preview_semantic_families"]:
                bucket["startup_preview_semantic_families"].append(family)

    return [
        {
            "name": plugin_name,
            "kind": "extension",
            "status": "available",
            "reason": None,
            "metadata": {
                "tool_names": sorted(bucket["tool_names"]),
                "skill_names": sorted(bucket["skill_names"]),
                "package_names": sorted(bucket["package_names"]),
                "startup_preview_tool_names": sorted(
                    bucket["startup_preview_tool_names"]
                ),
                "startup_preview_semantic_families": sorted(
                    bucket["startup_preview_semantic_families"]
                ),
            },
            "source": "plugin_runtime",
        }
        for plugin_name, bucket in sorted(extensions.items())
    ]


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

    summary = AIRuntimeInventoryService.build_compact_summary(manifest)
    summary.update(
        {
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
            "page_context_available": any(
                item.get("status") == "available"
                for item in (payload.get("page_context") or [])
            ),
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
    payload["summary"] = summary
    payload.setdefault("boundaries", {})
    payload["boundaries"]["scope_context"] = scope
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
        "page_context": [
            {
                "name": "page_context",
                "kind": "context_provider",
                "status": "unavailable",
                "reason": "page_context_not_attached",
                "metadata": {},
                "source": "request.page_context",
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
            "write_operations_require_confirmation": True,
        },
        "sources": [],
        "manifest_version": "runtime-capability-manifest/v1",
        "summary": {
            "selected_skill_names": [],
            "context_line": "",
            "context_source_kinds": [],
            "tool_families": [],
            "page_operation_names": [],
            "page_context_attached": False,
            "web_research_pair_complete": False,
            "continuation_capable_families": [],
            "knowledge_base_hint": False,
            "page_context_hint": False,
            "memory_hint": False,
            "provider": None,
            "model": None,
            "tool_count": 0,
            "skill_count": 0,
            "knowledge_base_count": 0,
            "knowledge_base_names": [],
            "extension_names": [],
            "disabled_capability_names": ["agent_resolution"],
            "page_context_available": False,
            "web_research_status": "unavailable",
            "agent_name": None,
            "manifest_version": "runtime-capability-manifest/v1",
        },
    }


__all__ = [
    "build_empty_manifest",
    "shape_manifest_payload",
]
