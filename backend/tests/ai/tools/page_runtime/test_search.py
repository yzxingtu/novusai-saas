from app.ai.tools.page_runtime import (
    resolve_navigation_candidates,
    search_runtime_snapshot,
)


def test_search_runtime_snapshot_returns_ranked_hits() -> None:
    hits = search_runtime_snapshot(
        {
            "nodes": [
                {
                    "kind": "button",
                    "locator": "testid:create-agent",
                    "summary": "Create agent",
                    "surface_id": "page:agents",
                },
                {
                    "kind": "table",
                    "locator": "testid:agent-table",
                    "content": "Agent Alice GPT-5 enabled",
                    "surface_id": "page:agents",
                },
            ]
        },
        "agent",
    )

    assert [hit["locator"] for hit in hits] == [
        "testid:agent-table",
        "testid:create-agent",
    ]
    assert all(hit["score"] > 0 for hit in hits)


def test_resolve_navigation_candidates_prefers_navigation_catalog() -> None:
    hits = resolve_navigation_candidates(
        "operation logs",
        {
            "page_data": {
                "navigation_catalog": [
                    {
                        "title": "Operation Logs",
                        "path": "/admin/system/operation-logs",
                        "page_key": "admin.system.operation-logs",
                        "category": "System",
                        "keywords": ["audit", "logs"],
                        "breadcrumb": ["System", "Operation Logs"],
                    },
                    {
                        "title": "Agents",
                        "path": "/admin/ai/agents",
                        "page_key": "admin.ai.agents",
                        "category": "AI",
                    },
                ]
            }
        },
    )

    assert hits == [
        {
            "breadcrumb": ["System", "Operation Logs"],
            "page_key": "admin.system.operation-logs",
            "path": "/admin/system/operation-logs",
            "score": 960,
            "title": "Operation Logs",
        }
    ]


def test_resolve_navigation_candidates_ignores_legacy_available_menus_payload() -> None:
    hits = resolve_navigation_candidates(
        "operation logs",
        {
            "page_data": {
                "available_menus": [
                    {
                        "title": "Operation Logs",
                        "path": "/admin/system/operation-logs",
                        "page_key": "admin.system.operation-logs",
                        "category": "System",
                        "keywords": ["audit", "logs"],
                        "breadcrumb": ["System", "Operation Logs"],
                    }
                ]
            }
        },
    )

    assert hits == []
