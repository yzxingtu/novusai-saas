"""
Test type: behavioral
Scope: Page-intent routing and continuation behavior with page-workflow metadata.
Mocked dependencies: none.
"""

from types import SimpleNamespace

from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
    looks_like_page_follow_up,
)


def _continuation_context(**overrides):
    payload = {
        "active": True,
        "continuation_capable_families": ["page_ops"],
        "family": "page_ops",
        "active_intent_kind": "page_workflow",
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
    }
    page_context.update(extra)
    return page_context


def _runtime_page_intent(
    *,
    kind: str = "page_workflow",
    workflow_goal: str,
    source_text: str = "继续看看",
) -> dict:
    return {
        "intent_id": "intent-1",
        "kind": kind,
        "family": "page_ops",
        "order": 1,
        "user_visible_label": "page_workflow",
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
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is True
    assert signal.metadata.get("continuation_source") == "page_ops"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_continuation_guard"
    assert signal.metadata.get("page_workflow_kind") == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"
    assert set(signal.metadata) == {
        "continuation_source",
        "routing_mode",
        "routing_provenance",
        "page_workflow_kind",
        "page_workflow_goal",
    }
    assert "page_workflow_intent_alias" not in signal.metadata


def test_detect_page_continuation_signal_prefers_screenshot() -> None:
    signal = detect_page_continuation_signal(
        clause="截个图看",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is True
    assert signal.metadata.get("page_workflow_goal") == "page_screenshot"


def test_detect_page_continuation_signal_prefers_row_detail_with_ui_tools() -> None:
    signal = detect_page_continuation_signal(
        clause="看这个区域",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("page_workflow_goal") == "row_detail"


def test_detect_page_continuation_signal_routes_click_follow_up_to_navigation() -> None:
    signal = detect_page_continuation_signal(
        clause="点击一下添加供应商",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("page_workflow_goal") == "navigation"


def test_detect_page_continuation_signal_uses_runtime_page_workflow_metadata() -> None:
    signal = detect_page_continuation_signal(
        clause="继续看看",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.logs"),
            "_runtime_intent_plan": [
                _runtime_page_intent(
                    workflow_goal="pagination",
                    source_text="把列表翻到下一页",
                )
            ],
            "_runtime_intent_facts": {"active_intent_kind": "page_workflow"},
        },
        continuation_context=_continuation_context(active_intent_kind="page_workflow"),
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("page_workflow_kind") == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "pagination"
    assert "page_workflow_intent_alias" not in signal.metadata


def test_detect_page_signal_uses_page_reference_search_phrasing_as_summary_fallback() -> (
    None
):
    signal = detect_page_signal(
        clause="在页面里搜索张三",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"


def test_detect_page_signal_routes_table_summary_to_canonical_workflow_goal() -> None:
    signal = detect_page_signal(
        clause="列出这个表格前5条标题和时间",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is True
    assert signal.metadata.get("routing_mode") == "structured_semantic"
    assert signal.metadata.get("routing_provenance") == "page_workflow_semantic_profile"
    assert signal.metadata.get("page_workflow_goal") == "table_summary"


def test_detect_page_signal_uses_navigation_catalog_semantics() -> None:
    signal = detect_page_signal(
        clause="添加供应商",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context(
                "admin.runtime.records",
                page_data={
                    "navigation_catalog": [
                        {
                            "title": "供应商管理",
                            "path": "/admin/suppliers",
                            "page_key": "admin.suppliers",
                            "description": "管理供应商并新增供应商",
                            "keywords": ["供应商", "添加供应商"],
                        }
                    ]
                },
            )
        },
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("routing_mode") == "structured_semantic"
    assert signal.metadata.get("routing_provenance") == "navigation_catalog_semantics"
    assert signal.metadata.get("page_workflow_goal") == "navigation"
    assert set(signal.metadata) == {
        "routing_mode",
        "routing_provenance",
        "page_workflow_kind",
        "page_workflow_goal",
    }


def test_detect_page_signal_routes_explicit_current_page_create_request_to_write_goal() -> (
    None
):
    signal = detect_page_signal(
        clause="在当前页面创建一条测试记录，名称叫 Consent-Recovery-E2E",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.skill-packages")
        },
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("routing_mode") == "structured_semantic"
    assert signal.metadata.get("routing_provenance") == "page_reference_write_semantics"
    assert signal.metadata.get("page_workflow_goal") == "form_write"
    assert set(signal.metadata) == {
        "routing_mode",
        "routing_provenance",
        "page_workflow_kind",
        "page_workflow_goal",
    }


def test_detect_page_signal_routes_explicit_page_record_shape_write_to_form_write() -> None:
    signal = detect_page_signal(
        clause="请帮我在这个页面编辑一条限速规则",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.quotas")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is False
    assert signal.metadata.get("routing_mode") == "structured_semantic"
    assert signal.metadata.get("routing_provenance") == "page_reference_write_semantics"
    assert signal.metadata.get("page_workflow_goal") == "form_write"


def test_detect_page_signal_supports_code_mixed_page_reference() -> None:
    signal = detect_page_signal(
        clause="这个page上有啥东西",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"


def test_detect_page_signal_treats_colloquial_here_question_as_current_page_reference() -> None:
    signal = detect_page_signal(
        clause="这里都有啥？",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.shortcircuit is True
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"


def test_detect_page_signal_marks_page_reference_analysis_as_fallback_summary() -> None:
    signal = detect_page_signal(
        clause="请解释一下当前页面的配额和限速差异",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.quotas")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"


def test_detect_page_signal_routes_form_read_from_readonly_state_request() -> None:
    signal = detect_page_signal(
        clause="先不要创建，查看表单状态",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.form")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "form_read"
    assert signal.metadata.get("routing_provenance") == "active_page_action_semantics"


def test_detect_page_signal_treats_skill_binding_with_page_reference_as_summary() -> (
    None
):
    signal = detect_page_signal(
        clause="帮我给这个页面的智能体绑定几个技能测试一下",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.agent.detail")
        },
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "page_summary"
    assert signal.metadata.get("routing_provenance") == "page_reference_fallback"


def test_detect_page_signal_does_not_infer_form_write_from_add_vendor_request() -> None:
    signal = detect_page_signal(
        clause="帮我点击一下添加供应商 添加一个测试的供应商",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
    )

    assert signal is None


def test_detect_page_signal_routes_form_read_from_active_form_field_listing() -> (
    None
):
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
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "form_read"
    assert signal.metadata.get("routing_provenance") == "active_page_action_semantics"


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


def test_detect_page_signal_routes_pagination_from_active_page_phrase() -> None:
    signal = detect_page_signal(
        clause="下一页",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "pagination"
    assert signal.metadata.get("routing_provenance") == "active_page_action_semantics"


def test_detect_page_signal_routes_row_detail_from_active_page_phrase() -> (
    None
):
    signal = detect_page_signal(
        clause="帮我看看第一条记录的详细信息",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "row_detail"
    assert signal.metadata.get("routing_provenance") == "page_workflow_semantic_profile"


def test_detect_page_signal_routes_search_from_active_page_phrase() -> None:
    signal = detect_page_signal(
        clause="请帮我搜索记录并清空筛选条件",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "search"
    assert signal.metadata.get("routing_provenance") == "active_page_action_semantics"


def test_detect_page_signal_routes_form_write_from_active_page_phrase() -> None:
    signal = detect_page_signal(
        clause="请帮我新增一条记录",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.ai.skills")},
    )

    assert signal is not None
    assert signal.kind == "page_workflow"
    assert signal.metadata.get("page_workflow_goal") == "form_write"
    assert signal.metadata.get("routing_provenance") == "active_page_action_semantics"


def test_detect_page_signal_does_not_special_case_business_nouns_as_page_detail() -> (
    None
):
    signal = detect_page_signal(
        clause="帮我看看这个对话的详细信息",
        offset=0,
        input_variables={"page_context": _runtime_page_context("admin.runtime.records")},
    )

    assert signal is None


def test_detect_page_signal_does_not_special_case_admin_ai_conversations_page() -> (
    None
):
    signal = detect_page_signal(
        clause="帮我看看这个对话的详细信息",
        offset=0,
        input_variables={
            "page_context": _runtime_page_context("admin.ai.conversations")
        },
    )

    assert signal is None


def test_page_follow_up_helper_covers_bounded_generic_actions() -> None:
    assert looks_like_page_follow_up("继续看看") is True
    assert looks_like_page_follow_up("点击一下") is True
    assert looks_like_page_follow_up("截个图看") is True
    assert looks_like_page_follow_up("这里都有啥？") is False
