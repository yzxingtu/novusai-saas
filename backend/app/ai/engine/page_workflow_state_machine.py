"""Canonical page workflow state machine for page-runtime intents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import (
    page_context_has_active_form,
    page_context_payload,
)


def _ordered_unique_tool_names(*groups: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw_name in group:
            name = str(raw_name or "").strip()
            if not name or name in seen:
                continue
            ordered.append(name)
            seen.add(name)
    return ordered


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
class PageIntentCompletionContract:
    mode: str = "verify_only"
    completion_signals: list[str] = field(default_factory=list)
    action_signals: list[str] = field(default_factory=list)
    verify_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "completion_signals": list(self.completion_signals),
            "action_signals": list(self.action_signals),
            "verify_signals": list(self.verify_signals),
        }


@dataclass(frozen=True)
class PageIntentToolPlan:
    allowed_names: list[str] = field(default_factory=list)
    preferred_names: list[str] = field(default_factory=list)
    workflow_stage: str = "idle"
    workflow_phase: str = "idle"
    workflow_goal: str = ""
    workflow_state: PageWorkflowState = field(default_factory=PageWorkflowState)
    completion_contract: PageIntentCompletionContract = field(
        default_factory=PageIntentCompletionContract
    )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "page_workflow_stage": self.workflow_stage,
            "page_workflow_phase": self.workflow_phase,
            "page_workflow_goal": self.workflow_goal,
            "page_workflow_state": self.workflow_state.to_dict(),
            "page_workflow_completion": self.completion_contract.to_dict(),
        }


def _verify_only_contract(
    *signal_groups: list[str] | tuple[str, ...] | str,
) -> PageIntentCompletionContract:
    groups: list[list[str]] = []
    for item in signal_groups:
        if isinstance(item, str):
            groups.append([item])
            continue
        groups.append([str(name or "").strip() for name in item])
    verify_signals = _ordered_unique_tool_names(*groups)
    return PageIntentCompletionContract(
        mode="verify_only",
        completion_signals=list(verify_signals),
        verify_signals=list(verify_signals),
    )


def _action_then_verify_contract(
    *,
    action_signals: list[str] | tuple[str, ...],
    verify_signals: list[str] | tuple[str, ...],
) -> PageIntentCompletionContract:
    normalized_actions = _ordered_unique_tool_names(list(action_signals))
    normalized_verify = _ordered_unique_tool_names(list(verify_signals))
    return PageIntentCompletionContract(
        mode="action_then_verify",
        completion_signals=list(normalized_verify),
        action_signals=normalized_actions,
        verify_signals=normalized_verify,
    )


def _plan(
    *,
    allowed_names: list[str],
    preferred_names: list[str] | None = None,
    workflow_stage: str,
    workflow_phase: str,
    workflow_goal: str,
    workflow_state: PageWorkflowState,
    completion_contract: PageIntentCompletionContract,
) -> PageIntentToolPlan:
    normalized_allowed = _ordered_unique_tool_names(list(allowed_names))
    normalized_preferred = _ordered_unique_tool_names(
        list(preferred_names or normalized_allowed),
        normalized_allowed,
    )
    return PageIntentToolPlan(
        allowed_names=normalized_allowed,
        preferred_names=normalized_preferred,
        workflow_stage=workflow_stage,
        workflow_phase=workflow_phase,
        workflow_goal=workflow_goal,
        workflow_state=workflow_state,
        completion_contract=completion_contract,
    )


class PageWorkflowStateMachine:
    """Owns page-runtime workflow planning for page intents."""

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
    def resolve_state(
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
            if str(entry.get("kind") or "").strip() not in {"", "page"}
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
    def plan_for_intent(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> PageIntentToolPlan:
        workflow_state = cls.resolve_state(input_variables=input_variables)

        if intent_kind == "page_summary":
            return _plan(
                allowed_names=["ui_get_snapshot"],
                workflow_stage="read_page_summary",
                workflow_phase="read",
                workflow_goal="page_summary",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract("ui_get_snapshot"),
            )

        if intent_kind == "page_screenshot":
            return _plan(
                allowed_names=["ui_get_snapshot"],
                workflow_stage="capture_page_snapshot",
                workflow_phase="read",
                workflow_goal="page_screenshot",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract("ui_get_snapshot"),
            )

        if intent_kind == "page_navigation":
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ]
            if workflow_state.has_overlay_surface:
                preferred_names = [
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ]
                return _plan(
                    allowed_names=allowed_names,
                    preferred_names=preferred_names,
                    workflow_stage="verify_navigation_result",
                    workflow_phase="verify",
                    workflow_goal="navigation",
                    workflow_state=workflow_state,
                    completion_contract=_verify_only_contract("ui_get_snapshot"),
                )
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="discover_navigation_target",
                workflow_phase="navigate_or_open",
                workflow_goal="navigation",
                workflow_state=workflow_state,
                completion_contract=_action_then_verify_contract(
                    action_signals=["ui_click", "ui_open_surface"],
                    verify_signals=["ui_get_snapshot"],
                ),
            )

        if intent_kind == "page_search":
            allowed_names = [
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ]
            preferred_names = [
                "ui_read_region",
                "ui_click",
                "ui_list_interactables",
            ]
            return _plan(
                allowed_names=allowed_names,
                preferred_names=preferred_names,
                workflow_stage="read_search_region",
                workflow_phase="read",
                workflow_goal="search",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract("ui_read_region"),
            )

        if intent_kind == "page_pagination":
            allowed_names = [
                "ui_read_table",
                "ui_click",
                "ui_list_interactables",
            ]
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="navigate_pagination",
                workflow_phase="navigate_or_open",
                workflow_goal="pagination",
                workflow_state=workflow_state,
                completion_contract=_action_then_verify_contract(
                    action_signals=["ui_click"],
                    verify_signals=["ui_read_table"],
                ),
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
                return _plan(
                    allowed_names=allowed_names,
                    workflow_stage="read_detail_surface",
                    workflow_phase="read",
                    workflow_goal="row_detail",
                    workflow_state=workflow_state,
                    completion_contract=_verify_only_contract(
                        [
                            "ui_read_region",
                            "ui_read_table",
                            "ui_get_snapshot",
                        ]
                    ),
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ]
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="open_detail_surface",
                workflow_phase="navigate_or_open",
                workflow_goal="row_detail",
                workflow_state=workflow_state,
                completion_contract=_action_then_verify_contract(
                    action_signals=["ui_click", "ui_open_surface"],
                    verify_signals=[
                        "ui_read_region",
                        "ui_read_table",
                        "ui_get_snapshot",
                    ],
                ),
            )

        if intent_kind == "page_form_read":
            if workflow_state.has_active_form:
                allowed_names = [
                    "ui_get_form_state",
                    "ui_read_region",
                    "ui_get_snapshot",
                ]
                return _plan(
                    allowed_names=allowed_names,
                    workflow_stage="read_active_form",
                    workflow_phase="read",
                    workflow_goal="form_read",
                    workflow_state=workflow_state,
                    completion_contract=_verify_only_contract(allowed_names),
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ]
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="discover_form_surface",
                workflow_phase="discover",
                workflow_goal="form_read",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract(
                    ["ui_get_form_state", "ui_read_region", "ui_get_snapshot"]
                ),
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
                ready_to_submit = (
                    workflow_state.can_submit_form
                    or workflow_state.active_form_stage == "ready_to_submit"
                )
                return _plan(
                    allowed_names=allowed_names,
                    preferred_names=preferred_names,
                    workflow_stage=(
                        "submit_active_form" if ready_to_submit else "fill_active_form"
                    ),
                    workflow_phase="submit" if ready_to_submit else "write",
                    workflow_goal="form_write",
                    workflow_state=workflow_state,
                    completion_contract=_verify_only_contract(
                        ["ui_submit_form"]
                        if ready_to_submit
                        else ["ui_fill_form", "ui_set_field", "ui_submit_form"]
                    ),
                )
            allowed_names = [
                "ui_list_interactables",
                "ui_open_surface",
                "ui_click",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ]
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="discover_form_before_write",
                workflow_phase="discover",
                workflow_goal="form_write",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract(
                    ["ui_fill_form", "ui_set_field", "ui_submit_form"]
                ),
            )

        if intent_kind == "page_editor_read":
            allowed_names = [
                "ui_read_region",
                "ui_get_snapshot",
            ]
            return _plan(
                allowed_names=allowed_names,
                workflow_stage="read_editor_surface",
                workflow_phase="read",
                workflow_goal="editor_read",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract("ui_read_region"),
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
            if workflow_state.has_active_form:
                ready_to_submit = (
                    workflow_state.can_submit_form
                    or workflow_state.active_form_stage == "ready_to_submit"
                )
                return _plan(
                    allowed_names=allowed_names,
                    preferred_names=preferred_names,
                    workflow_stage=(
                        "submit_active_editor"
                        if ready_to_submit
                        else "edit_active_editor"
                    ),
                    workflow_phase="submit" if ready_to_submit else "write",
                    workflow_goal="editor_write",
                    workflow_state=workflow_state,
                    completion_contract=_verify_only_contract(
                        ["ui_submit_form"]
                        if ready_to_submit
                        else ["ui_fill_form", "ui_submit_form"]
                    ),
                )
            return _plan(
                allowed_names=allowed_names,
                preferred_names=preferred_names,
                workflow_stage="discover_editor_surface",
                workflow_phase="discover",
                workflow_goal="editor_write",
                workflow_state=workflow_state,
                completion_contract=_verify_only_contract(
                    ["ui_fill_form", "ui_submit_form"]
                ),
            )

        return _plan(
            allowed_names=[],
            preferred_names=[],
            workflow_stage="intent_static_tools",
            workflow_phase="idle",
            workflow_goal=intent_kind,
            workflow_state=workflow_state,
            completion_contract=PageIntentCompletionContract(
                mode="any_of",
                completion_signals=[],
                action_signals=[],
                verify_signals=[],
            ),
        )


__all__ = [
    "PageIntentCompletionContract",
    "PageIntentToolPlan",
    "PageWorkflowState",
    "PageWorkflowStateMachine",
]
