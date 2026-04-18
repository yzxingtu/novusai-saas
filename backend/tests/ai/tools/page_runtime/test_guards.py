from app.ai.tools.page_runtime import detect_guard_failure
from app.ai.tools.page_runtime.guards import (
    classify_sensitive_field,
    requires_confirmation,
    validate_ui_epoch,
)


def test_validate_ui_epoch_returns_stale_context_on_mismatch() -> None:
    result = validate_ui_epoch(4, 7)

    assert result == {
        "data": {
            "actual_ui_epoch": 7,
            "expected_ui_epoch": 4,
        },
        "error_type": "stale_context",
        "message": "UI context is stale. Read the page again before acting.",
    }


def test_requires_confirmation_for_submit_and_destructive_navigation() -> None:
    submit_result = requires_confirmation("ui_submit_form")
    delete_nav_result = requires_confirmation(
        "ui_navigate", target_hint="Delete user"
    )

    assert submit_result["error_type"] == "confirmation_required"
    assert delete_nav_result["error_type"] == "confirmation_required"


def test_classify_sensitive_field_blocks_password_and_token_inputs() -> None:
    assert classify_sensitive_field(field_type="password") == "password"
    assert classify_sensitive_field(field_name="api_token") == "token"
    assert classify_sensitive_field(field_name="verification_code") == "captcha"


def test_detect_guard_failure_prefers_stale_context_then_field_policy() -> None:
    stale_result = detect_guard_failure(
        action_name="ui_fill_form",
        actual_ui_epoch=8,
        expected_ui_epoch=3,
        field_name="password",
        field_type="password",
    )
    field_result = detect_guard_failure(
        action_name="ui_fill_form",
        actual_ui_epoch=5,
        expected_ui_epoch=5,
        field_name="password",
        field_type="password",
    )

    assert stale_result["error_type"] == "stale_context"
    assert field_result["error_type"] == "forbidden"
