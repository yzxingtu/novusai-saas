from app.ai.tools.executors.http_executor import _substitute_template


def test_substitute_template_replaces_double_brace_variables() -> None:
    rendered = _substitute_template(
        "https://api.example.com/{{ tenant_id }}/items/{{item_id}}",
        {"tenant_id": 7, "item_id": "abc"},
    )

    assert rendered == "https://api.example.com/7/items/abc"


def test_substitute_template_keeps_invalid_or_missing_placeholders() -> None:
    rendered = _substitute_template(
        "{{ valid_key }} {{ missing_key }} {{ invalid-key }} {{ unterminated",
        {"valid_key": "ok"},
    )

    assert rendered == "ok {{ missing_key }} {{ invalid-key }} {{ unterminated"
