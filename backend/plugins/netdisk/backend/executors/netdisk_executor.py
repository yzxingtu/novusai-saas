"""
Netdisk 工具执行器
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.tools.types import ExecutionContext


class NetdiskExecutor(BaseToolExecutor):
    """Netdisk 执行器"""

    async def validate(self, definition: ToolDefinition, arguments: dict[str, Any]) -> bool:
        if definition.name == "search_files":
            return bool(str(arguments.get("keyword", "")).strip())
        return True

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        if context is None or context.db is None:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("common.server_error"),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        try:
            if definition.name == "list_files":
                folder_path = str(arguments.get("folder_path", "/") or "/")
                file_type = str(arguments.get("file_type", "") or "")
                output = await self._list_files(
                    context.db,
                    context.tenant_id,
                    folder_path=folder_path,
                    file_type=file_type,
                )
            elif definition.name == "search_files":
                keyword = str(arguments.get("keyword", "")).strip()
                if not keyword:
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=_("common.invalid_request"),
                        duration_ms=int((time.perf_counter() - start) * 1000),
                    )
                file_type = str(arguments.get("file_type", "") or "")
                limit = arguments.get("limit", 10)
                try:
                    limit = int(limit)
                except (TypeError, ValueError):
                    limit = 10
                output = await self._search_files(
                    context.db,
                    context.tenant_id,
                    keyword=keyword,
                    file_type=file_type,
                    limit=limit,
                )
            else:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"{_('common.invalid_request')}: {definition.name}",
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )
        except Exception as exc:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=output,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    async def _list_files(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        folder_path: str = "/",
        file_type: str = "",
    ) -> str:
        from ..models.node import FileNode

        parent_id = await self._resolve_path(db, tenant_id, folder_path)
        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == tenant_id,
                FileNode.parent_id == parent_id,
                FileNode.is_deleted.is_(False),
            )
            .order_by(FileNode.node_type, FileNode.name)
        )

        if file_type:
            mime_prefix = self._file_type_to_mime(file_type)
            if mime_prefix:
                stmt = stmt.where(FileNode.mime_type.ilike(f"{mime_prefix}%"))

        result = await db.execute(stmt)
        nodes = result.scalars().all()

        items = [
            {
                "name": node.name,
                "type": node.node_type,
                "size": node.size_bytes,
                "mimeType": node.mime_type,
                "updatedAt": node.updated_at.isoformat() if node.updated_at else None,
            }
            for node in nodes
        ]
        return json.dumps(
            {"path": folder_path, "items": items, "total": len(items)},
            ensure_ascii=False,
        )

    async def _search_files(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        keyword: str,
        file_type: str = "",
        limit: int = 10,
    ) -> str:
        from ..models.node import FileNode

        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == tenant_id,
                FileNode.is_deleted.is_(False),
                FileNode.name.ilike(f"%{keyword}%"),
            )
            .order_by(FileNode.updated_at.desc())
            .limit(min(max(limit, 1), 50))
        )
        if file_type:
            mime_prefix = self._file_type_to_mime(file_type)
            if mime_prefix:
                stmt = stmt.where(FileNode.mime_type.ilike(f"{mime_prefix}%"))

        result = await db.execute(stmt)
        nodes = result.scalars().all()
        items = [
            {
                "name": node.name,
                "type": node.node_type,
                "size": node.size_bytes,
                "mimeType": node.mime_type,
                "updatedAt": node.updated_at.isoformat() if node.updated_at else None,
            }
            for node in nodes
        ]
        return json.dumps(
            {"keyword": keyword, "items": items, "total": len(items)},
            ensure_ascii=False,
        )

    async def _resolve_path(
        self,
        db: AsyncSession,
        tenant_id: int,
        path: str,
    ) -> int | None:
        from ..models.node import FileNode, NodeTypeEnum

        if not path or path == "/":
            return None

        parts = [p for p in path.strip("/").split("/") if p]
        current_parent: int | None = None

        for part in parts:
            result = await db.execute(
                select(FileNode.id).where(
                    FileNode.tenant_id == tenant_id,
                    FileNode.parent_id == current_parent,
                    FileNode.name == part,
                    FileNode.node_type == NodeTypeEnum.FOLDER.value,
                    FileNode.is_deleted.is_(False),
                )
            )
            node_id = result.scalar_one_or_none()
            if node_id is None:
                return None
            current_parent = node_id
        return current_parent

    @staticmethod
    def _file_type_to_mime(file_type: str) -> str:
        mapping = {
            "image": "image/",
            "video": "video/",
            "audio": "audio/",
            "pdf": "application/pdf",
            "doc": "application/vnd",
            "text": "text/",
            "zip": "application/zip",
        }
        return mapping.get(file_type.lower(), "")
