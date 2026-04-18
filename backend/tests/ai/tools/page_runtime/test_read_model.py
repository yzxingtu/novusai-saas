from app.ai.tools.page_runtime import build_read_page_result


def test_build_read_page_result_returns_thin_runtime_summary() -> None:
    result = build_read_page_result(
        {
            "page_key": "admin.ai.agents",
            "page_title": "Agents",
            "ui_epoch": 12,
            "active_surface_id": "drawer:editor",
            "surface_stack": [
                {"surface_id": "page:agents", "kind": "page", "title": "Agents"},
                {"surface_id": "drawer:editor", "kind": "drawer", "title": "Editor"},
                {"surface_id": "drawer:editor", "kind": "drawer", "title": "Duplicate"},
            ],
            "active_form_summary": {
                "form_session_id": "form-1",
                "entity_name": "Agent",
            },
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_fill_form"],
            },
        },
        snapshot={
            "interactables_count": 9,
        },
    )

    assert result == {
        "active_form_summary": {
            "form_session_id": "form-1",
            "entity_name": "Agent",
        },
        "active_surface_id": "drawer:editor",
        "interactables_count": 9,
        "page_key": "admin.ai.agents",
        "page_title": "Agents",
        "suggested_tools": {
            "primary": ["ui_get_snapshot", "ui_fill_form"],
        },
        "surface_stack": [
            {"surface_id": "page:agents", "kind": "page", "title": "Agents"},
            {"surface_id": "drawer:editor", "kind": "drawer", "title": "Editor"},
        ],
        "ui_epoch": 12,
    }


def test_build_read_page_result_falls_back_to_snapshot_when_page_context_missing() -> None:
    result = build_read_page_result(
        None,
        snapshot={
            "active_surface_id": "page:agents",
            "interactables_count": 3,
            "surface_stack": [
                {"surface_id": "page:agents", "kind": "page", "title": "Agents"},
            ],
            "ui_epoch": 5,
        },
    )

    assert result["page_key"] == ""
    assert result["active_surface_id"] == "page:agents"
    assert result["interactables_count"] == 3
    assert result["ui_epoch"] == 5
