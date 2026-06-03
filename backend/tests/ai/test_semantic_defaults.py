from app.ai.tools.semantic_defaults import tool_family_from_name


def test_tool_family_from_name_does_not_expose_ui_page_tools() -> None:
    """
    Test type: structural
    Scope: ordinary record helper names are not promoted by arbitrary context.
    """
    assert (
        tool_family_from_name(
            "crm_read_record",
            {
                "business_context": {"record_id": "crm-1"},
            },
        )
        == "none"
    )


def test_tool_family_from_name_does_not_promote_unknown_runtime_prefix() -> None:
    """
    Test type: structural
    Scope: arbitrary runtime names are not promoted by context.
    """
    assert (
        tool_family_from_name(
            "custom_runtime_tool",
            {"business_context": {"record_id": "crm-1"}},
        )
        == "none"
    )
