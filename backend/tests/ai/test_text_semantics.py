from app.ai.text_semantics import (
    extract_double_brace_placeholders,
    extract_first_json_object,
    extract_public_attachment_reference,
    extract_textual_tool_call_names,
    remove_trailing_json_commas,
    split_last_suffix,
    strip_model_function_call_markup,
)


def test_extract_textual_tool_call_names_detects_dsml_invoke_markup() -> None:
    names = extract_textual_tool_call_names(
        '<｜DSML｜tool_calls><｜DSML｜invoke name="crm_lookup"></｜DSML｜invoke></｜DSML｜tool_calls>',
        alias_to_tool_name={"crm_lookup": "crm_lookup"},
        known_tool_names={"crm_lookup"},
    )

    assert names == ["crm_lookup"]


def test_strip_model_function_call_markup_removes_dsml_tool_call_block() -> None:
    cleaned = strip_model_function_call_markup(
        '前面的内容 <｜DSML｜tool_calls><｜DSML｜invoke name="crm_lookup"><｜DSML｜parameter name="query">{"record_id":"x"}</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜tool_calls> 后面的内容'
    )

    assert cleaned == "前面的内容  后面的内容"


def test_extract_public_attachment_reference_accepts_relative_public_urls() -> None:
    attachment_id, token = extract_public_attachment_reference(
        "/api/public/attachments/42/access?token=test-token"
    )

    assert attachment_id == 42
    assert token == "test-token"


def test_extract_first_json_object_ignores_non_dict_candidates() -> None:
    payload = extract_first_json_object('answer [1, 2] {"ok": true, "value": 3}')

    assert payload == {"ok": True, "value": 3}


def test_remove_trailing_json_commas_keeps_string_commas() -> None:
    assert (
        remove_trailing_json_commas('{"a":"x, y","b":[1,2,],"c":{"d":3,},}')
        == '{"a":"x, y","b":[1,2],"c":{"d":3}}'
    )


def test_split_last_suffix_only_returns_allowed_suffix() -> None:
    assert split_last_suffix("gpt-4o-mini", allowed_suffixes={"mini", "nano"}) == (
        "gpt-4o",
        "mini",
    )
    assert split_last_suffix("gpt-4o-pro", allowed_suffixes={"mini", "nano"}) == (
        "gpt-4o-pro",
        None,
    )


def test_extract_double_brace_placeholders_keeps_unique_identifiers() -> None:
    assert extract_double_brace_placeholders(
        "{{ user_id }} {{user_id}} {{ tenant_id }}"
    ) == [
        "user_id",
        "tenant_id",
    ]
