from app.ai.tools.semantic_defaults import tool_family_from_name


def test_tool_family_from_name_does_not_expose_ui_page_tools() -> None:
    """
    Test type: structural
    Scope: ui_* names are no longer classified as live page_ops tools.
    """
    assert (
        tool_family_from_name(
            "ui_read_region",
            {
                "page_context": {"page_key": "admin.ai.agents"},
            },
        )
        == "none"
    )


def test_tool_family_from_name_does_not_promote_ui_prefix_with_page_context() -> None:
    """
    Test type: structural
    Scope: page_context no longer promotes arbitrary ui_* names to page_ops.
    """
    assert (
        tool_family_from_name(
            "ui_custom_runtime_tool",
            {"page_context": {"page_key": "admin.ai.agents"}},
        )
        == "none"
    )


def test_tool_family_from_name_list_page_operations_without_page_context_is_none() -> None:
    assert tool_family_from_name("list_page_operations", {}) == "none"
