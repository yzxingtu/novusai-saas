from app.ai.tools.semantic_defaults import tool_family_from_name


def test_tool_family_from_name_uses_page_context_key() -> None:
    assert (
        tool_family_from_name(
            "list_page_operations",
            {
                "page_context": {"page_key": "admin.ai.agents"},
            },
        )
        == "page_ops"
    )


def test_tool_family_from_name_treats_pageop_prefix_as_page_ops() -> None:
    assert tool_family_from_name("pageop_read_visible_rows", {}) == "page_ops"


def test_tool_family_from_name_list_page_operations_without_page_context_is_none() -> None:
    assert tool_family_from_name("list_page_operations", {}) == "none"
