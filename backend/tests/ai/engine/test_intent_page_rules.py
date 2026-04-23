"""
Test type: behavioral
Scope: Page-intent routing and continuation behavior with page-workflow metadata.
Mocked dependencies: none.
"""

from types import SimpleNamespace

from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
    looks_like_page_jump_request,
    looks_like_page_search_request,
    looks_like_read_only_form_instruction,
    looks_like_required_field_form_read,
)


def _continuation_context(**overrides):
    payload = {
        "continuation_capable_families": ["page_ops"],
        "family": "page_ops",
        "active_intent_kind": "page_summary",
        "last_tool_name": "ui_get_snapshot",
        "tool_families": ["page_ops"],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _runtime_page_context(page_key: str, **extra):
    page_context = {
        "page_key": page_key,
        "page_session_id": f"{page_key}-session",
        "ui_epoch": 1,
        "suggested_tools": {
            "primary": [
                "ui_get_snapshot",
                "ui_read_region",
                "ui_read_table",
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ]
        },
    }
    page_context.update(extra)
    return page_context


def _runtime_page_intent(
    *,
    kind: str = "page_workflow",
    workflow_goal: str,
    workflow_alias: str,
    source_text: str = "继续看看",
) -> dict:
    return {
        "intent_id": "intent-1",
        "kind": kind,
        "family": "page_ops",
        "order": 1,
        "user_visible_label": workflow_alias,
        "source_text": source_text,
        "status": "pending",
        "requires_tools": True,
        "allow_text_response": False,
        "continuation": False,
        "shortcircuit": workflow_goal == "page_summary",
        "metadata": {
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": workflow_goal,
        },
    }


def test_detect_page_continuation_signal_returns_page_summary() -> None:
    signal = detect_page_continuation_signal(
        clause="继续看看",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_summary"
    assert signal.shortcircuit is True
    assert signal.metadata.get("continuation_source") == "page_ops"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_continuation_guard"
    assert signal.metadata.get("page_workflow_kind") == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"
    assert "page_workflow_intent_alias" not in signal.metadata


def test_detect_page_continuation_signal_prefers_screenshot() -> None:
    signal = detect_page_continuation_signal(
        clause="截个图看",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_screenshot"
    assert signal.shortcircuit is False


def test_detect_page_continuation_signal_prefers_row_detail_with_ui_tools() -> None:
    signal = detect_page_continuation_signal(
        clause="看这个区域",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_row_detail"
    assert signal.shortcircuit is False


def test_detect_page_continuation_signal_routes_click_follow_up_to_navigation() -> (
    None
):
    signal = detect_page_continuation_signal(
        clause="点击一下添加供应商",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_navigation"
    assert signal.shortcircuit is False


def test_detect_page_continuation_signal_uses_runtime_page_workflow_metadata() -> None:
    signal = detect_page_continuation_signal(
        clause="继续看看",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.logs"),
            "_runtime_intent_plan": [
                _runtime_page_intent(
                    workflow_goal="pagination",
                    workflow_alias="page_pagination",
                    source_text="把列表翻到下一页",
                )
            ],
            "_runtime_intent_facts": {"active_intent_kind": "page_workflow"},
        },
        continuation_context=_continuation_context(active_intent_kind="page_workflow"),
    )

    assert signal is not None
    assert signal.kind == "page_pagination"
    assert signal.shortcircuit is False
    assert signal.metadata.get("page_workflow_kind") == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "pagination"
    assert "page_workflow_intent_alias" not in signal.metadata


def test_detect_page_signal_selects_page_search() -> None:
    signal = detect_page_signal(
        clause="在页面里搜索张三",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_search"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_search_shortcircuit"
    assert signal.metadata.get("page_workflow_kind") == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "search"


def test_detect_page_signal_treats_colloquial_here_question_as_page_summary() -> None:
    signal = detect_page_signal(
        clause="这里都有啥？",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_summary"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_summary_shortcircuit"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"
    assert "page_workflow_intent_alias" not in signal.metadata


def test_detect_page_signal_marks_page_reference_analysis_as_fallback_summary() -> None:
    signal = detect_page_signal(
        clause="请解释一下当前页面的配额和限速差异",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.quotas")},
    )

    assert signal is not None
    assert signal.kind == "page_summary"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"


def test_detect_page_signal_respects_readonly_form_hint() -> None:
    signal = detect_page_signal(
        clause="先不要创建，查看表单状态",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.form")},
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_treats_required_field_probe_as_form_read() -> None:
    signal = detect_page_signal(
        clause="请帮我点击添加技能，看看表单里有哪些必填项，但不要提交",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.skills")},
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_treats_skill_binding_as_form_write() -> None:
    signal = detect_page_signal(
        clause="帮我给这个页面的智能体绑定几个技能测试一下",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.agent.detail")
        },
    )

    assert signal is not None
    assert signal.kind == "page_form_write"
    assert signal.metadata.get("page_workflow_goal") == "form_write"


def test_detect_page_signal_treats_specific_add_vendor_request_as_form_write() -> None:
    signal = detect_page_signal(
        clause="帮我点击一下添加供应商 添加一个测试的供应商",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
    )

    assert signal is not None
    assert signal.kind == "page_form_write"


def test_detect_page_signal_treats_active_form_field_listing_as_form_read() -> None:
    signal = detect_page_signal(
        clause="当前有哪些字段",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context(
                "admin.ai.skills",
                active_form_session_id="form-session-1",
            )
        },
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_ignores_explicit_external_url_request() -> None:
    signal = detect_page_signal(
        clause="请打开 https://docs.python.org/3/whatsnew/3.13.html 并概括重点",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is None


def test_detect_page_signal_ignores_negated_page_reference_for_explicit_url_request() -> (
    None
):
    signal = detect_page_signal(
        clause=(
            "必须只使用 fetch_url 抓取 https://example.com ，"
            "不要联网搜索，也不要参考当前页面"
        ),
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is None


def test_detect_page_signal_selects_page_pagination() -> None:
    signal = detect_page_signal(
        clause="下一页",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_pagination"


def test_detect_page_signal_selects_page_pagination_for_jump_to_numbered_page() -> None:
    signal = detect_page_signal(
        clause="翻到第3页",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_pagination"


def test_detect_page_signal_selects_row_detail_for_detailed_info_phrase() -> None:
    signal = detect_page_signal(
        clause="帮我看看第一条记录的详细信息",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_row_detail"
    assert signal.metadata.get("page_workflow_goal") == "row_detail"


def test_page_rule_helpers_cover_jump_search_readonly() -> None:
    assert looks_like_page_jump_request("下一页")
    assert looks_like_page_search_request("在页面里搜索")
    assert looks_like_read_only_form_instruction("先不要创建")
    assert looks_like_required_field_form_read("看看表单里有哪些必填项")

