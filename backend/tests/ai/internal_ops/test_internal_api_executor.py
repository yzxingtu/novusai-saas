import json
from types import SimpleNamespace

from app.ai.tools.executors import internal_api_executor
from app.ai.tools.executors.internal_api_executor import InternalApiExecutor


def test_list_operations_empty_result_tells_model_to_stop_after_retry(
    monkeypatch,
) -> None:
    """Test type: behavioral; empty internal_ops searches must steer ReAct exit."""

    def fake_search_operations(**_kwargs):
        return [], 0

    monkeypatch.setattr(
        internal_api_executor,
        "search_operations",
        fake_search_operations,
    )

    result = InternalApiExecutor()._list_operations(
        "call_list",
        {"keyword": "agents"},
        SimpleNamespace(permissions={"*"}),
        "admin",
    )

    payload = json.loads(result.output)
    assert result.success is True
    assert payload["total"] == 0
    assert payload["empty_result"] is True
    assert payload["should_stop_searching"] is True
    assert payload["recommended_next_action"].startswith(
        "Stop calling list_internal_operations"
    )
    assert "permission_scope_has_no_matching_operation" in payload["possible_reasons"]
