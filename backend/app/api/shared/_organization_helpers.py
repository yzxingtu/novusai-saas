"""Shared organization-controller helpers. / 组织控制器共享辅助。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, NoReturn, Protocol, TypeVar

from fastapi import HTTPException, status

from app.core.deps import DbSession
from app.exceptions import BusinessException, NotFoundException

TResult = TypeVar("TResult")


class OrganizationTreeNode(Protocol):
    """Minimal node contract for organization tree serialization."""

    id: int
    parent_id: int | None


TNode = TypeVar("TNode", bound=OrganizationTreeNode)


def raise_organization_http(exc: Exception) -> NoReturn:
    """Normalize business errors to HTTP errors for organization endpoints."""
    if isinstance(exc, NotFoundException):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc.message),
        )
    if isinstance(exc, BusinessException):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc.message),
        )
    raise exc


async def await_or_raise_http(operation: Awaitable[TResult]) -> TResult:
    """Await an organization service call and re-map known business exceptions."""
    try:
        return await operation
    except Exception as exc:
        raise_organization_http(exc)


async def commit_or_raise_http(
    db: DbSession,
    operation: Awaitable[TResult],
) -> TResult:
    """Run an organization mutation, commit on success, and normalize failures."""
    try:
        result = await operation
        await db.commit()
        return result
    except Exception as exc:
        raise_organization_http(exc)


def serialize_organization_tree(
    org_nodes: Sequence[TNode],
    serializer: Callable[[TNode], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Serialize flat organization nodes into a nested tree payload."""
    if not org_nodes:
        return []

    node_map = {org_node.id: org_node for org_node in org_nodes}
    children_map: dict[int, list[TNode]] = {org_node.id: [] for org_node in org_nodes}
    roots: list[TNode] = []

    for org_node in org_nodes:
        if org_node.parent_id is not None and org_node.parent_id in node_map:
            children_map[org_node.parent_id].append(org_node)
        else:
            roots.append(org_node)

    def build(node: TNode) -> dict[str, Any]:
        payload = dict(serializer(node))
        payload["children"] = [build(child) for child in children_map.get(node.id, [])]
        return payload

    return [build(root) for root in roots]
