"""Structured tool routing for intent-aware orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import (
    page_context_has_active_form,
    page_context_payload,
)
from app.ai.tools.types import ToolDefinition

from .types import ExecutionBudget, IntentPlan


@dataclass
class ToolRoutingDecision:
    candidate_tools: list[ToolDefinition] = field(default_factory=list)
    intent_allowed_tools: dict[str, list[str]] = field(default_factory=dict)
    intent_preferred_tools: dict[str, list[str]] = field(default_factory=dict)

    def candidate_tool_names(self) -> list[str]:
        return [tool.name for tool in self.candidate_tools]


@dataclass(frozen=True)
class PageWorkflowState:
    active_form_stage: str = ""
    active_surface_id: str = ""
    active_surface_kind: str = ""
    can_submit_form: bool = False
    has_active_form: bool = False
    has_active_surface: bool = False
    has_overlay_surface: bool = False
    has_surface_stack: bool = False
    has_thin_runtime_state: bool = False
    page_key: str = ""
    surface_stack_depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_form_stage": self.active_form_stage,
            "active_surface_id": self.active_surface_id,
            "active_surface_kind": self.active_surface_kind,
            "can_submit_form": self.can_submit_form,
            "has_active_form": self.has_active_form,
            "has_active_surface": self.has_active_surface,
            "has_overlay_surface": self.has_overlay_surface,
            "has_surface_stack": self.has_surface_stack,
            "has_thin_runtime_state": self.has_thin_runtime_state,
            "page_key": self.page_key,
            "surface_stack_depth": self.surface_stack_depth,
        }


@dataclass(frozen=True)
class PageIntentToolPlan:
    allowed_names: list[str] = field(default_factory=list)
    preferred_names: list[str] = field(default_factory=list)
    workflow_stage: str = "idle"
    workflow_state: PageWorkflowState = field(default_factory=PageWorkflowState)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "page_workflow_stage": self.workflow_stage,
            "page_workflow_state": self.workflow_state.to_dict(),
        }


class ToolRouter:
    _PAGE_INTENT_TOOL_MAP: dict[str, tuple[list[str], list[str]]] = {
        "page_summary": (
            ["ui_get_snapshot"],
            ["ui_get_snapshot"],
        ),
        "page_navigation": (
            [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
            [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
        ),
        "page_search": (
            [
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ],
            [
                "ui_read_region",
                "ui_click",
                "ui_list_interactables",
            ],
        ),
        "page_pagination": (
            [
                "ui_read_table",
                "ui_click",
                "ui_list_interactables",
            ],
            [
                "ui_read_table",
                "ui_click",
                "ui_list_interactables",
            ],
        ),
        "page_row_detail": (
            [
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ],
            [
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ],
        ),
        "page_form_read": (
            [
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ],
            [
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ],
        ),
        "page_screenshot": (
            [
                "ui_get_snapshot",
            ],
            [
                "ui_get_snapshot",
            ],
        ),
        "page_editor_read": (
            [
                "ui_read_region",
                "ui_get_snapshot",
            ],
            [
                "ui_read_region",
                "ui_get_snapshot",
            ],
        ),
        "page_editor_write": (
            [
                "ui_open_surface",
                "ui_fill_form",
                "ui_submit_form",
            ],
            [
                "ui_fill_form",
                "ui_submit_form",
                "ui_open_surface",
            ],
        ),
    }

    @classmethod
    def _surface_stack_entries(
        cls,
        page_context: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        raw_stack = page_context.get("surface_stack")
        if not isinstance(raw_stack, list):
            return []
        return [entry for entry in raw_stack if isinstance(entry, Mapping)]

    @classmethod
    def _resolve_active_surface_kind(
        cls,
        *,
        active_surface_id: str,
        surface_stack: list[Mapping[str, Any]],
    ) -> str:
        if not surface_stack:
            return ""
        if active_surface_id:
            for entry in reversed(surface_stack):
                surface_id = str(entry.get("surface_id") or "").strip()
                if surface_id and surface_id == active_surface_id:
                    return str(entry.get("kind") or "").strip()
        return str(surface_stack[-1].get("kind") or "").strip()

    @classmethod
    def resolve_page_workflow_state(
        cls,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> PageWorkflowState:
        page_context = page_context_payload(input_variables)
        if not isinstance(page_context, Mapping):
            return PageWorkflowState()
        active_form_summary = (
            page_context.get("active_form_summary")
            if isinstance(page_context.get("active_form_summary"), Mapping)
            else {}
        )
        active_form_stage = str(active_form_summary.get("stage") or "").strip()
        surface_stack = cls._surface_stack_entries(page_context)
        active_surface_id = str(page_context.get("active_surface_id") or "").strip()
        has_surface_stack = bool(surface_stack)
        has_active_surface = bool(active_surface_id)
        has_active_form = page_context_has_active_form(page_context)
        active_surface_kind = cls._resolve_active_surface_kind(
            active_surface_id=active_surface_id,
            surface_stack=surface_stack,
        )
        overlay_surface_entries = [
            entry
            for entry in surface_stack
            if str(entry.get("kind") or "").strip()
            not in {"", "page"}
        ]
        return PageWorkflowState(
            active_form_stage=active_form_stage,
            active_surface_id=active_surface_id,
            active_surface_kind=active_surface_kind,
            can_submit_form=bool(active_form_summary.get("can_submit")),
            has_active_form=has_active_form,
            has_active_surface=has_active_surface,
            has_overlay_surface=bool(overlay_surface_entries),
            has_surface_stack=has_surface_stack,
            has_thin_runtime_state=bool(
                isinstance(page_context.get("ui_epoch"), int)
                or has_surface_stack
                or has_active_surface
                or has_active_form
            ),
            page_key=str(page_context.get("page_key") or "").strip(),
            surface_stack_depth=len(surface_stack),
        )

    @classmethod
    def page_intent_tool_plan(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> PageIntentToolPlan:
        workflow_state = cls.resolve_page_workflow_state(
            input_variables=input_variables
        )
        if intent_kind == "page_navigation":
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ]
            preferred_names = (
                [
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ]
                if workflow_state.has_overlay_surface
                else list(allowed_names)
            )
            return PageIntentToolPlan(
                allowed_names=allowed_names,
                preferred_names=preferred_names,
                workflow_stage=(
                    "verify_navigation_result"
                    if workflow_state.has_overlay_surface
                    else "discover_navigation_target"
                ),
                workflow_state=workflow_state,
            )

        if intent_kind == "page_form_read":
            if workflow_state.has_active_form:
                allowed_names = [
                    "ui_get_form_state",
                    "ui_read_region",
                    "ui_get_snapshot",
                ]
                return PageIntentToolPlan(
                    allowed_names=allowed_names,
                    preferred_names=list(allowed_names),
                    workflow_stage="read_active_form",
                    workflow_state=workflow_state,
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ]
            return PageIntentToolPlan(
                allowed_names=allowed_names,
                preferred_names=list(allowed_names),
                workflow_stage="discover_form_surface",
                workflow_state=workflow_state,
            )

        if intent_kind == "page_form_write":
            if workflow_state.has_active_form:
                allowed_names = [
                    "ui_get_form_state",
                    "ui_fill_form",
                    "ui_set_field",
                    "ui_submit_form",
                    "ui_open_surface",
                ]
                preferred_names = [
                    "ui_fill_form",
                    "ui_set_field",
                    "ui_submit_form",
                    "ui_get_form_state",
                    "ui_open_surface",
                ]
                return PageIntentToolPlan(
                    allowed_names=allowed_names,
                    preferred_names=preferred_names,
                    workflow_stage=(
                        "submit_active_form"
                        if workflow_state.can_submit_form
                        or workflow_state.active_form_stage == "ready_to_submit"
                        else "fill_active_form"
                    ),
                    workflow_state=workflow_state,
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_open_surface",
                "ui_click",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ]
            return PageIntentToolPlan(
                allowed_names=allowed_names,
                preferred_names=list(allowed_names),
                workflow_stage="discover_form_before_write",
                workflow_state=workflow_state,
            )

        if intent_kind == "page_row_detail":
            if workflow_state.has_overlay_surface:
                allowed_names = [
                    "ui_read_region",
                    "ui_read_table",
                    "ui_get_snapshot",
                    "ui_click",
                    "ui_open_surface",
                ]
                preferred_names = [
                    "ui_read_region",
                    "ui_read_table",
                    "ui_get_snapshot",
                    "ui_click",
                    "ui_open_surface",
                ]
                return PageIntentToolPlan(
                    allowed_names=allowed_names,
                    preferred_names=preferred_names,
                    workflow_stage="read_detail_surface",
                    workflow_state=workflow_state,
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ]
            return PageIntentToolPlan(
                allowed_names=allowed_names,
                preferred_names=list(allowed_names),
                workflow_stage="open_detail_surface",
                workflow_state=workflow_state,
            )

        if intent_kind == "page_editor_write":
            allowed_names = [
                "ui_open_surface",
                "ui_fill_form",
                "ui_submit_form",
            ]
            preferred_names = (
                [
                    "ui_fill_form",
                    "ui_submit_form",
                    "ui_open_surface",
                ]
                if workflow_state.has_active_form
                else list(allowed_names)
            )
            workflow_stage = "discover_editor_surface"
            if workflow_state.has_active_form:
                workflow_stage = (
                    "submit_active_editor"
                    if workflow_state.can_submit_form
                    or workflow_state.active_form_stage == "ready_to_submit"
                    else "edit_active_editor"
                )
            return PageIntentToolPlan(
                allowed_names=allowed_names,
                preferred_names=preferred_names,
                workflow_stage=workflow_stage,
                workflow_state=workflow_state,
            )

        allowed_names, preferred_names = cls._PAGE_INTENT_TOOL_MAP.get(
            intent_kind,
            ([], []),
        )
        return PageIntentToolPlan(
            allowed_names=list(allowed_names),
            preferred_names=list(preferred_names),
            workflow_stage="intent_static_tools",
            workflow_state=workflow_state,
        )

    @classmethod
    def page_intent_tool_preferences(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        plan = cls.page_intent_tool_plan(
            intent_kind,
            input_variables=input_variables,
        )
        return list(plan.allowed_names), list(plan.preferred_names)

    @classmethod
    def route(
        cls,
        *,
        intents: list[IntentPlan],
        tools: list[ToolDefinition],
        budget: ExecutionBudget,
        input_variables: dict[str, Any] | None,
        user_text: str = "",
    ) -> ToolRoutingDecision:
        tools_by_name = {tool.name: tool for tool in tools}
        candidate_names: list[str] = []
        intent_allowed: dict[str, list[str]] = {}
        intent_preferred: dict[str, list[str]] = {}
        lowered = user_text.lower()

        def register(
            intent: IntentPlan,
            names: list[str],
            preferred: list[str] | None = None,
        ) -> None:
            allowed = [name for name in names if name in tools_by_name]
            effective_preferred = [
                name for name in (preferred or allowed) if name in allowed
            ]
            intent_allowed[intent.intent_id] = allowed
            intent_preferred[intent.intent_id] = effective_preferred
            for name in allowed:
                if name not in candidate_names:
                    candidate_names.append(name)

        for intent in intents:
            if intent.family == "none" or not intent.requires_tools:
                intent_allowed[intent.intent_id] = []
                intent_preferred[intent.intent_id] = []
                continue

            if intent.kind == "weather_query":
                future_terms = (
                    "明天",
                    "未来",
                    "forecast",
                    "接下来",
                    "后天",
                    "7天",
                    "一周",
                )
                wants_forecast = any(term in lowered for term in future_terms)
                names = ["get_current_weather"]
                if wants_forecast and "get_weather_forecast" in tools_by_name:
                    names.append("get_weather_forecast")
                register(intent, names, names)
                continue

            if intent.kind == "time_query":
                register(intent, ["get_current_time"])
                continue

            if intent.kind == "web_research":
                metadata = dict(intent.metadata or {})
                explicit_url = str(metadata.get("explicit_url") or "").strip()
                fetch_only = bool(metadata.get("fetch_only")) or bool(explicit_url)
                prefer_fetch_url = fetch_only or bool(
                    metadata.get("prefer_fetch_url")
                )
                if fetch_only:
                    if "fetch_url" in tools_by_name:
                        register(intent, ["fetch_url"], ["fetch_url"])
                    else:
                        register(intent, ["web_search"], ["web_search"])
                    continue
                if prefer_fetch_url:
                    register(
                        intent,
                        ["fetch_url", "web_search"],
                        ["fetch_url", "web_search"],
                    )
                    continue
                register(
                    intent,
                    ["web_search", "fetch_url"],
                    ["web_search", "fetch_url"],
                )
                continue

            if intent.kind in cls._PAGE_INTENT_TOOL_MAP or intent.kind == "page_form_write":
                names, preferred = cls.page_intent_tool_preferences(
                    intent.kind,
                    input_variables=input_variables,
                )
                register(intent, names, preferred)
                continue

            if intent.kind == "knowledge_query":
                register(intent, [])

        if (
            budget.max_candidate_tools > 0
            and len(candidate_names) > budget.max_candidate_tools
        ):
            candidate_names = candidate_names[: budget.max_candidate_tools]

        candidate_tools = [
            tools_by_name[name] for name in candidate_names if name in tools_by_name
        ]
        for intent_id, allowed in list(intent_allowed.items()):
            intent_allowed[intent_id] = [
                name for name in allowed if name in candidate_names
            ]
            intent_preferred[intent_id] = [
                name
                for name in intent_preferred.get(intent_id, [])
                if name in candidate_names
            ]

        return ToolRoutingDecision(
            candidate_tools=candidate_tools,
            intent_allowed_tools=intent_allowed,
            intent_preferred_tools=intent_preferred,
        )


__all__ = [
    "PageIntentToolPlan",
    "PageWorkflowState",
    "ToolRouter",
    "ToolRoutingDecision",
]
