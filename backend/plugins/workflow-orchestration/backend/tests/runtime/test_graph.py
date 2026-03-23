from __future__ import annotations


def test_build_graph_normalizes_nodes_edges_and_dependencies(load_plugin_backend_module) -> None:
    graph = load_plugin_backend_module("runtime.graph")

    snapshot = {
        "nodes": [
            {"id": "start", "type": "planner"},
            {"node_key": "llm_step", "node_type": "llm"},
            {"key": "approve", "type": "approval", "depends_on": ["start"]},
        ],
        "edges": [
            {"source": "start", "target": "llm_step"},
            {"source_node_key": "llm_step", "target_node_key": "approve"},
        ],
    }

    result = graph.build_graph(snapshot)
    nodes_by_key = {item["node_key"]: item for item in result["nodes"]}

    assert result["root_node_keys"] == ["start"]
    assert nodes_by_key["start"]["initial_status"] == "ready"
    assert nodes_by_key["llm_step"]["depends_on"] == ["start"]
    assert nodes_by_key["approve"]["depends_on"] == ["llm_step", "start"]
    assert nodes_by_key["approve"]["executor_type"] == "approval"


def test_summarize_snapshot_marks_parallel_and_agentic(load_plugin_backend_module) -> None:
    graph = load_plugin_backend_module("runtime.graph")

    summary = graph.summarize_snapshot(
        {
            "nodes": [
                {"id": "a", "type": "planner"},
                {"id": "b", "type": "tool"},
            ],
            "edges": [],
        }
    )

    assert summary["node_count"] == 2
    assert summary["edge_count"] == 0
    assert summary["root_node_count"] == 2
    assert summary["has_parallel"] is True
    assert summary["has_agentic"] is True


def test_infer_executor_type_maps_known_types(load_plugin_backend_module) -> None:
    graph = load_plugin_backend_module("runtime.graph")

    assert graph.infer_executor_type({"type": "llm"}) == "llm"
    assert graph.infer_executor_type({"type": "api"}) == "tool"
    assert graph.infer_executor_type({"type": "human_review"}) == "approval"
    assert graph.infer_executor_type({"type": "noop"}) == "system"
