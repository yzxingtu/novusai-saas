"""Test type: behavioral
Scope: RecoveryResultNormalizer data-workflow compatibility labels for partial outputs
Real dependencies: IntentPlan and RecoveryResultNormalizer label selection logic
Mocked dependencies: none
"""

from app.ai.engine.recovery_result_normalizer import RecoveryResultNormalizer
from app.ai.engine.types import IntentPlan


def _page_intent(
    *,
    kind: str = "data_workflow",
    label: str,
    goal: str,
) -> IntentPlan:
    return IntentPlan(
        intent_id="intent-page",
        kind=kind,
        family="data_ops",
        order=1,
        user_visible_label=label,
        source_text="看看当前数据集",
        status="pending",
        metadata={
            "data_workflow_kind": "data_workflow",
            "data_workflow_goal": goal,
            "data_workflow_phase": "read",
        },
    )


def test_partial_output_label_hides_canonical_data_workflow_machine_label() -> None:
    intent = _page_intent(label="data_workflow", goal="table_summary")

    assert RecoveryResultNormalizer._partial_output_label(intent) == "这部分"


def test_partial_output_label_hides_invalid_runtime_summary_machine_label() -> None:
    intent = _page_intent(
        kind="page_summary",
        label="page_summary",
        goal="page_summary",
    )

    assert RecoveryResultNormalizer._partial_output_label(intent) == "这部分"


def test_partial_output_label_preserves_human_data_workflow_label() -> None:
    intent = _page_intent(label="页面概览", goal="table_summary")

    assert RecoveryResultNormalizer._partial_output_label(intent) == "页面概览"
