"""Tool definitions for page-runtime ui_* tools."""

from __future__ import annotations

from app.ai.tools.types import ToolDefinition, ToolParameter


def build_page_runtime_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="ui_read_page",
            description="Read the current page summary-first snapshot.",
            parameters=[
                ToolParameter(
                    name="ui_epoch",
                    type="integer",
                    description="Expected ui_epoch for stale-context protection.",
                ),
            ],
        ),
        ToolDefinition(
            name="ui_get_snapshot",
            description="Compatibility alias for reading the current page snapshot.",
            parameters=[
                ToolParameter(
                    name="ui_epoch",
                    type="integer",
                    description="Expected ui_epoch for stale-context protection.",
                ),
            ],
        ),
        ToolDefinition(
            name="ui_read_surface",
            description="Read one surface deeply by surface_id.",
            parameters=[
                ToolParameter(
                    name="surface_id",
                    description="Surface id to read.",
                    required=True,
                ),
                ToolParameter(
                    name="ui_epoch",
                    type="integer",
                    description="Expected ui_epoch for stale-context protection.",
                ),
            ],
        ),
        ToolDefinition(
            name="ui_read_region",
            description="Read a UI region by locator.",
            parameters=[
                ToolParameter(name="locator", description="UI locator.", required=True),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_read_table",
            description="Read a UI table by locator.",
            parameters=[
                ToolParameter(name="locator", description="UI locator.", required=True),
                ToolParameter(name="page", type="integer"),
                ToolParameter(name="page_size", type="integer"),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_list_interactables",
            description="List visible interactables in the current page or surface.",
            parameters=[
                ToolParameter(name="surface_id", description="Optional surface id."),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_get_form_state",
            description="Read the current form-session state.",
            parameters=[
                ToolParameter(name="form_session_id", description="Optional form session id."),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_click",
            description="Click a UI element by locator.",
            parameters=[
                ToolParameter(
                    name="target_locator",
                    description="Locator of the element to click.",
                    required=True,
                ),
                ToolParameter(name="confirm", type="boolean"),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_open_surface",
            description="Open a drawer, modal, dropdown, or popover.",
            parameters=[
                ToolParameter(name="target_locator", description="Fallback target locator."),
                ToolParameter(name="surface", type="object"),
                ToolParameter(name="confirm", type="boolean"),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_set_field",
            description="Set a single form field.",
            parameters=[
                ToolParameter(name="field_name", description="Field name.", required=True),
                ToolParameter(name="value", type="string"),
                ToolParameter(name="form_session_id", description="Optional form session id."),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_fill_form",
            description="Fill one or more form fields.",
            parameters=[
                ToolParameter(name="fields", type="object", required=True),
                ToolParameter(name="form_session_id", description="Optional form session id."),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
        ToolDefinition(
            name="ui_submit_form",
            description="Submit the active form session.",
            parameters=[
                ToolParameter(name="form_session_id", description="Optional form session id."),
                ToolParameter(name="confirm", type="boolean"),
                ToolParameter(name="ui_epoch", type="integer"),
            ],
        ),
    ]

