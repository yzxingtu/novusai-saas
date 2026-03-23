from __future__ import annotations

from typing import Any


def extract_snapshot(source: Any) -> dict[str, Any]:
    for field_name in ("workflow_json", "snapshot_json", "definition_json"):
        payload = getattr(source, field_name, None)
        if isinstance(payload, dict):
            return payload
    for field_name in ("control_envelope_json", "settings_json", "metadata_json"):
        payload = getattr(source, field_name, None)
        if not isinstance(payload, dict):
            continue
        for nested_field in ("workflow_snapshot", "snapshot_json", "workflow_json", "draft_snapshot"):
            nested_payload = payload.get(nested_field)
            if isinstance(nested_payload, dict):
                return nested_payload
    return {}


def build_graph(snapshot: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    edges = []

    raw_nodes = snapshot.get("nodes") or snapshot.get("workflow_nodes") or []
    raw_edges = snapshot.get("edges") or snapshot.get("workflow_edges") or []

    for entry in raw_nodes:
        if not isinstance(entry, dict):
            continue
        node_key = str(
            entry.get("node_key")
            or entry.get("key")
            or entry.get("id")
            or ""
        ).strip()
        if not node_key:
            continue
        nodes.append(
            {
                "node_key": node_key,
                "node_type": entry.get("node_type") or entry.get("type") or "system",
                "executor_type": entry.get("executor_type") or infer_executor_type(entry),
                "executor_ref": entry.get("executor_ref"),
                "config": entry.get("config") or {},
                "depends_on": list(entry.get("depends_on") or []),
                "timeout_seconds": entry.get("timeout_seconds"),
                "retry_policy": entry.get("retry_policy") or {},
                "risk_level": entry.get("risk_level"),
            }
        )

    for entry in raw_edges:
        if not isinstance(entry, dict):
            continue
        source_key = str(
            entry.get("source_node_key")
            or entry.get("source")
            or entry.get("from")
            or ""
        ).strip()
        target_key = str(
            entry.get("target_node_key")
            or entry.get("target")
            or entry.get("to")
            or ""
        ).strip()
        if not source_key or not target_key:
            continue
        edges.append(
            {
                "source_node_key": source_key,
                "target_node_key": target_key,
                "edge_type": entry.get("edge_type") or "sequential",
                "condition_expr": entry.get("condition_expr"),
                "label": entry.get("label"),
            }
        )

    dependencies: dict[str, set[str]] = {node["node_key"]: set(node.get("depends_on") or []) for node in nodes}
    for edge in edges:
        dependencies.setdefault(edge["target_node_key"], set()).add(edge["source_node_key"])

    root_nodes: list[str] = []
    for node in nodes:
        node_key = node["node_key"]
        upstream = sorted(dependencies.get(node_key, set()))
        node["depends_on"] = upstream
        node["initial_status"] = "ready" if not upstream else "pending"
        if not upstream:
            root_nodes.append(node_key)

    return {
        "nodes": nodes,
        "edges": edges,
        "root_node_keys": root_nodes,
    }


def infer_executor_type(node_definition: dict[str, Any]) -> str:
    node_type = str(node_definition.get("node_type") or node_definition.get("type") or "system")
    if node_type in {"llm", "rewrite", "generate"}:
        return "llm"
    if node_type in {"tool", "http", "api"}:
        return "tool"
    if node_type in {"planner", "branch_planner"}:
        return "planner"
    if node_type in {"approval", "human_review"}:
        return "approval"
    return "system"


def summarize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    graph = build_graph(snapshot)
    node_types = sorted({node["node_type"] for node in graph["nodes"]})
    return {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "root_node_count": len(graph["root_node_keys"]),
        "node_types": node_types,
        "has_parallel": len(graph["root_node_keys"]) > 1,
        "has_agentic": "planner" in node_types or "agentic" in node_types,
    }
