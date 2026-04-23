"""Test type: behavioral
Scope: RecoveryResultNormalizer page-workflow compatibility labels for partial outputs
Real dependencies: IntentPlan and RecoveryResultNormalizer label selection logic
Mocked dependencies: none
"""

from app.ai.engine.recovery_result_normalizer import RecoveryResultNormalizer
from app.ai.engine.types import IntentPlan


def _page_intent(
    *,
    kind: str = "page_workflow",
    label: str,
    goal: str,
) -> IntentPlan:
    return IntentPlan(
        intent_id="intent-page",
        kind=kind,
        family="page_ops",
        order=1,
        user_visible_label=label,
        source_text="看看当前页面",
        status="pending",
        metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": goal,
            "page_workflow_phase": "read",
        },
    )


def test_partial_output_label_hides_canonical_page_workflow_machine_label() -> None:
    intent = _page_intent(label="page_workflow", goal="table_summary")

    assert RecoveryResultNormalizer._partial_output_label(intent) == "这部分"


def test_partial_output_label_hides_legacy_page_summary_machine_label() -> None:
    intent = _page_intent(
        kind="page_summary",
        label="page_summary",
        goal="page_summary",
    )

    assert RecoveryResultNormalizer._partial_output_label(intent) == "这部分"


def test_partial_output_label_preserves_human_page_workflow_label() -> None:
    intent = _page_intent(label="页面概览", goal="table_summary")

    assert RecoveryResultNormalizer._partial_output_label(intent) == "页面概览"
