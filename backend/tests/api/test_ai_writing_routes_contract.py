"""Test type: structural / behavioral
Scope: retired rich-text AI writing route exposure and global AgentChat message contract.
Real dependencies: FastAPI router registration, Pydantic schemas, and rich-text message builder.
Mocked dependencies: none.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.admin import ai_writing as admin_ai_writing_module
from app.api.tenant import ai_writing as tenant_ai_writing_module
from app.schemas.ai.agent_chat import AgentChatRequest
from app.services.ai.writing_service import build_rich_text_agent_chat_message

_RETIRED_PATHS = {
    "/ai/writing/{feature}",
    "/ai/rich-text/operations/{action}",
}


def _route_paths(router) -> set[str]:
    return {str(getattr(route, "path", "")) for route in router.routes}


def test_admin_and_tenant_ai_writing_modules_no_longer_register_runtime_routes() -> (
    None
):
    assert _RETIRED_PATHS.isdisjoint(_route_paths(admin_ai_writing_module.router))
    assert _RETIRED_PATHS.isdisjoint(_route_paths(tenant_ai_writing_module.router))
    assert _route_paths(admin_ai_writing_module.router) == set()
    assert _route_paths(tenant_ai_writing_module.router) == set()


def test_admin_and_tenant_aggregate_routers_do_not_expose_retired_ai_writing_paths() -> (
    None
):
    from app.api.admin import admin_router
    from app.api.tenant import tenant_router

    assert _RETIRED_PATHS.isdisjoint(_route_paths(admin_router))
    assert _RETIRED_PATHS.isdisjoint(_route_paths(tenant_router))
    assert "/ai/agent-chat/{agent_id}/chat/stream" in _route_paths(admin_router)
    assert "/ai/agent-chat/{agent_id}/chat/stream" in _route_paths(tenant_router)


@pytest.mark.parametrize(
    "schema_cls",
    [
        admin_ai_writing_module.AIWritingRequest,
        tenant_ai_writing_module.AIWritingRequest,
    ],
)
def test_internal_ai_writing_request_rejects_page_context_fields(schema_cls) -> None:
    with pytest.raises(ValidationError) as exc_info:
        schema_cls.model_validate(
            {
                "selected_text": "hello",
                "page_context": {"url": "/admin/plugins/novusdoc/editor/9"},
            }
        )

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("page_context",)
    assert errors[0]["input"] == {"url": "/admin/plugins/novusdoc/editor/9"}


def test_internal_ai_writing_request_accepts_explicit_editor_payload() -> None:
    payload = admin_ai_writing_module.AIWritingRequest.model_validate(
        {
            "selected_text": "原文",
            "selection_html": "<p>原文</p>",
            "before_text": "前文",
            "after_text": "后文",
            "document_title": "Demo Doc",
            "document_id": 9,
            "surface": "novusdoc.editor",
            "format_instruction": "use bullet list",
        }
    )

    assert payload.document_id == 9
    assert payload.surface == "novusdoc.editor"
    assert payload.format_instruction == "use bullet list"
    assert payload.selection_html == "<p>原文</p>"


def test_global_agent_chat_request_accepts_rendered_rich_text_operation_message() -> (
    None
):
    message = build_rich_text_agent_chat_message(
        "continue",
        {
            "before_text": "第一段内容",
            "after_text": "后一段内容",
            "document_title": "Demo Doc",
            "instruction": "自然续写一段",
        },
    )

    request = AgentChatRequest.model_validate(
        {
            "message": message,
            "selected_skill_names": ["novusdoc.rich_text_ai.actions"],
        }
    )

    assert request.message == message
    assert request.selected_skill_names == ["novusdoc.rich_text_ai.actions"]
    assert "[User Request]" in request.message
    assert "自然续写一段" in request.message
    assert request.variables is None
    assert not hasattr(request, "page_context")
