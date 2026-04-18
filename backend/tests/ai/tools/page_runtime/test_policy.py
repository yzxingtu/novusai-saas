from app.ai.tools.page_runtime.policy import confirmation_guard


def test_confirmation_guard_blocks_delete_like_click_targets() -> None:
    result = confirmation_guard(
        arguments={"target_locator": "text:Delete supplier"},
        tool_name="ui_click",
    )

    assert result.allowed is False
    assert result.error_type == "confirmation_required"
    assert result.message == "Delete-like page actions require confirmation."
