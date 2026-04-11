from app.ai.tools.semantic_defaults import tool_family_from_name


def test_tool_family_from_name_recognizes_ui_page_tools() -> None:
    assert (
        tool_family_from_name(
            "ui_read_region",
            {
                "page_context": {"page_key": "admin.ai.agents"},
            },
        )
        == "page_ops"
    )


def test_tool_family_from_name_treats_ui_prefix_with_page_context_as_page_ops() -> None:
    assert (
        tool_family_from_name(
            "ui_custom_runtime_tool",
            {"page_context": {"page_key": "admin.ai.agents"}},
        )
        == "page_ops"
    )


def test_tool_family_from_name_list_page_operations_without_page_context_is_none() -> None:
    assert tool_family_from_name("list_page_operations", {}) == "none"
