"""Regression tests for shared organization controller helpers. / 组织。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.shared._organization_helpers import (
    commit_or_raise_http,
    serialize_organization_tree,
)
from app.exceptions import BusinessException


@pytest.mark.asyncio
async def test_commit_or_raise_http_commits_and_returns_result() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()

    result = await commit_or_raise_http(db, AsyncMock(return_value={"ok": True})())

    assert result == {"ok": True}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_commit_or_raise_http_maps_business_exception_to_http_400() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await commit_or_raise_http(
            db,
            AsyncMock(
                side_effect=BusinessException(message="organization blocked"),
            )(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "organization blocked"
    db.commit.assert_not_awaited()


def test_serialize_organization_tree_builds_nested_payload() -> None:
    nodes = [
        SimpleNamespace(id=1, parent_id=None, name="root"),
        SimpleNamespace(id=2, parent_id=1, name="child-a"),
        SimpleNamespace(id=3, parent_id=1, name="child-b"),
        SimpleNamespace(id=4, parent_id=2, name="leaf"),
    ]

    payload = serialize_organization_tree(
        nodes,
        lambda node: {"id": node.id, "name": node.name},
    )

    assert payload == [
        {
            "id": 1,
            "name": "root",
            "children": [
                {
                    "id": 2,
                    "name": "child-a",
                    "children": [
                        {"id": 4, "name": "leaf", "children": []},
                    ],
                },
                {"id": 3, "name": "child-b", "children": []},
            ],
        }
    ]
